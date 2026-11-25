"""orc_full.csv (= phan_tich/orc4.py của v2.1: table(R, O=R).round(4)) và orc_lt.csv (= table(R, traces=("lt",))) cho gốc R.
Dùng (cwd = repo): python orc.py <R> <thư mục ra>"""
import sys; sys.path.insert(0, "experiments"); sys.path.insert(0, ".")
from analyze_oracle import table
R, P = sys.argv[1], sys.argv[2]
t = table(R, O=R).round(4)
t.to_csv(P + "/orc_full.csv", index=False); print(t.to_string())
l = table(R, traces=("lt",), O=R).round(4)
l.to_csv(P + "/orc_lt.csv", index=False); print(l.to_string())
