"""Smoke test cho experiments/runner.py (T38): dry-run mọi config, seed, INDEX.csv, chạy tiếp, bài dở dang, chạy lại khi chết.
Không chạy mô phỏng thật: một script giả thay run.py, ghi run.log có/không có 'completed at'."""
import csv
import glob
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import runner  # noqa: E402

CFG_DIR = os.path.join(runner.REPO, "experiments", "configs")
COUNTS = {"s4": 2, "lt": 4, "oracle": 12, "chiron": 1, "sched": 8, "nov2024": 4, "burst": 4, "h100": 4, "niw": 8, "scale5": 4,
          "week": 4, "sens": 21, "sens2": 10, "s4load": 1, "t43_dev": 5, "t43_v2_6h": 5}

FAKE = r'''
import os, sys
out = next(a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("output_dir="))
os.makedirs(out, exist_ok=True)
flag = out + ".lan"
n = int(open(flag).read()) + 1 if os.path.exists(flag) else 1
open(flag, "w").write(str(n))
die = os.environ.get("FAKE_DIE", "")
if die and out.endswith(die) and n <= int(os.environ.get("FAKE_DIE_TIMES", "1")):
    open(f"{out}/run.log", "w").write("Time: 5\n"); sys.exit(3)
open(f"{out}/run.log", "w").write("Time: 10\nTraceSimulator completed at 10\n")
open(f"{out}/sage_env.txt", "w").write("CODE_COMMIT=abc\n")
'''


def cfg_file(tmp_path, fake, extra=None):
    c = {"name": "thu", "end_time": 10, "ram_gb": 0.01, "script": str(fake), "prefix": ["p=1"],
         "runs": [{"name": "a", "overrides": ["x=1"]}, {"name": "g/b", "overrides": ["x=2"], "env": {"SAGE_T": 1}}], **(extra or {})}
    p = tmp_path / "thu.yaml"
    p.write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")
    return str(p)


@pytest.fixture
def fake(tmp_path):
    f = tmp_path / "fake_run.py"
    f.write_text(FAKE, encoding="utf-8")
    return f


def index(root):
    return list(csv.DictReader(open(f"{root}/thu/INDEX.csv", encoding="utf-8")))


@pytest.mark.parametrize("name", sorted(COUNTS))
def test_moi_config_dry_run_du_bai(name, capsys):
    cfg = yaml.safe_load(open(f"{CFG_DIR}/{name}.yaml", encoding="utf-8"))
    jobs = runner.jobs_of(cfg, "/goc", [0], None, None)
    assert len(jobs) == COUNTS[name]
    assert len({j["out"] for j in jobs}) == len(jobs)
    for j in jobs:
        assert j["out"].startswith(f"/goc/{name}/") and j["out"].endswith("/seed0")
        assert not any("{" in o for o in j["overrides"]), j["overrides"]       # mọi biến đã thay
        assert sum(o.startswith("output_dir=") for o in j["overrides"]) == 1
    assert runner.main(["--config", f"{CFG_DIR}/{name}.yaml", "--out", "/goc", "--dry-run"]) == 0
    assert capsys.readouterr().out.count("output_dir=") == COUNTS[name]


def test_seed_0_khong_them_override_seed_k_thi_them():
    cfg = yaml.safe_load(open(f"{CFG_DIR}/s4.yaml", encoding="utf-8"))
    j0, j2 = runner.jobs_of(cfg, "/g", [0, 2], 300, ["unified"])
    assert not any(o.startswith("seed=") for o in j0["overrides"]) and "seed=2" in j2["overrides"]
    assert "end_time=300" in j0["overrides"] and j2["out"] == "/g/s4/unified/seed2"


def test_chay_index_va_chay_tiep(tmp_path, fake):
    c, root = cfg_file(tmp_path, fake), str(tmp_path / "kq")
    assert runner.main(["--config", c, "--out", root, "--poll", "0.2"]) == 0
    rows = index(root)
    assert [(r["bai"], r["trang_thai"], r["code_commit"]) for r in rows] == [("a", "xong", "abc"), ("g/b", "xong", "abc")]
    assert runner.main(["--config", c, "--out", root, "--poll", "0.2"]) == 0          # chạy tiếp: bài đã xong thì bỏ qua
    assert [r["trang_thai"] for r in index(root)] == ["đã có", "đã có"]
    assert open(f"{root}/thu/a/seed0.lan").read() == "1"


def test_bai_do_dang_doi_ten_roi_chay(tmp_path, fake):
    c, root = cfg_file(tmp_path, fake), str(tmp_path / "kq")
    os.makedirs(f"{root}/thu/a/seed0")
    open(f"{root}/thu/a/seed0/run.log", "w").write("Time: 3\n")
    assert runner.main(["--config", c, "--out", root, "--poll", "0.2"]) == 0
    assert glob.glob(f"{root}/thu/a/seed0_loi_*") and index(root)[0]["trang_thai"] == "xong"


def test_chet_mot_lan_thi_chay_lai_chet_hai_lan_thi_thieu(tmp_path, fake, monkeypatch):
    c, root = cfg_file(tmp_path, fake), str(tmp_path / "kq")
    monkeypatch.setenv("FAKE_DIE", "a/seed0")
    assert runner.main(["--config", c, "--out", root, "--poll", "0.2"]) == 0
    assert index(root)[0]["trang_thai"] == "xong" and len([d for d in glob.glob(f"{root}/thu/a/seed0_loi_*") if os.path.isdir(d)]) == 1
    c2, root2 = cfg_file(tmp_path, fake), str(tmp_path / "kq2")
    monkeypatch.setenv("FAKE_DIE_TIMES", "2")
    assert runner.main(["--config", c2, "--out", root2, "--poll", "0.2"]) == 1
    assert index(root2)[0]["trang_thai"] == "THIẾU" and index(root2)[1]["trang_thai"] == "xong"


def test_env_sage_den_duoc_script(tmp_path):
    f = tmp_path / "env_run.py"
    f.write_text(FAKE + "\nopen(f'{out}/env.txt', 'w').write(os.environ.get('SAGE_T', ''))\n", encoding="utf-8")
    c, root = cfg_file(tmp_path, f), str(tmp_path / "kq")
    assert runner.main(["--config", c, "--out", root, "--poll", "0.2"]) == 0
    assert open(f"{root}/thu/g/b/seed0/env.txt").read() == "1" and open(f"{root}/thu/a/seed0/env.txt").read() == ""
