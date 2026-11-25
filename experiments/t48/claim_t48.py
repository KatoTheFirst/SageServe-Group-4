"""Claim riêng của nháp T48, nạp trong doi_chieu_t48.py (chế độ kiem) với namespace g của doi_chieu gốc.
OVR: đoạn v2.1 → (đoạn T48 viết lại, hàm(vs) → giá trị): dùng khi câu chữ phải viết lại làm đổi thứ tự / số lượng số trong đoạn.
EXTRA: claim mới cho số T48 viết thêm (file, đoạn, giá trị) hoặc ("BOUND", mô tả, điều kiện).
DOI: 7 BOUND v2.1 sai trên số T48 = "kết quả thay đổi so với v2.1": giữ nguyên điều kiện gốc, in riêng (nhóm b), không thay điều kiện mới.
BOUND tên bắt đầu "[mô tả T48]": mô tả số T48 (nhóm c), không dùng để chấm."""
ob, obp, sv, v, ih, pct, tt, S6, _bc, MN, gap, H100, SM_H, BD, WS, wsp, RNG, sih = (
    g[k] for k in ("ob", "obp", "sv", "v", "ih", "pct", "tt", "S6", "_bc", "MN", "gap", "H100", "SM_H", "BD", "WS", "wsp", "RNG", "sih"))
RES, SEN, B, L2, LT, U, S = (g[k] for k in ("RES", "SEN", "B", "L2", "LT", "U", "S"))
miss = lambda p, t: S6[(p, "miss", t)]
p95s = [ob("nov2024", s, "oracle", "ttft_p95_l2") for s in LT]

OVR = {
    "Bloom 5,24 và 5,18 s (Unified xấu hơn 1,2%); Llama-2 5,16 và 6,22 s. Biên độ so bài báo 0,41x, 0,15x":
        ("Bloom 5,17 và 5,22 s (Unified tốt hơn 1,0%); Llama-2 5,31 và 7,03 s. Biên độ so bài báo 0,40x, 0,15x",
         lambda vs: vs[:2] + [-vs[2]] + vs[3:]),
    "**v2.1, đủ 18 cấu hình: 8/18 đạt theo Llama-2 (v2: 7/18).**":
        ("**T48, đủ 18 cấu hình: 9/18 đạt theo Llama-2 (v2.1: 8/18; v2: 7/18).**", lambda vs: vs[:3] + [None, None, None, vs[4]]),
    "ARIMA: Llama-2 20,25 ≥ 20,18 ≥ 19,99% (cách nhau ≤ 0,26 điểm); tổng 12,9 ≥ 8,7 ≥ 6,7%. oracle_smooth: 16,6 ≥ 15,4 ≥ 15,1%":
        ("ARIMA: Llama-2 LT-I 21,94 ≥ LT-U 20,97 ≥ LT-UA 20,90% (LT-UA và LT-U đảo chỗ, cách 0,06 điểm; cả ba cách nhau ≤ 1,03 điểm); "
         "tổng LT-I 14,3 ≥ LT-U 7,8 ≥ LT-UA 7,4%. oracle_smooth: 18,4 ≥ 16,2 ≥ 15,7%",
         lambda vs: [vs[0], vs[2], vs[1], vs[2] - vs[1], vs[3], vs[4], vs[6], vs[5]] + vs[7:]),
    "oracle: ngược, LT-UA 7,55 ≥ LT-U 4,17 ≥ LT-I −1,30% (LT-I tốn hơn Reactive). Nov: ARIMA 36,71 ≥ 33,18 ≥ 33,09% và oracle_smooth 34,54 ≥ 31,01 = 31,01% đạt; "
    "oracle ngược (LT-UA 10,85 ≥ LT-U 10,67 ≥ LT-I 10,13%)":
        ("oracle: ngược, LT-UA 8,06 ≥ LT-U 7,48 ≥ LT-I 0,90% (v2.1: LT-I tốn hơn Reactive). Nov: ARIMA 36,08 ≥ 32,14 ≥ 32,05% và oracle_smooth 33,97 ≥ 30,13 = 30,13% đạt; "
         "oracle nay cũng đạt (LT-I 9,80 ≥ LT-UA 9,62 ≥ LT-U 9,52%; v2.1 ngược)",
         lambda vs: vs[:9] + [vs[11], vs[9], vs[10]]),
    "IW-F 34,1% (EDF 34,0% thấp hơn); IW-N 3,3% (cao nhất)":
        ("IW-F 36,6% (thấp nhất); IW-N 2,3% (cao hơn FCFS 2,0% và DPA 1,2%, thấp hơn EDF 2,6%)",
         lambda vs: [miss("pf", "IW-F"), miss("pf", "IW-N"), miss("fcfs", "IW-N"), miss("dpa", "IW-N"), miss("edf", "IW-N")]),
    "Bản cắt (v2.1): chỉ hơn khi burst rơi vào 20 phút cuối giờ (vi phạm Llama-2 LT-UA 39,37% so với LT-U 59,82%; ngoài cửa sổ LT-UA trùng LT-U)":
        ("Bản cắt: chỉ hơn khi burst rơi vào 20 phút cuối giờ (vi phạm Llama-2 LT-UA 36,31% so với LT-U 59,83%); ngoài cửa sổ LT-UA không còn trùng LT-U mà kém hơn "
         "(67,31% so với 63,16%; v2.1 trùng)",
         lambda vs: vs + [_bc[("burst_out", "lt_ua")][1], _bc[("burst_out", "lt_u")][1]]),
    "Bản cắt (v2.1): khởi động A100 1200 s cho khoảng cách Reactive − LT-UA 27,8% so với 17,3% ở gốc, tức **tăng** (v2: 11,2%, không tăng). Bản cắt A100 17,3% vẫn thấp hơn H100 18,6%":
        ("Bản cắt: khởi động A100 1200 s cho khoảng cách Reactive − LT-UA 17,2% so với 14,5% ở gốc, tức **tăng** (v2: 11,2%, không tăng). "
         "Bản cắt A100 14,5% nay cao hơn H100 14,2% một chút (v2.1: 17,3% so với 18,6%)",
         lambda vs: vs + [None, None]),
    "Ngày thường: LT-U −8,0 so với LT-UA −11,1% (cách 3,1 điểm); thứ Bảy, Chủ Nhật: −20,0 so với −22,1% (cách 2,1 điểm). Vi phạm IW Chủ Nhật: LT-UA 7,65%, LT-U 6,36%":
        ("Ngày thường: LT-U −7,8 so với LT-UA −8,9% (cách 1,0 điểm); thứ Bảy, Chủ Nhật: −19,6 so với −17,8% (cách 1,8 điểm, LT-U tiết kiệm hơn). "
         "Vi phạm IW Chủ Nhật: LT-UA 8,94%, LT-U 7,30%",
         lambda vs: vs[:5] + [-vs[5]] + vs[6:]),
    "TTFT P95 Llama-2 5,21 → 1179 / 1145 / 1145 s; vi phạm SLA một tầng 60 s (D4): Reactive 0,09%, LT-U = LT-UA 30,47%":
        ("TTFT P95 Llama-2 5,24 → 1161 / 1205 / 1163 s; vi phạm SLA một tầng 60 s (D4): Reactive 0,07%, LT-U 29,52%, LT-UA 29,31%",
         lambda vs: vs + [MN[0]["lt_ua"][1]]),
    "12–13/24 giờ thiếu máy so với oracle cùng chiến lược, và các giờ này chứa 99,8–100% số request trễ hạn thêm":
        ("12/24 giờ thiếu máy so với oracle cùng chiến lược (như nhau ở cả ba chiến lược), và các giờ này chứa 99,7–100% số request trễ hạn thêm",
         lambda vs: [vs[0], vs[2], vs[3], vs[4]]),
    "LT tiết kiệm Llama-2 −20% trên trace chính":
        ("LT tiết kiệm Llama-2 −21 đến −22% trên trace chính", lambda vs: [vs[0], sv("lt", "lt_i", "ARIMA")]),
    "Bản cắt: A100 17,3%, H100 18,6% (Llama-2 15,0%, Bloom 25,5%), A100 vẫn không hơn H100. Tăng thời gian khởi động A100 lên 1200 s cho 27,8%":
        ("Bản cắt: A100 14,5%, H100 14,2% (Llama-2 10,8%, Bloom 24,5%), A100 nay hơn H100 0,4 điểm (v2.1: A100 17,3%, H100 18,6%, A100 không hơn). "
         "Tăng thời gian khởi động A100 lên 1200 s cho 17,2%",
         lambda vs: vs[:4] + [gap("base") - H100[0], None, None, None] + vs[5:]),
    "| | LT-U = LT-UA | 165,5 | 66,81% | 64,49% | 6600 s |": ("| | LT-U | 163,25 | 63,16% | 69,03% | 6600 s |", lambda vs: vs),
}
# đoạn Nov lớn: chỉ đổi "P95 −42% (3,02 s)" thành khoảng của 3 chiến lược
_nov = [k for k in g["CLAIMS_B"] if isinstance(k[1], str) and k[1].startswith("Trace Nov (Reactive 276,5 IH")][0][1]
OVR[_nov] = (None, lambda vs: vs[:25] + [min(p95s), max(p95s)] + vs[26:])           # đoạn T48 = map + sửa tay (sua_tay.py), xem NOV_SUA

DOI = {"sched sla6: DPA IW-F cao nhất, IW-N thấp nhất; PF IW-N cao nhất; EDF IW-F thấp nhất",
        "Nov oracle: TTFT P95 cả 3 chiến lược làm tròn ra −42% và 3,02 s", "Nov: SLA 60 s LT-U = LT-UA",
        "ARIMA trace chính: cả 3 làm tròn ra −20%",
        "LT-I: không khối nào dưới MT (2 trace), 0 giảm giữa giờ, phần vượt ngoài sàn chỉ ở khối đầu giờ",
        "burst: P95 LT-UA kém nhất trong 3 LT",
        "sens2: ngoài cửa sổ LT-U = LT-UA = LT-UA tắt luật giảm; trong cửa sổ LT-UA = LT-UA tắt luật giảm"}

EXTRA = [
    (RES, "Các chính sách cách nhau 1,21 điểm ở IW-F và 1,45 điểm ở IW-N",
     [max(miss(p, t) for p in ("fcfs", "edf", "pf", "dpa")) - min(miss(p, t) for p in ("fcfs", "edf", "pf", "dpa")) for t in ("IW-F", "IW-N")]),
    (RES, "dưới mục tiêu ILP chỉ 2 IH tổng (đều ở Llama-2; Nov 0)",
     [tt("lt", "lt_i", "tổng", "IH dưới MT"), tt("nov2024", "lt_i", "tổng", "IH dưới MT")]),
    ("BOUND", "[mô tả T48] LT-I oracle trace chính: IH dưới MT tổng = Llama-2", tt("lt", "lt_i", "tổng", "IH dưới MT") == tt("lt", "lt_i", "llama2-70b", "IH dưới MT")),
    (RES, "LT-UA giảm giữa giờ 414 lần và thừa 330,75 IH tổng so với nhu cầu, tổng IH cao hơn Reactive 6,8%",
     [tt("lt", "lt_ua", "tổng", "giảm giữa giờ"), tt("lt", "lt_ua", "tổng", "IH thừa"), ob("lt", "lt_ua", "oracle", "ih_total_vs_R_%")]),
    ("BOUND", "[mô tả T48] thứ tự ARIMA trace chính: LT-I > LT-U > LT-UA (Llama-2 và tổng)",
     sv("lt", "lt_i", "ARIMA") < sv("lt", "lt_u", "ARIMA") < sv("lt", "lt_ua", "ARIMA")
     and ob("lt", "lt_i", "ARIMA", "ih_total_vs_R_%") < ob("lt", "lt_u", "ARIMA", "ih_total_vs_R_%") < ob("lt", "lt_ua", "ARIMA", "ih_total_vs_R_%")),
    ("BOUND", "[mô tả T48] smooth_nov: số giờ thiếu máy như nhau ở cả ba chiến lược", len({a for a, _, _ in SM_H}) == 1),
    ("BOUND", "[mô tả T48] week: cuối tuần LT-U tiết kiệm hơn LT-UA; |cách| ngày thường < cuối tuần",
     wsp("cuối tuần", "lt_u") < wsp("cuối tuần", "lt_ua")
     and abs(wsp("ngày thường", "lt_u") - wsp("ngày thường", "lt_ua")) < abs(wsp("cuối tuần", "lt_u") - wsp("cuối tuần", "lt_ua"))),
    ("BOUND", "[mô tả T48] dòng chính: trace chính oracle_smooth 3/3, oracle 3/3, ARIMA 0/3; Nov ARIMA 0/3, oracle 3/3, oracle_smooth 0/3",
     [g["dat"](tr, fc) for tr in ("lt", "nov2024") for fc in ("oracle_smooth", "oracle", "ARIMA")] == [3, 3, 0, 0, 3, 0]),
    ("BOUND", "[mô tả T48] thứ tự LT-I ≥ LT-UA ≥ LT-U (tiết kiệm Llama-2) đúng ở 4/6 cấu hình",
     sum(-sv(tr, "lt_i", fc) >= -sv(tr, "lt_ua", fc) >= -sv(tr, "lt_u", fc) for tr in ("lt", "nov2024") for fc in ("ARIMA", "oracle", "oracle_smooth")) == 4),
    ("BOUND", "[mô tả T48] sched sla6: các chính sách cách nhau dưới 1,5 điểm (IW-F và IW-N)",
     all(max(miss(p, t) for p in ("fcfs", "edf", "pf", "dpa")) - min(miss(p, t) for p in ("fcfs", "edf", "pf", "dpa")) < 1.5 for t in ("IW-F", "IW-N"))),
    ("BOUND", "Nov: giờ LT-U vi phạm thêm nhiều nhất là 8–11, 14 (khớp chữ 'giờ 8–11, 14')", MN[5] == [8, 9, 10, 11, 14]),
    # s4load (D18) T48
    (RES, "Llama-2 4,20 s (0,12x; ngưỡng 17,25 s)", [v("s4load", U, "iw_ttft_p95", L2), v("s4load", U, "iw_ttft_p95", L2) / 34.5, None]),
    (RES, "(vi phạm IW 86%, quá tải sụp)", [v("s4load", U, "iw_sla_miss_%", B)]),
    ("BOUND", "[mô tả T48] s4load: Bloom TTFT P95 21.486 s (≥ 6,45), Llama-2 < 17,25 → D",
     round(v("s4load", U, "iw_ttft_p95", B)) == 21486 and v("s4load", U, "iw_ttft_p95", B) >= 6.45 and v("s4load", U, "iw_ttft_p95", L2) < 17.25),
    # SENSITIVITY T48
    (SEN, "| | LT-UA | 166,5 | 67,31% | 64,13% | 6600 s |", _bc[("burst_out", "lt_ua")]),
    (SEN, "LT-UA tắt luật giảm: 35,74% trong cửa sổ, 66,29% ngoài cửa sổ", [_bc[("burst_in", "lt_ua_nodown")][1], _bc[("burst_out", "lt_ua_nodown")][1]]),
    (SEN, "Yếu tố đứng thứ hai nay là mức tải (11,5 điểm; ×0,5 cho 5,4%)", [RNG["tải"], gap("r50")]),
    ("BOUND", "[mô tả T48] sens: mức tải đứng thứ hai", sorted(RNG, key=RNG.get)[-2] == "tải"),
    (SEN, "khoảng cách gốc 17,3% → 14,5%, khởi động 1200 s 27,8% → 17,2%, phút phẳng / gai 31,3% → 18,7% / 22,2%, mức tải ×0,5 19,7% → 5,4%",
     [None, gap("base"), None, None, gap("su1200"), None, gap("flat"), gap("spike"), None, gap("r50")]),
    (SEN, "Reactive gốc 200,75 → 196,00 IH, LT-UA 166,00 → 167,50", [None, sih("sens/base", "reactive"), None, sih("sens/base", "lt_ua")]),
]
