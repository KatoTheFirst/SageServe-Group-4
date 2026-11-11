"""
Tạo trace v2 từ trace v1 (v1 giữ nguyên), chỉ sửa thuộc tính trượt cổng docs/TRACE_SPEC.md. Mỗi cờ ứng với một cổng:
  --niw_sigma S        T6 NIW `t7`: trọng số phút log-normal(0, S) cho NIW trong từng giờ (Fig. 3d)
  --spikes TIER M...   T6 `t11`: mỗi giờ, mỗi hệ số M tạo 1 phút có tải gấp M lần phút thường (Fig. 3b). TIER: IW hoặc NIW
  --fill_week_iwn      T7b: Azure conv thiếu thứ Sáu, thứ Bảy -> chép IW-N của thứ Năm sang thứ Sáu, của Chủ Nhật sang thứ Bảy
  --iwn_diurnal A      T2: Azure conv gần như không có chu kỳ ngày -> lọc IW-N của Bloom theo hình ngày của IW-F (mức A)
  --region_share W C E T4 `t11`: rút lại vùng gốc của IW theo tỉ lệ này (Fig. 5)
  --clip_max P         T5: giảm tỉ lệ prompt bị cắt ở 8192 của từng mô hình về P%, thay bằng prompt chưa cắt của mô hình đó
  --niw_ratio R        T1 §4: đưa số NIW về IW/R bằng lấy mẫu có hoàn lại
Số request IW theo giờ không đổi, trừ --fill_week_iwn.

Dùng: python make_trace_v2.py traces/composed_day_3regions.csv traces/composed_day_3regions_v2.csv --niw_sigma 0.22
"""
import argparse

import numpy as np
import pandas as pd

MAX_PROMPT = 8192


def reshape_minutes(df, mask, weights_of_hour, rng):
    """Đổi phút đến của các request trong mask, giữ nguyên số request mỗi giờ."""
    t = df.arrival_timestamp.values.copy()
    idx = np.flatnonzero(mask.values)
    hours = (t[idx] // 3600).astype(int)
    for h in np.unique(hours):
        sel = idx[hours == h]
        w = weights_of_hour(rng)
        t[sel] = h * 3600 + rng.choice(60, size=len(sel), p=w / w.sum()) * 60 + rng.random(len(sel)) * 60
    df["arrival_timestamp"] = t.round(3)
    return df


def lognormal_weights(sigma):
    return lambda rng: np.exp(rng.normal(0, sigma, 60))


def spike_weights(multipliers):
    def weights(rng):
        w = np.ones(60)
        w[rng.choice(60, size=len(multipliers), replace=False)] = multipliers
        return w
    return weights


def fill_week_iwn(df):
    """Trace bắt đầu thứ Sáu: ngày 0 = thứ Sáu, 1 = thứ Bảy, 2 = Chủ Nhật, 6 = thứ Năm."""
    iwn = df[df.scenario == "IW-N"]
    day = (iwn.arrival_timestamp // 86400).astype(int)
    assert not (day < 2).any(), "trace đã có IW-N ở ngày 0, 1"
    fri = iwn[day == 6].assign(arrival_timestamp=lambda x: x.arrival_timestamp - 6 * 86400)
    sat = iwn[day == 2].assign(arrival_timestamp=lambda x: x.arrival_timestamp - 86400)
    return pd.concat([df, fri, sat], ignore_index=True)


def iwn_diurnal(df, model, shape_from, amount, rng):
    """T2: IW-N theo xu hướng IW-F (§3). Lọc IW-N của model với xác suất giữ 1 - amount * (1 - s(giờ trong ngày)), s = hình ngày của IW-F, đỉnh 1."""
    w = pd.read_csv(shape_from, usecols=["arrival_timestamp", "scenario", "model_type"])
    w = w[(w.scenario == "IW-F") & (w.model_type == model)]
    s = w.groupby((w.arrival_timestamp % 86400 // 3600).astype(int)).size()
    s = (s / s.max()).reindex(range(24)).values
    x = (df.scenario == "IW-N") & (df.model_type == model)
    hour = (df.arrival_timestamp[x] % 86400 // 3600).astype(int).values
    keep = rng.random(x.sum()) < 1 - amount * (1 - s[hour])
    return df.drop(df.index[x][~keep]).reset_index(drop=True)


def redraw_regions(df, share, rng):
    iw = (df.scenario != "NIW").values
    first = rng.choice(3, size=iw.sum(), p=np.array(share) / sum(share))
    swap = rng.random(iw.sum()) < 0.5
    rest = {0: "12", 1: "02", 2: "01"}
    order = [f"{f}{rest[f][::-1] if s else rest[f]}" for f, s in zip(first, swap)]
    df = df.astype({"regions": str})
    df.loc[iw, "client_tenant"] = first
    df.loc[iw, "regions"] = order
    return df


def reduce_clip(df, target_pct, rng):
    iw = df.scenario != "NIW"
    for _, x in df[iw].groupby("model_type"):
        clipped = x.index[x.prompt_size >= MAX_PROMPT]
        extra = len(clipped) - int(target_pct / 100 * len(x))
        if extra > 0:
            pool = x.prompt_size[x.prompt_size < MAX_PROMPT].values
            df.loc[rng.choice(clipped, size=extra, replace=False), "prompt_size"] = rng.choice(pool, size=extra)
    return df


def set_niw_ratio(df, ratio, rng):
    niw, iw = df[df.scenario == "NIW"], df[df.scenario != "NIW"]
    return pd.concat([iw, niw.sample(int(len(iw) / ratio), replace=True, random_state=int(rng.integers(1 << 31)))], ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("output_csv")
    ap.add_argument("--niw_sigma", type=float)
    ap.add_argument("--spikes", nargs="+", action="append", metavar=("TIER", "M"))
    ap.add_argument("--fill_week_iwn", action="store_true")
    ap.add_argument("--region_share", type=float, nargs=3)
    ap.add_argument("--clip_max", type=float)
    ap.add_argument("--niw_ratio", type=float)
    ap.add_argument("--iwn_diurnal", type=float)
    ap.add_argument("--shape_from", default="traces/composed_week_3regions.csv")
    ap.add_argument("--seed", type=int, default=2)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    df = pd.read_csv(a.trace, dtype={"regions": str})
    if a.fill_week_iwn:
        df = fill_week_iwn(df)
    if a.iwn_diurnal:
        df = iwn_diurnal(df, "bloom-176b", a.shape_from, a.iwn_diurnal, rng)
    if a.niw_ratio:
        df = set_niw_ratio(df, a.niw_ratio, rng)
    if a.region_share:
        df = redraw_regions(df, a.region_share, rng)
    if a.clip_max is not None:
        df = reduce_clip(df, a.clip_max, rng)
    if a.niw_sigma:
        df = reshape_minutes(df, df.scenario == "NIW", lognormal_weights(a.niw_sigma), rng)
    for spec in a.spikes or []:
        mask = df.scenario != "NIW" if spec[0] == "IW" else df.scenario == spec[0]
        df = reshape_minutes(df, mask, spike_weights([float(m) for m in spec[1:]]), rng)
    df = df.sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    df["request_id"] = df.index
    df.to_csv(a.output_csv, index=False)
    print(f"[+] {a.output_csv}: {len(df):,} request ({(df.scenario != 'NIW').sum():,} IW)")


if __name__ == "__main__":
    main()
