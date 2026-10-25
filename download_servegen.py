"""
Tải trace Alibaba ServeGen (github.com/alibaba/ServeGen, Apache-2.0) về traces/raw_servegen/.

- Tải toàn bộ chunk-*-trace.csv (tốc độ đến theo cửa sổ 600s, 14 ngày) của 4 mô hình:
  language/m-large, language/m-mid, language/m-small, reason/deepseek-r1.
- Chỉ tải chunk-*-dataset.json (phân bố token) của các client lớn nhất, đủ phủ
  --coverage tổng lượng request của mỗi mô hình (bộ đầy đủ ~800MB).
- Tải các batch job offline dạng stat (trace_d/e/f.jsonl) làm tải NIW.
"""
import argparse
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = "alibaba/ServeGen"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
MODELS = ["language/m-large", "language/m-mid", "language/m-small", "reason/deepseek-r1"]
OFFLINE = ["data/offline/README.md", "data/offline/trace_d.jsonl",
           "data/offline/trace_e.jsonl", "data/offline/trace_f.jsonl"]


def fetch(path, out_root):
    dest = os.path.join(out_root, path[len("data/"):])
    if os.path.exists(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(RAW + path, timeout=120) as r, open(dest + ".part", "wb") as f:
        f.write(r.read())
    os.replace(dest + ".part", dest)
    return dest


def client_volume(trace_csv):
    """Tổng số request ước tính = sum(rate * độ dài cửa sổ)."""
    rows = [line.strip().split(",") for line in open(trace_csv) if line.strip()]
    ts = [int(r[0]) for r in rows]
    total = 0.0
    for i, r in enumerate(rows):
        width = ts[i + 1] - ts[i] if i + 1 < len(ts) else 600
        total += float(r[1]) * width
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="traces/raw_servegen")
    ap.add_argument("--coverage", type=float, default=0.95)
    args = ap.parse_args()

    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1") as r:
        tree = [x["path"] for x in json.load(r)["tree"] if x["type"] == "blob"]

    pool = ThreadPoolExecutor(16)
    traces = [p for p in tree if p.endswith("-trace.csv") and any(f"data/{m}/" in p for m in MODELS)]
    print(f"[*] Downloading {len(traces)} trace files + offline jobs...")
    list(pool.map(lambda p: fetch(p, args.out), traces + OFFLINE))

    datasets = []
    for m in MODELS:
        paths = [p for p in traces if f"data/{m}/" in p]
        vols = sorted(((client_volume(os.path.join(args.out, p[len("data/"):])), p) for p in paths), reverse=True)
        total, acc = sum(v for v, _ in vols), 0.0
        for v, p in vols:
            if acc >= args.coverage * total:
                break
            acc += v
            datasets.append(p.replace("-trace.csv", "-dataset.json"))
        print(f"    {m}: {len(paths)} clients, keep token dists of {sum(m in d for d in datasets)} "
              f"(cover {acc / total:.1%} of {total:,.0f} requests)")
    print(f"[*] Downloading {len(datasets)} dataset files...")
    list(pool.map(lambda p: fetch(p, args.out), datasets))
    print("[+] Done.")


if __name__ == "__main__":
    main()
