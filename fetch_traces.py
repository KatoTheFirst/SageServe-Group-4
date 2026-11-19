"""
Tải các trace đã đóng băng từ GitHub Release của repo, giải nén vào traces/ và kiểm sha256 theo traces/SHA256SUMS.
Trace quá lớn để nằm trong git (> 100 MB/file) nên được đính vào Release dưới dạng .csv.gz.

Dùng: python fetch_traces.py [--repo KatoTheFirst/SageServe-Group-4] [--tag traces-v1] [--only composed_day_3regions fork_s4_westus]
      python fetch_traces.py --v2 [--only composed_day_3regions_v2 ...]
--v2: tải trace v2 (Release `traces-v2`, sha256 theo traces/SHA256SUMS_v2) và dự báo v2 (forecasts_v2.tar.gz -> traces/forecasts/,
sha256 theo SHA256SUMS_forecasts_v2 của Release). File sha256 đọc bỏ ký tự CR và dấu '*' (git trên Windows checkout CRLF).
--v2 còn sinh trace chẩn đoán traces/diag_fork_s4_westus_load.csv (Table 1, D18; không có trong Release) bằng fork_trace.py +
make_trace_v2.py, khoảng 4 phút, kiểm sha256 (DIAG); đã có và đúng sha256 thì bỏ qua.
"""
import argparse
import gzip
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tarfile
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


def read_sums(path):
    """{đường dẫn tương đối: sha256} từ file dạng `sha256sum` (strip() bỏ CR/LF, bỏ '*')."""
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            digest, name = line.split(maxsplit=1)
            out[name.lstrip("*")] = digest
    return out


def download_gz(url, dst, want):
    print(f"[*] tải {url}")
    with urllib.request.urlopen(url) as r, gzip.GzipFile(fileobj=r) as g, open(dst + ".part", "wb") as f:
        shutil.copyfileobj(g, f, 1 << 20)
    got = sha256(dst + ".part")
    if got != want:
        os.remove(dst + ".part")
        raise SystemExit(f"[!] sai sha256 cho {dst}: {got}")
    os.replace(dst + ".part", dst)
    print(f"[+] {dst} đúng sha256")


# Trace chẩn đoán Table 1 (D18): §4 Unified với tải đúng §4 (1,39M IW/ngày) = lệnh của fork_s4_westus với --rate_scale 0.1139, rồi cùng lệnh v2.
# Sinh lại ngày 19/11/2026 trùng sha256 với file đã dùng cho p5/s4load.
DIAG = {"diag_fork_s4_westus_load": ("d3f522dc2f0f0f7fcef5c698e9faffc365c26d7bd09ab248ac723896ff2c2ba7",
                                      ["--rate_scale", "0.1139", "--start_day", "1", "--days", "1", "--regions", "0"],
                                      ["--niw_ratio", "7", "--clip_max", "9", "--spikes", "IW", "1.77", "1.77", "--spikes", "NIW", "2.5", "3.75"])}


def gen_diag(name):
    want, fork_args, v2_args = DIAG[name]
    dst = f"traces/{name}.csv"
    if os.path.exists(dst) and sha256(dst) == want:
        print(f"[=] {dst} đã có, đúng sha256")
        return
    print(f"[*] sinh {dst} (fork_trace.py + make_trace_v2.py, khoảng 4 phút)")
    with tempfile.TemporaryDirectory() as tmp:
        v1, out = os.path.join(tmp, "v1.csv"), os.path.join(tmp, "v2.csv")
        subprocess.run([sys.executable, "fork_trace.py", *fork_args, "--output_csv", v1], check=True)
        subprocess.run([sys.executable, "make_trace_v2.py", v1, out, *v2_args], check=True)
        if sha256(out) != want:
            raise SystemExit(f"[!] sinh {name} sai sha256: {sha256(out)}")
        shutil.move(out, dst)
    print(f"[+] {dst} đúng sha256")


def fetch_v2(a):
    base = a.base or f"https://github.com/{a.repo}/releases/download/traces-v2"
    sums = read_sums("traces/SHA256SUMS_v2")
    names = [os.path.basename(k)[:-4] for k in sums if k.startswith("traces/")]
    for t in [x for x in a.only or names if x not in DIAG]:
        dst, want = f"traces/{t}.csv", sums[f"traces/{t}.csv"]
        if os.path.exists(dst) and sha256(dst) == want:
            print(f"[=] {dst} đã có, đúng sha256")
            continue
        download_gz(f"{base}/{t}.csv.gz", dst, want)
    for k, want in sums.items():                       # θ v2 nằm sẵn trong repo: chỉ kiểm
        if k.startswith("data/") and sha256(k) != want:
            raise SystemExit(f"[!] sai sha256 cho {k}")
    urllib.request.urlretrieve(f"{base}/SHA256SUMS_forecasts_v2", "SHA256SUMS_forecasts_v2")
    fsums = read_sums("SHA256SUMS_forecasts_v2")
    bad = [k for k, v in fsums.items() if not os.path.exists(k) or sha256(k) != v]
    if bad:
        print(f"[*] {len(bad)}/{len(fsums)} file dự báo thiếu hoặc sai: tải {base}/forecasts_v2.tar.gz")
        tmp = "forecasts_v2.tar.gz.part"
        urllib.request.urlretrieve(f"{base}/forecasts_v2.tar.gz", tmp)
        with tarfile.open(tmp) as tf:
            for m in tf.getmembers():                  # chỉ nhận file thường nằm trong traces/forecasts/
                if not os.path.normpath(m.name).replace(os.sep, "/").startswith("traces/forecasts/") or m.issym() or m.islnk():
                    raise SystemExit(f"[!] tar có đường dẫn lạ: {m.name}")
            tf.extractall(".")
        os.remove(tmp)
        bad = [k for k, v in fsums.items() if not os.path.exists(k) or sha256(k) != v]
        if bad:
            raise SystemExit(f"[!] sau khi giải nén vẫn sai {len(bad)} file dự báo, ví dụ {bad[0]}")
    print(f"[+] dự báo v2: {len(fsums)} file đúng sha256")
    for t in [x for x in a.only or DIAG if x in DIAG]:
        gen_diag(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="KatoTheFirst/SageServe-Group-4", help="<chủ>/<tên repo> trên GitHub")
    ap.add_argument("--tag", default="traces-v1")
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--v2", action="store_true", help="tải trace + dự báo v2 (Release traces-v2)")
    ap.add_argument("--base", default=None, help="nguồn khác (vd. file:///<thư mục bản phát hành>); mặc định là Release của repo")
    a = ap.parse_args()
    if a.v2:
        return fetch_v2(a)
    expected = {os.path.basename(k): v for k, v in read_sums("traces/SHA256SUMS").items()}
    for t in a.only or TRACES:
        dst = f"traces/{t}.csv"
        if os.path.exists(dst) and sha256(dst) == expected[f"{t}.csv"]:
            print(f"[=] {dst} đã có, đúng sha256")
            continue
        download_gz(f"{a.base or f'https://github.com/{a.repo}/releases/download/{a.tag}'}/{t}.csv.gz", dst, expected[f"{t}.csv"])


if __name__ == "__main__":
    main()
