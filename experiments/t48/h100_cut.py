import sys
from analyze_s4 import analyze
for n in ("sens/base", "sens2/h100"):
    r, u = (analyze(f"{sys.argv[1]}/{n}/{k}", 1)[0].instance_hours for k in ("reactive", "lt_ua"))
    print(n, f"R {r.sum():.2f} U {u.sum():.2f} tong {100*(1-u.sum()/r.sum()):.2f}% L2 {100*(1-u['llama2-70b']/r['llama2-70b']):.2f}% Bl {100*(1-u['bloom-176b']/r['bloom-176b']):.2f}%")
