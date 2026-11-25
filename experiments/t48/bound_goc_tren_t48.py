"""Chỉ đọc: chạy NGUYÊN VĂN phần claim của experiments/doi_chieu.py (không vá) trên phan_tich T48, in giá trị mọi BOUND.
Dùng (cwd = repo): python bound_goc_tren_t48.py <phan_tich> <gốc RAM json> <gốc sens>"""
import sys
import os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
src = open(f"{REPO}/experiments/doi_chieu.py", encoding="utf-8").read()
pre = src.split('texts = {f: open(f, encoding="utf-8").read() for f in (RES, SO, SEN) if os.path.exists(f)}')[0]
sys.argv = ["doi_chieu.py", REPO] + sys.argv[1:4]
g = {"__name__": "x"}
exec(compile(pre, "doi_chieu.py", "exec"), g)
for f, s, v in g["CLAIMS"] + g["CLAIMS_B"]:
    if f == "BOUND":
        print(("ĐÚNG" if v else "SAI ") + " | " + s)
