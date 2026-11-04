"""Pha 6 (D21a): hành vi co giãn của một mô hình theo vùng, bỏ giờ đầu (t < 3600 s, đợt giảm từ 20 instance).
Chỉ số CHÍNH = số lần lấy lại spot + khởi động mới (dòng SCALEUP_WASTE trong run.log).
Scale-in = số lần cột prod (arbiters/<vùng>/*.csv) giảm. Flap (phụ) = ghép 1–1: theo thứ tự thời gian, mỗi lần prod tăng khớp với
lần prod giảm gần nhất trước nó, chưa được ghép, cách ≤ 1800 s. Lãng phí = tổng thời gian chờ lấy lại/khởi động.
Dùng: python experiments/reactive_behavior.py <bài> [model] [gpus/instance]"""
import glob
import sys

import pandas as pd

SKIP = 3600


def flaps(downs, ups, window=1800):
    used, n = set(), 0
    for u in sorted(ups):
        cand = [i for i, d in enumerate(downs) if d < u and u - d <= window and i not in used]
        if cand:
            used.add(max(cand, key=lambda i: downs[i]))     # scale-in gần nhất trước scale-out này
            n += 1
    return n


def table(run, model="llama2-70b", gpus=8):
    w = []
    for line in open(f"{run}/run.log", encoding="utf-8", errors="ignore"):
        if "SCALEUP_WASTE," in line:
            t, m, kind, sec, region = line.strip().split("SCALEUP_WASTE,")[1].split(",")[:5]
            if m == model and float(t) >= SKIP:
                w.append({"t": float(t), "kind": kind, "sec": float(sec), "region": region})
    w = pd.DataFrame(w, columns=["t", "kind", "sec", "region"])
    rows = []
    for region in sorted(p.replace("\\", "/").split("/")[-1] for p in glob.glob(f"{run}/arbiters/*")):
        a = pd.concat(pd.read_csv(f) for f in glob.glob(f"{run}/arbiters/{region}/*.csv"))
        a = a[a.model == model].sort_values("timestamp", kind="stable")
        prod, ts = a["prod"].astype(int).to_numpy(), a.timestamp.to_numpy()
        step, t1 = prod[1:] - prod[:-1], ts[1:]
        keep = t1 >= SKIP
        downs, ups = list(t1[keep & (step < 0)]), list(t1[keep & (step > 0)])
        r = w[w.region == region]
        rows.append({"vùng": region, "CHÍNH: lấy lại spot + khởi động": len(r), "lấy lại spot": int((r.kind == "reclaim_spot").sum()),
                     "khởi động mới": int((r.kind == "spin_up").sum()), "scale-in": len(downs), "flap 1–1 ≤30 phút": flaps(downs, ups),
                     "lãng phí (instance-giờ)": r.sec.sum() / 3600})
    t = pd.DataFrame(rows)
    t.loc[len(t)] = {"vùng": "tổng", **t.drop(columns="vùng").sum().to_dict()}
    t[f"lãng phí (GPU-giờ, x{gpus})"] = t["lãng phí (instance-giờ)"] * gpus
    return t


def main():
    run, model = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "llama2-70b")
    gpus = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    print(f"{run} | {model} | bỏ t < {SKIP} s")
    print(table(run, model, gpus).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
