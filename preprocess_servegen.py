"""
Pipeline tiền xử lý trace Alibaba ServeGen -> định dạng trace của SageServe (Trace.from_csv).

Nguồn (tải bằng download_servegen.py vào traces/raw_servegen/):
- Online (IW): 14 ngày, mỗi client có rate/CV/phân phối khoảng cách đến (Gamma/Weibull) theo
  cửa sổ 600s và phân phối token vào/ra theo cửa sổ 6h.
- Offline (NIW): 3 batch job thật (trace_d/e/f.jsonl) có độ dài token vào/ra, không có thời điểm gửi.

Ánh xạ và giả định (ghi rõ trong báo cáo):
- Mô hình: m-large -> bloom-176b, m-mid -> llama2-70b, m-small -> llama3.1-8b,
  deepseek-r1 -> llama3.2-3b (chỉ có 1 ngày, chỉ dùng khi --models có r1).
- Vùng: client_id % 3 (mỗi client cố định thuộc 1 vùng).
- IW: ServeGen không tách IW-F/IW-N (giống trace T11/2024 của bài báo) -> mọi request online là IW-F.
- Khối lượng: mỗi mô hình được nhân một hệ số cố định để đạt --iw_per_day; hình dạng theo thời gian
  giữ nguyên. Tỉ lệ IW:NIW mặc định 3:1 (Phụ lục A của bài báo).
- NIW: mỗi ngày mỗi job gửi 1 lần vào giờ cố định trong NIW_SUBMIT_HOURS.
"""
import argparse
import ast
import glob
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from validate_trace import validate_trace_file

MODELS = {
    "m-large": ("language/m-large", "bloom-176b"),
    "m-mid": ("language/m-mid", "llama2-70b"),
    "m-small": ("language/m-small", "llama3.1-8b"),
    "r1": ("reason/deepseek-r1", "llama3.2-3b"),
}
DEFAULT_SHARE = {"m-mid": 0.40, "m-large": 0.30, "m-small": 0.30, "r1": 0.15}
NIW_JOBS = ["trace_d", "trace_e", "trace_f"]
NIW_SUBMIT_HOURS = [1, 9, 17]
REGION_ORDERS = {0: ["012", "021"], 1: ["120", "102"], 2: ["201", "210"]}
WINDOW = 600
MAX_PROMPT, MAX_TOKENS = 8192, 4096


def read_rates(raw, model):
    """Bảng dài: client, ts, rate, cv, pat, a1, a2 (bỏ cửa sổ rỗng)."""
    rows = []
    for f in glob.glob(os.path.join(raw, MODELS[model][0], "chunk-*-trace.csv")):
        cid = int(os.path.basename(f).split("-")[1])
        df = pd.read_csv(f, header=None, names=["ts", "rate", "cv", "pat", "a1", "a2"])
        df["client"] = cid
        rows.append(df)
    df = pd.concat(rows, ignore_index=True)
    df = df[df["pat"].notna() & (df["rate"] > 0)].copy()
    df["region"] = df["client"] % 3
    return df.sort_values(["client", "ts"]).reset_index(drop=True)


def _parse_pdf(text):
    pdf = ast.literal_eval(text)  # an toàn với dữ liệu tải về, không dùng eval()
    if not pdf:
        return None
    vals = np.array(list(pdf.keys()), dtype=float)
    probs = np.array(list(pdf.values()), dtype=float)
    return vals, np.cumsum(probs) / probs.sum()


def read_token_dists(raw, model):
    """client -> sorted list of (ts, {'input_tokens': (vals, cdf), 'output_tokens': ...})."""
    out = {}
    for f in glob.glob(os.path.join(raw, MODELS[model][0], "chunk-*-dataset.json")):
        cid = int(os.path.basename(f).split("-")[1])
        windows = []
        for ts, fields in json.load(open(f)).items():
            d = {k: _parse_pdf(fields[k]) for k in ("input_tokens", "output_tokens")}
            if all(v is not None for v in d.values()):
                windows.append((int(ts), d))
        if windows:
            out[cid] = sorted(windows, key=lambda w: w[0])
    return out


def dist_at(windows, ts):
    """Cửa sổ token gần nhất có mốc <= ts (hoặc cửa sổ đầu tiên)."""
    best = windows[0][1]
    for wts, d in windows:
        if wts > ts:
            break
        best = d
    return best


def mean_of(dist):
    vals, cdf = dist
    return float(np.sum(vals * np.diff(np.concatenate([[0.0], cdf]))))


def sample(dist, n, rng):
    vals, cdf = dist
    return vals[np.minimum(np.searchsorted(cdf, rng.random(n)), len(vals) - 1)]


def iats(pat, a1, a2, n, rng):
    if pat == "Gamma":
        x = stats.gamma.rvs(a=a1, scale=a2, size=n, random_state=rng)
    elif pat == "Weibull":
        x = stats.weibull_min.rvs(c=a1, scale=a2, size=n, random_state=rng)
    else:
        raise ValueError(f"Unknown arrival pattern: {pat}")
    return np.maximum(x, 1e-12)


def fallback_dists(rates, dists):
    """Client không có phân phối token (ngoài top 95%) dùng phân phối của client lớn nhất cùng vùng."""
    vol = rates.groupby("client")["rate"].sum()
    top = {}
    for cid in vol.sort_values(ascending=False).index:
        if cid in dists:
            top.setdefault(cid % 3, cid)
    first = next(iter(top.values()))
    return {cid: dists.get(cid, dists[top.get(cid % 3, first)]) for cid in vol.index}


def export_rates(raw, models, path):
    """RPS/TPS thật (chưa co giãn) theo (mô hình, vùng, cửa sổ 600s) cho phân tích chuỗi thời gian."""
    out = []
    for m in models:
        rates = read_rates(raw, m)
        dists = fallback_dists(rates, read_token_dists(raw, m))
        mean_cache = {}

        def means(cid, ts):
            key = (cid, ts // 21600)
            if key not in mean_cache:
                d = dist_at(dists[cid], ts)
                mean_cache[key] = (mean_of(d["input_tokens"]), mean_of(d["output_tokens"]))
            return mean_cache[key]

        mi = np.array([means(c, t) for c, t in zip(rates["client"], rates["ts"])])
        rates["tps_in"] = rates["rate"] * mi[:, 0]
        rates["tps_out"] = rates["rate"] * mi[:, 1]
        agg = rates.groupby(["region", "ts"])[["rate", "tps_in", "tps_out"]].sum().reset_index()
        agg.insert(0, "model", MODELS[m][1])
        out.append(agg.rename(columns={"rate": "rps"}))
    df = pd.concat(out, ignore_index=True)
    df.to_csv(path, index=False)
    print(f"[+] Rates written to {path} ({len(df):,} rows)")
    return df


def load_rates_grid(path="traces/servegen_rates_600s.csv", days=14):
    """Lưới đầy đủ (mô hình, vùng, cửa sổ 600s) từ file export_rates.
    Cửa sổ mà cả 3 vùng đều không có dữ liệu là lỗ hổng thu thập (gap=True) -> nội suy tuyến tính;
    vùng không có request trong khi vùng khác có -> 0."""
    r = pd.read_csv(path)
    ts_all = range(0, days * 86400, WINDOW)
    out = []
    for m, x in r.groupby("model"):
        present = set(x.ts)
        grid = pd.MultiIndex.from_product([[0, 1, 2], ts_all], names=["region", "ts"])
        g = x.set_index(["region", "ts"]).drop(columns="model").reindex(grid, fill_value=0).reset_index()
        g["gap"] = ~g.ts.isin(present)
        cols = ["rps", "tps_in", "tps_out"]
        g.loc[g.gap, cols] = np.nan
        g[cols] = g.groupby("region")[cols].transform(lambda s: s.interpolate(limit_direction="both"))
        g.insert(0, "model", m)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def generate_iw(raw, model, start, end, iw_per_day, rng):
    rates = read_rates(raw, model)
    dists = fallback_dists(rates, read_token_dists(raw, model))
    span_days = (rates["ts"].max() + WINDOW) / 86400
    scale = iw_per_day / ((rates["rate"] * WINDOW).sum() / span_days)
    win = rates[(rates["ts"] >= start) & (rates["ts"] < end)]

    times, prompts, tokens, regions = [], [], [], []
    for r in win.itertuples(index=False):
        exp = r.rate * WINDOW * scale
        n = int(exp) + int(rng.random() < exp - int(exp))
        if n == 0:
            continue
        gaps = iats(r.pat, r.a1, r.a2, n, rng)
        t = np.concatenate([[0.0], np.cumsum(gaps)[:-1]]) * (WINDOW / gaps.sum())
        d = dist_at(dists[r.client], r.ts)
        times.append(r.ts - start + t)
        prompts.append(sample(d["input_tokens"], n, rng))
        tokens.append(sample(d["output_tokens"], n, rng))
        regions.append(np.full(n, r.region))
    if not times:
        return pd.DataFrame()
    print(f"    {model} -> {MODELS[model][1]}: scale={scale:.2e}, {sum(map(len, times)):,} IW requests")
    return pd.DataFrame({
        "arrival_timestamp": np.round(np.concatenate(times), 3),
        "prompt_size": np.concatenate(prompts), "token_size": np.concatenate(tokens),
        "client_tenant": np.concatenate(regions), "model_type": MODELS[model][1],
        "scenario": "IW-F", "workload_type": "prod", "sla": 1, "utility": 5.0,
    })


def generate_niw(raw, models, days, n_niw, rng, spread=False):
    # Mặc định: mỗi batch job gán 1 mô hình, gửi 1 lần/ngày.
    # spread: mỗi mô hình 1 luồng NIW (job xoay vòng), thời điểm gửi rải đều trong ngày
    #         (bài báo §2.2, Fig. 4-5: NIW ổn định, không chu kỳ, có ở mọi mô hình).
    streams = [(NIW_JOBS[i % len(NIW_JOBS)], m, i) for i, m in enumerate(models)] if spread \
        else [(job, models[j % len(models)], j) for j, job in enumerate(NIW_JOBS)]
    per_day = max(1, n_niw // (len(streams) * days))
    out = []
    for job, m, k in streams:
        df = pd.read_json(os.path.join(raw, "offline", f"{job}.jsonl"), lines=True)
        model = MODELS[m][1]
        for day in range(days):
            # job thật ~50k request; cần nhiều hơn (tải full scale) thì lấy mẫu có lặp lại
            s = df.sample(n=per_day, replace=per_day > len(df), random_state=int(rng.integers(1 << 31)))
            arrival = (day * 86400 + rng.uniform(0, 86400, len(s))) if spread \
                else float(day * 86400 + NIW_SUBMIT_HOURS[k] * 3600)
            out.append(pd.DataFrame({
                "arrival_timestamp": arrival,
                "prompt_size": s["input_length"].values, "token_size": s["output_length"].values,
                "client_tenant": k % 3, "model_type": model,
                "scenario": "NIW", "workload_type": "dev", "sla": 86400, "utility": 1.0,
            }))
    return pd.concat(out, ignore_index=True)


def build_trace(raw, output_csv, models, start_day, days, iw_per_day, niw_ratio, seed, validate=True, one_region=False,
                niw_spread=False, prompt_scale=1.0):
    rng = np.random.default_rng(seed)
    start, end = start_day * 86400, (start_day + days) * 86400
    share = np.array([DEFAULT_SHARE[m] for m in models])
    share = share / share.sum()
    print(f"[*] ServeGen days {start_day}..{start_day + days - 1}, models={models}")
    iw = pd.concat([generate_iw(raw, m, start, end, iw_per_day * s, rng) for m, s in zip(models, share)],
                   ignore_index=True)
    niw = generate_niw(raw, models, days, int(len(iw) / niw_ratio), rng, spread=niw_spread)
    df = pd.concat([iw, niw], ignore_index=True).sort_values("arrival_timestamp", kind="stable")
    # prompt_scale: kéo dài prompt cho giống bài báo (§7.1, Fig. 10: phần lớn request > 1k token đầu vào)
    df["prompt_size"] = (df["prompt_size"] * prompt_scale).clip(1, MAX_PROMPT).astype(int)
    df["token_size"] = df["token_size"].clip(1, MAX_TOKENS).astype(int)
    df["client_tenant"] = 0 if one_region else df["client_tenant"].astype(int)  # one_region: thí nghiệm §4 (chỉ West US)
    df["regions"] = [REGION_ORDERS[c][i] for c, i in zip(df["client_tenant"], rng.integers(0, 2, len(df)))]
    df = df.reset_index(drop=True)
    df["request_id"] = df.index
    df["batch_id"], df["request_type"], df["application_id"], df["batch_size"] = -1, 2, 0, 1
    cols = ["request_id", "batch_id", "client_tenant", "request_type", "scenario", "sla", "utility", "regions",
            "model_type", "workload_type", "application_id", "arrival_timestamp", "batch_size",
            "prompt_size", "token_size"]
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    df[cols].to_csv(output_csv, index=False)
    print(f"[+] {output_csv}: {len(df):,} requests ({len(iw):,} IW + {len(niw):,} NIW)")
    if validate and not validate_trace_file(output_csv, verbose=True):
        raise RuntimeError(f"Validation FAILED for {output_csv}")
    return df


def main():
    ap = argparse.ArgumentParser(description="ServeGen -> SageServe trace")
    ap.add_argument("--raw", default="traces/raw_servegen")
    ap.add_argument("--output_csv", default="traces/servegen_dev_1day.csv")
    ap.add_argument("--models", nargs="+", default=["m-large", "m-mid", "m-small"], choices=list(MODELS))
    ap.add_argument("--start_day", type=int, default=0)
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--iw_per_day", type=int, default=90000, help="Tổng số request IW mỗi ngày sau co giãn")
    ap.add_argument("--niw_ratio", type=float, default=3.0, help="Tỉ lệ IW:NIW")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--export_rates", default=None, help="Ghi RPS/TPS thật theo 600s ra CSV rồi thoát")
    ap.add_argument("--no_validate", action="store_true")
    ap.add_argument("--one_region", action="store_true", help="Gom mọi request về vùng 0 (westus), như thí nghiệm §4")
    ap.add_argument("--niw_spread", action="store_true", help="Rải đều NIW suốt ngày thay vì gửi theo đợt")
    ap.add_argument("--prompt_scale", type=float, default=1.0, help="Nhân độ dài prompt (giữ nguyên output)")
    a = ap.parse_args()
    if a.export_rates:
        export_rates(a.raw, a.models, a.export_rates)
        return
    build_trace(a.raw, a.output_csv, a.models, a.start_day, a.days, a.iw_per_day, a.niw_ratio, a.seed,
                validate=not a.no_validate, one_region=a.one_region, niw_spread=a.niw_spread,
                prompt_scale=a.prompt_scale)


if __name__ == "__main__":
    main()
