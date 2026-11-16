"""Smoke test: experiments/chay_phan_tich.py (chạy lệnh, ghi đầu ra + nhật ký, trả mã lệnh) và experiments/doi_chieu.py (biên dịch, thiếu tham số thì in cách dùng)."""
import os
import py_compile
import subprocess
import sys

EXP = os.path.join(os.path.dirname(__file__), "..", "experiments")


def run(args, **env):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8", **env})


def test_chay_phan_tich_ghi_dau_ra_va_nhat_ky(tmp_path):
    out, log = tmp_path / "ra.txt", tmp_path / "nhat_ky.txt"
    r = run([f"{EXP}/chay_phan_tich.py", str(out), sys.executable, "-c", "print('xin chào')"],
            SAGE_RAM_MAX="100", SAGE_ANALYSIS_LOG=str(log))
    assert r.returncode == 0
    assert out.read_text(encoding="utf-8").strip() == "xin chào"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert "bắt đầu" in lines[0] and "ngưỡng 100%" in lines[0] and "xong mã 0" in lines[1]


def test_chay_phan_tich_tra_ma_loi(tmp_path):
    out = tmp_path / "ra.txt"
    r = run([f"{EXP}/chay_phan_tich.py", str(out), sys.executable, "-c", "import sys; sys.exit(3)"], SAGE_RAM_MAX="100")
    assert r.returncode == 3
    assert "xong mã 3" in (tmp_path / "nhat_ky_phan_tich.txt").read_text(encoding="utf-8")


def test_doi_chieu_bien_dich_va_cach_dung():
    py_compile.compile(f"{EXP}/doi_chieu.py", doraise=True)
    r = run([f"{EXP}/doi_chieu.py"])
    assert r.returncode == 2 and "Dùng:" in r.stdout
