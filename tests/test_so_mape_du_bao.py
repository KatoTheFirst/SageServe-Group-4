"""experiments/so_mape_du_bao.py: đỉnh thực theo giờ, giữ đỉnh giờ trước và ARIMA trên dữ liệu tự dựng có đáp án tính tay."""
import os
import subprocess
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_so_mape_tinh_tay(tmp_path):
    # 1 mô hình, vùng 0; giờ 0: 1 request 100 token; giờ 1: phút 60 có 300 token; giờ 2: phút 120 có 200 token (giờ trọn cuối = 2)
    tr = pd.DataFrame({"model_type": ["m"] * 4, "workload_type": ["prod"] * 4, "arrival_timestamp": [10, 3610, 7210, 10799],
                       "prompt_size": [100, 300, 200, 0], "regions": ["0"] * 4})
    tr.to_csv(tmp_path / "t.csv", index=False)
    fd = tmp_path / "fc"
    fd.mkdir()
    pd.DataFrame({"Time": [0, 3600, 7200], "Predicted": [50.0, 150.0, 400.0]}).to_csv(fd / "final_m_prod_1minute_region0_arima.csv", index=False)
    out = tmp_path / "kq.csv"
    subprocess.run([sys.executable, f"{ROOT}/experiments/so_mape_du_bao.py", str(tmp_path / "t.csv"), str(fd), str(out)], check=True,
                   capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    k = pd.read_csv(out).set_index("cách")
    # giờ 1: thực 300, ARIMA 150, giữ giờ trước 100; giờ 2: thực 200, ARIMA 400, giữ 300
    assert abs(k.loc["arima_v1", "MAPE (%)"] - 100 * (150 / 300 + 200 / 200) / 2) < 1e-9
    assert abs(k.loc["giu_gio_truoc", "MAPE (%)"] - 100 * (200 / 300 + 100 / 200) / 2) < 1e-9
    assert abs(k.loc["max_hai", "WAPE (%)"] - 100 * (150 + 200) / 500) < 1e-9
    assert k.loc["arima_v1", "số ô"] == 2
