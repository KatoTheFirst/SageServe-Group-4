"""doi_chieu cho số T48 (25/11/2026). Nạp nguyên mã experiments/doi_chieu.py (mọi công thức claim giữ nguyên), chỉ đổi:
  - RES / SEN = file nháp (biến môi trường DC_RES, DC_SEN); SO_DOI_V21 bỏ qua (T48 không có bảng số đổi);
  - <phan_tich>, <gốc RAM json>, <gốc sens> = tham số như doi_chieu gốc;
  - các BOUND ghi cứng số v2.1 (vd. 14098, 10798, danh sách niw_done) → kiểm chuỗi số T48 có mặt trong nháp (THAY_CHU bên dưới).
Hai chế độ:
  viet <RESULTS gốc> <SENSITIVITY gốc> <RES ra> <SEN ra>: với mỗi claim, thay các số có giá trị tính lại (không phải None) trong đoạn chữ v2.1
       bằng giá trị T48, giữ số chữ số thập phân và kiểu dấu (−/+); số None (số bài báo, số v2, số trong nhãn) giữ nguyên. Ghi map đoạn cũ → mới
       ra <RES ra>.map.json và in các chỗ cần sửa tay (đổi dấu ở số không dấu, số có dấu chấm nghìn trong đoạn claim, BOUND sai).
  kiem: đối chiếu như doi_chieu gốc trên nháp (đoạn chữ lấy theo map), in "Đối chiếu: N số T48, K sai".
LƯU Ý: số trong nháp được sinh từ chính các giá trị này, nên phần "số" của kiem chủ yếu bắt sửa tay sai sau khi sinh; phần BOUND (thứ tự,
bằng nhau, điều kiện chữ) là kiểm độc lập trên số T48.
Dùng (cwd = repo): python doi_chieu_t48.py viet|kiem <repo> <phan_tich> <gốc RAM json> <gốc sens> [4 file nếu viet]"""
import json
import os
import re
import sys

MODE = sys.argv[1]
REPO, P, V21, SENS = sys.argv[2:6]
if MODE == "viet":
    RES_GOC, SEN_GOC, RES_RA, SEN_RA = sys.argv[6:10]
    DC_RES, DC_SEN = RES_GOC, SEN_GOC                          # claim theta_row quét dòng của file đang đọc: lúc viết là RESULTS v2.1
else:
    DC_RES, DC_SEN = os.environ["DC_RES"], os.environ["DC_SEN"]

src = open(f"{REPO}/experiments/doi_chieu.py", encoding="utf-8").read()
TACH = 'texts = {f: open(f, encoding="utf-8").read() for f in (RES, SO, SEN) if os.path.exists(f)}'
pre, post = src.split(TACH)


def sua(s, a, b):
    assert s.count(a) == 1, a
    return s.replace(a, b)


pre = sua(pre, 'RES, SO = f"{REPO}/RESULTS.md", f"{REPO}/output/SO_DOI_V21.md"', 'RES, SO = DC_RES, "<SO_DOI không dùng cho T48>"')
pre = sua(pre, 'SEN, SR = f"{REPO}/SENSITIVITY.md", SENS_ROOT', 'SEN, SR = DC_SEN, SENS_ROOT')
# BOUND ghi cứng số v2.1 → True ở đây; thay bằng kiểm chuỗi (THAY_CHU) sau khi nạp
for a in ['ML[2] == 14098 and ML[1] == 11340', 'MN[5] == [8, 9, 10, 11, 14] and MN[2] == 108278 and MN[1] == 117095',
          'CT["lt_u"] == 18794 and CT["lt_u"] - CT["reactive"] == ML[2]', 'all(BD[r][0] == 10798 for r in LT)',
          '[v("niw1", r, "niw_done", m) for m in (B, L2) for r in ["reactive"] + LT] == [301784, 131012, 262504, 255204, 349937, 305193, 346838, 344820]',
          'MW[2] == 40317 and MW[1] == 35614']:
    pre = sua(pre, a, "True")
sys.argv = ["doi_chieu.py", REPO, P, V21, SENS]
g = {"DC_RES": DC_RES, "DC_SEN": DC_SEN, "__name__": "doi_chieu_t48"}
exec(compile(pre, "doi_chieu.py", "exec"), g)
CLAIMS = g["CLAIMS"] + g["CLAIMS_B"]
ML, MN, CT, BD, MW, v, B, L2, LT = (g[k] for k in ("ML", "MN", "CT", "BD", "MW", "v", "B", "L2", "LT"))


def nghin(x):                                                     # 18794 -> "18.794" (kiểu RESULTS)
    return f"{int(x):,}".replace(",", ".")


# (đoạn v2.1 có số dấu chấm nghìn mà doi_chieu không tách được, đoạn T48 tương ứng); kiem: đoạn T48 phải có trong nháp
THAY_CHU = [
    ("+14.098 trên ròng +11.340", f"+{nghin(ML[2])} trên ròng +{nghin(ML[1])}", CT["lt_u"] - CT["reactive"] == ML[2]),
    ("+108.278 / +117.095", f"+{nghin(MN[2])} / +{nghin(MN[1])}", True),
    ("LT-U ARIMA 18.794)", f"LT-U ARIMA {nghin(CT['lt_u'])})", True),
    ("+40.317 trên ròng +35.614", f"+{nghin(MW[2])} trên ròng +{nghin(MW[1])}", True),
    ("Bloom 301.784 / 131.012 / 262.504 / 255.204, Llama-2 349.937 / 305.193 / 346.838 / 344.820",
     "Bloom " + " / ".join(nghin(v("niw1", r, "niw_done", B)) for r in ["reactive"] + LT) + ", Llama-2 "
     + " / ".join(nghin(v("niw1", r, "niw_done", L2)) for r in ["reactive"] + LT), True),
]
if all(BD[r][0] == BD["lt_i"][0] for r in LT):
    THAY_CHU.append(("cửa sổ 3 giờ (10.798 s)", f"cửa sổ 3 giờ ({nghin(BD['lt_i'][0])} s)", True))
else:
    print("CẦN SỬA TAY: burst 1 ba LT không cùng thời gian hồi:", {r: BD[r][0] for r in LT})

STRIP, NUM = g["STRIP"], g["NUM"]
_ct = {"g": g}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "claim_t48.py"), encoding="utf-8").read(), _ct)
OVR, EXTRA, DOI = _ct["OVR"], _ct["EXTRA"], _ct["DOI"]
_ten = {s for f, s, _ in CLAIMS}
assert all(k in _ten for k in OVR), [k[:60] for k in OVR if k not in _ten]
assert all(k in _ten for k in DOI), [k for k in DOI if k not in _ten]


def spans(snip):
    """Như nums() của doi_chieu nhưng giữ vị trí: thay phần STRIP bằng khoảng trắng cùng độ dài."""
    t = snip
    for p in STRIP:
        t = re.sub(p, lambda m: " " * len(m.group(0)), t)
    return [(m.start(), m.end(), m.group(1), m.group(2)) for m in NUM.finditer(t)]


def fmt(val, d, sgn, cu=None):
    from decimal import ROUND_HALF_UP, Decimal                    # làm tròn nửa lên như số viết tay trong RESULTS (223,25 → 223,3)
    if cu is not None and abs(cu * 4 - round(cu * 4)) < 1e-9 and d in (0, 1) and abs(val * 4 - round(val * 4)) < 1e-9 and abs(val * 10 ** d - round(val * 10 ** d)) > 1e-9:
        d = 2 if abs(val * 2 - round(val * 2)) > 1e-9 else 1      # bội 0,25 (instance-hours): hiện đúng giá trị (215,25 thay vì 215,3)
    s = str(Decimal(repr(abs(val))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)).replace(".", ",")
    zero = float(s.replace(",", ".")) == 0
    if val < 0 and not zero:
        return "−" + s, sgn == ""
    return (("+" if sgn else "") + s), False


if MODE == "viet":
    texts = {RES_GOC: open(RES_GOC, encoding="utf-8", newline="").read(), SEN_GOC: open(SEN_GOC, encoding="utf-8", newline="").read()}
    mp, tay = {}, []
    for f, snip, vals in CLAIMS:
        if f == "BOUND":
            if not vals and snip not in DOI:
                tay.append(f"BOUND SAI trên số T48: {snip}")
            continue
        if f not in texts:
            continue
        if snip not in texts[f]:
            tay.append(f"không thấy đoạn trong bản gốc: {snip[:80]}")
            continue
        sp = spans(snip)
        assert len(sp) == len(vals), (snip, len(sp), len(vals))
        new, last = [], 0
        for (a, b, sgn, n), val in zip(sp, vals):
            new.append(snip[last:a])
            if val is None:
                new.append(snip[a:b])
            else:
                d = len(n.split(",")[1]) if "," in n else 0
                s, doi = fmt(float(val), d, sgn, None if snip[b:b + 1] == "%" else float(n.replace(",", ".")))   # % không phải instance-hours
                if doi:
                    tay.append(f"đổi dấu ở số không dấu '{n}' → '{s}' trong: {snip[:90]}")
                new.append(s)
            last = b
        new.append(snip[last:])
        ns = "".join(new)
        if re.search(r"\b\d{1,3}(?:\.\d{3})+\b", snip):
            tay.append(f"đoạn claim có số dấu chấm nghìn (doi_chieu không tách): {snip[:90]}")
        if snip in OVR and OVR[snip][0]:                           # câu chữ viết lại (claim_t48.OVR)
            ns = OVR[snip][0]
        mp[snip] = ns
        texts[f] = texts[f].replace(snip, ns)
    for a, b, ok in THAY_CHU:
        for f in texts:
            texts[f] = texts[f].replace(a, b)
        for k in mp:                                               # đoạn claim chứa số nghìn: map cũng phải mang số T48
            mp[k] = mp[k].replace(a, b)
        if not ok:
            tay.append(f"điều kiện kèm THAY_CHU sai: {a}")
    open(RES_RA, "w", encoding="utf-8", newline="").write(texts[RES_GOC])
    open(SEN_RA, "w", encoding="utf-8", newline="").write(texts[SEN_GOC])
    json.dump(mp, open(RES_RA + ".map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"đã thay {len(mp)} đoạn claim; {len(THAY_CHU)} đoạn chữ số nghìn")
    print("CẦN XEM TAY:" if tay else "không có chỗ cần xem tay")
    for x in tay:
        print(" -", x)
else:
    mp = json.load(open(os.environ.get("DC_MAP", DC_RES + ".map.json"), encoding="utf-8"))
    texts = {f: open(f, encoding="utf-8").read() for f in (DC_RES, DC_SEN)}
    CL = []
    for f, s, vals in CLAIMS:
        if s in OVR:
            CL.append((f, OVR[s][0] or mp[s], OVR[s][1](list(vals))))
        else:
            CL.append((f, mp.get(s, s), vals))
    CL += EXTRA + [("BOUND", f"chữ số T48 có trong văn bản: '{b}'", ok and any(b in t for t in texts.values())) for a, b, ok in THAY_CHU]
    nums = g["nums"]
    a_so, a_loi, b_doi, c_mo_ta, bo_qua = 0, [], [], [], 0
    for f, snip, vals in CL:
        if f == "BOUND":
            if snip in DOI:
                b_doi.append((snip, vals))
            elif snip.startswith("[mô tả T48]"):
                c_mo_ta.append((snip, vals))
            else:
                a_so += 1
                if not vals:
                    a_loi.append(("BOUND", snip, "điều kiện SAI"))
            continue
        if f not in texts:
            bo_qua += 1
            continue
        if snip not in texts[f]:
            a_loi.append((f, snip[:90], "KHÔNG TÌM THẤY đoạn chữ")); continue
        ns = nums(snip)
        if len(ns) != len(vals):
            a_loi.append((f, snip[:90], f"tách được {len(ns)} số nhưng có {len(vals)} giá trị")); continue
        for (txt, shown, d), val in zip(ns, vals):
            if val is None:
                continue
            a_so += 1
            if abs(shown - val) > 0.5 * 10 ** -d + 1e-6:
                a_loi.append((f.split("/")[-1], snip[:90], f"'{txt}' nhưng tính lại = {val:.4f}"))
    print(f"(a) LỖI SỐ: {a_so} số và điều kiện kiểm, {len(a_loi)} sai" + (f"; bỏ qua {bo_qua} claim của SO_DOI_V21 (T48 không có bảng số đổi)" if bo_qua else ""))
    for x in a_loi:
        print("    -", " | ".join(x))
    print(f"(b) KẾT QUẢ THAY ĐỔI SO VỚI v2.1: {len(b_doi)} điều kiện của doi_chieu v2.1 (giữ nguyên), giá trị trên T48:")
    for snip, val in b_doi:
        print(f"    - {'ĐÚNG' if val else 'SAI '} | {snip}")
    print(f"(c) BOUND MÔ TẢ T48 (không dùng để chấm): {len(c_mo_ta)}")
    for snip, val in c_mo_ta:
        print(f"    - {'ĐÚNG' if val else 'SAI '} | {snip}")
    ok = not a_loi and len(b_doi) == len(DOI) == 7 and not any(v for _, v in b_doi) and all(v for _, v in c_mo_ta)
    print("KẾT LUẬN:", "ĐẠT (a = 0 lỗi; b đúng 7 điều kiện, đều SAI trên T48; c đều đúng)" if ok else "KHÔNG ĐẠT")
    sys.exit(0 if ok else 1)
