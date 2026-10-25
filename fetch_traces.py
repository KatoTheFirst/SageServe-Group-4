"""
Tải các trace đã đóng băng từ GitHub Release của repo, giải nén vào traces/ và kiểm sha256 theo traces/SHA256SUMS.
Trace quá lớn để nằm trong git (> 100 MB/file) nên được đính vào Release dưới dạng .csv.gz.

Dùng: python fetch_traces.py --repo <chủ>/<tên repo> [--tag traces-v1] [--only composed_day_3regions fork_s4_westus]
"""
import argparse
import gzip
import hashlib
import os
import shutil
import urllib.request

TRACES = ["composed_day_3regions", "composed_day_3regions_12to15", "composed_day_3regions_12to15_iwn6",
          "composed_day_3regions_5models", "composed_day_3regions_burst8", "composed_day_3regions_niw1",
          "composed_day_3regions_niw9", "composed_week_3regions", "fork_s4_westus", "fork_day_3regions"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="<chủ>/<tên repo> trên GitHub")
    ap.add_argument("--tag", default="traces-v1")
    ap.add_argument("--only", nargs="+", default=TRACES)
    ap.add_argument("--base", default=None, help="nguồn khác (vd. file:///D:/SageServe_release); mặc định là Release của repo")
    a = ap.parse_args()
    expected = {}
    for line in open("traces/SHA256SUMS", encoding="utf-8"):
        digest, name = line.split()
        expected[os.path.basename(name.lstrip("*"))] = digest
    for t in a.only:
        dst = f"traces/{t}.csv"
        if os.path.exists(dst) and sha256(dst) == expected[f"{t}.csv"]:
            print(f"[=] {dst} đã có, đúng sha256")
            continue
        base = a.base or f"https://github.com/{a.repo}/releases/download/{a.tag}"
        url = f"{base}/{t}.csv.gz"
        print(f"[*] tải {url}")
        with urllib.request.urlopen(url) as r, gzip.GzipFile(fileobj=r) as g, open(dst + ".part", "wb") as f:
            shutil.copyfileobj(g, f, 1 << 20)
        got = sha256(dst + ".part")
        if got != expected[f"{t}.csv"]:
            os.remove(dst + ".part")
            raise SystemExit(f"[!] sai sha256 cho {t}: {got}")
        os.replace(dst + ".part", dst)
        print(f"[+] {dst} đúng sha256")


if __name__ == "__main__":
    main()
