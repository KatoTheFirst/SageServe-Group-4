"""
Bài kiểm thử trace (trace qualification) cho kế hoạch tái hiện SageServe.

Mỗi kết luận của bài báo chỉ xuất hiện được nếu trace có một đặc tính nhất định. Mỗi cổng (G1..G9) kiểm tra một
đặc tính đó với ngưỡng PASS/FAIL lấy từ số liệu bài báo. Trace phải qua TẤT CẢ cổng trước khi được "đóng băng"
(ghi mã băm) để dùng cho toàn bộ kế hoạch 12 tuần.

Dùng: python qualify_trace.py <trace tuần (có thể lấy mẫu)> --day0 4 --sample_frac 0.25
      (--day0: thứ của ngày 0, 0 = Thứ Hai; trace ghép Azure bắt đầu thứ Sáu -> 4)
"""
import argparse
import hashlib
import sys
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf

warnings.filterwarnings("ignore")
A, B = "bloom-176b", "llama2-70b"
results = []


def gate(code, conclusion, ok, value, need):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {code} – {conclusion}\n        đo được: {value} | yêu cầu: {need}")


def forecast_mape(series, window=60, horizon=60, step=60):
    """ARIMA cửa sổ 60 phút, chọn bậc theo AIC, dự báo đỉnh 60 phút tới (Phụ lục B, §6.3)."""
    orders = [(1, 0, 0), (2, 0, 0), (1, 1, 1), (2, 1, 1), (0, 1, 1)]
    errs = []
    for t in range(24 * 60, len(series) - horizon, step):
        train, actual = series[t - window:t], series[t:t + horizon]
        best = None
        for o in orders:
            try:
                fit = ARIMA(train, order=o).fit()
                if best is None or fit.aic < best.aic:
                    best = fit
            except Exception:
                pass
        if best is not None and actual.max() > 0:
            errs.append(abs(best.forecast(horizon).max() - actual.max()) / actual.max())
    return 100 * np.mean(errs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--day0", type=int, default=0)
    ap.add_argument("--sample_frac", type=float, default=1.0)
    a = ap.parse_args()
    d = pd.read_csv(a.trace, usecols=["scenario", "model_type", "client_tenant", "arrival_timestamp",
                                      "prompt_size", "token_size"])
    hours = int(d.arrival_timestamp.max() // 3600) + 1
    d["hour"] = (d.arrival_timestamp // 3600).astype(int)
    d["weekday"] = (d.arrival_timestamp // 86400 + a.day0).astype(int) % 7
    iw = d[d.scenario != "NIW"]
    print(f"Trace: {a.trace} ({len(d):,} request, {hours / 24:.1f} ngày)\n")

    share = 100 * len(iw) / len(d)
    gate("G1", "Tỉ lệ IW/NIW giống production (§3, Phụ lục A)", 65 <= share <= 80, f"IW = {share:.1f}%", "65–80% (bài báo 72%)")

    def ps(tier, model):
        s = d[(d.scenario == tier) & (d.model_type == model)].groupby("hour").size().reindex(range(hours), fill_value=0)
        return acf(s, nlags=24)[24]
    week = hours >= 48     # G2, G3, G9 cần nhiều ngày -> trace 1 ngày được kiểm qua trace tuần sinh cùng tham số
    if not week:
        print("[N/A ] G2, G3, G9 – cần trace ≥ 2 ngày; kiểm trên trace tuần sinh bằng cùng tham số\n")
    if week:
        pa, pn = ps("IW-F", A), ps("NIW", A)
        gate("G2", "IW có chu kỳ ngày, NIW không (§3) → dự báo có ích cho IW",
             pa >= 0.6 and pn <= 0.3, f"ACF24 IW-F(A) = {pa:.2f}, NIW(A) = {pn:.2f}", "IW-F ≥ 0,6 (bài báo 0,7–0,95); NIW ≤ 0,3 (0–0,29)")

    wd = iw.groupby("weekday").size()
    ratio = wd.reindex([5, 6]).mean() / wd.reindex(range(5)).mean()
    if week:
        gate("G3", "Cuối tuần tải IW giảm (§3, §7.2.7 cả tuần)", ratio <= 0.6, f"cuối tuần / ngày thường = {ratio:.2f}", "≤ 0,6")

    # §3: "IW-F ... East US exhibiting a high demand, followed by Central US and West US" (câu này nói về IW-F)
    reg = d[d.scenario == "IW-F"].groupby("client_tenant").size()
    niw_reg = d[d.scenario == "NIW"].groupby("client_tenant").size()
    a_ew = (lambda x: x.get(2, 0) / max(x.get(0, 1), 1))(d[(d.scenario == "IW-F") & (d.model_type == A)].groupby("client_tenant").size())
    ok = reg.get(2, 0) > reg.get(1, 0) > reg.get(0, 0) and niw_reg.idxmin() == 0 and 3 <= a_ew <= 7
    gate("G4", "Lệch tải giữa vùng → ILP có lý do chuyển tải (§3, §5)", ok,
         f"IW-F W/C/E = {reg.get(0, 0):,}/{reg.get(1, 0):,}/{reg.get(2, 0):,}; NIW ít nhất ở vùng {niw_reg.idxmin()}; A IW-F East/West = {a_ew:.1f}",
         "IW-F: East > Central > West; NIW ít nhất ở West; East/West 3–7 (bài báo ~4)")

    gt1k, lt1k = 100 * (iw.prompt_size > 1000).mean(), 100 * (iw.token_size < 1000).mean()
    clip = 100 * (d.prompt_size >= 8192).mean()
    gate("G5", "Request dài như production (Fig. 10) → bộ nhớ KV đủ lớn để co giãn",
         gt1k > 50 and lt1k > 50 and clip <= 10, f"input > 1k: {gt1k:.0f}%, output < 1k: {lt1k:.0f}%, bị cắt ở 8192: {clip:.1f}%",
         "> 50%, > 50%, ≤ 10%")

    r = len(iw) / max((d.scenario == "NIW").sum(), 1)
    gate("G6", "Tỉ lệ IW:NIW (Phụ lục A, T11/2024)", 2.7 <= r <= 3.3, f"{r:.2f}:1", "3:1 ± 10%")

    h = iw[(iw.model_type == A) & (iw.client_tenant == 2) & (iw.weekday < 5)].groupby("hour").size()
    amp = h.quantile(0.95) / max(h.quantile(0.05), 1)
    gate("G7", "Biên độ ngày đủ lớn → Unified/LT tiết kiệm được máy giờ thấp điểm (§4, §7.2.1)",
         amp >= 2, f"đỉnh/đáy theo giờ (A, East, ngày thường) = {amp:.1f}", "≥ 2")

    f, n = 100 * (iw.scenario == "IW-F").mean(), 100 * (iw.scenario == "IW-N").mean()
    gate("G8", "Có đủ IW-F và IW-N để so bộ lập lịch (§7.2.6)", f >= 20 and n >= 20, f"IW-F {f:.0f}%, IW-N {n:.0f}%", "mỗi loại ≥ 20% IW")

    mapes = {}
    for model, reg_id in ([(A, 2), (A, 0), (B, 1), (B, 0)] if week else []):
        x = iw[(iw.model_type == model) & (iw.client_tenant == reg_id)]
        tpm = (x.groupby((x.arrival_timestamp // 60).astype(int)).prompt_size.sum() / a.sample_frac)
        tpm = tpm.reindex(range(hours * 60), fill_value=0).values.astype(float)
        mapes[f"{model}@{reg_id}"] = forecast_mape(tpm)
    worst = max(mapes.values()) if mapes else None
    if week:
        gate("G9", "Tải dự báo được bằng ARIMA cửa sổ 60 phút (§6.3, Phụ lục B) → chiến lược LT có lợi",
             worst <= 30, ", ".join(f"{k} {v:.0f}%" for k, v in mapes.items()), "MAPE đỉnh giờ ≤ 30% (bài báo ARIMA-60 ~20%)")

    # G10 (tải đủ để co giãn) KHÔNG ước lượng được từ trace: bộ nhớ KV phụ thuộc độ dài output và thời gian xử lý.
    # Đo trực tiếp bằng một bài Reactive ngắn ở giờ cao điểm: python check_g10.py results/<bài Reactive>
    print("[ -> ] G10 – đo bằng check_g10.py trên bài chạy Reactive (xem REPRODUCE.md)")

    digest = hashlib.sha256(open(a.trace, "rb").read()).hexdigest()[:16]
    print(f"\nKẾT QUẢ: {sum(results)}/{len(results)} cổng PASS | sha256 trace: {digest}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
