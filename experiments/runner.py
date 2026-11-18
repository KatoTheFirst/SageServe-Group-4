"""Runner thí nghiệm batch (T38): đọc một file YAML trong experiments/configs/, chạy các bài theo RAM, chạy tiếp được, ghi INDEX.csv.

Dùng:
  python experiments/runner.py --config experiments/configs/lt.yaml [--out <gốc kết quả>] [--seeds 0 1] [--only lt_ua]
                               [--end-time 300] [--max-parallel 4] [--dry-run [--ref <gốc kết quả cũ>]]
Gốc kết quả: --out, nếu không có thì biến RESULTS_ROOT, nếu không có nữa thì results/. Bài ghi vào <gốc>/<thí nghiệm>/<bài>/seed<k>/,
log ở <...>/seed<k>.out; run.py tự ghi sage_env.txt (CODE_COMMIT, biến SAGE_*). Cuối cùng: <gốc>/<thí nghiệm>/INDEX.csv.

Lập lịch (như bộ điều phối v4 + D33): ngân sách RAM = min(85% tổng, tổng − 2 GB); một bài mới chỉ khởi động khi
RAM đang dùng + phần RAM các bài đang chạy còn có thể tăng tới đỉnh ước + đỉnh ước bài mới ≤ ngân sách (đỉnh ước = ram_gb × 1,15);
số bài song song ≤ min(số nhân − 2, 8, max_parallel); RAM máy > 90% thì ngừng khởi động tới khi < 80% (không dừng bài nào);
`stagger` trong YAML: bài kế chỉ khởi động khi mọi bài đang chạy đã qua đỉnh khởi động (RSS < peak_rss_gb VÀ giờ mô phỏng ≥ peak_sim_t).
Chạy tiếp: bài đã có "completed at" trong run.log thì bỏ qua; bài dở dang đổi tên <bài>_loi_<giờ> rồi chạy; chết thì chạy lại tối đa 1 lần,
lần 2 ghi THIẾU. Seed 0 là mặc định của configs/config.yaml nên không thêm override (để so được với kết quả cũ); seed k ≠ 0 thêm `seed=k`.
--dry-run in lệnh, không chạy; kèm --ref thì so override + biến SAGE_* với bài cũ (khóa `ref` của từng bài, đường dẫn tương đối --ref)."""
import argparse
import csv
import datetime
import os
import re
import subprocess
import sys
import time

import psutil
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GB = 2 ** 30
LT4 = (("reactive", ["long_term_scaling=False"], None), ("lt_i", ["long_term_scaling=True"], "global_arbiter_short_term_scaling"),
       ("lt_u", ["long_term_scaling=True"], "global_arbiter_memory_utilization"), ("lt_ua", ["long_term_scaling=True"], "global_arbiter_ARIMA_checking"))


def arb(name, regions):
    return [f"controller.regions.{r}.arbiter={name}" for r in range(regions)] if name else []


def runs_of(cfg):
    """Mở rộng mục `lt4` (4 chiến lược như lt_runs của run.sh) thành 4 bài; các mục khác giữ nguyên."""
    out = []
    for r in cfg["runs"]:
        if "lt4" not in r:
            out.append(r)
            continue
        g = r["lt4"]
        for k, ov, a in LT4:
            if k not in g.get("strategies", [x[0] for x in LT4]):
                continue
            out.append({"name": f"{g.get('prefix', '')}{k}", "vars": g.get("vars", {}), "overrides": ov + g.get("overrides", []), "arbiter": a,
                        "ref": f"{g['ref_prefix']}{k}" if "ref_prefix" in g else None, "ram_gb": g.get("ram_gb")})
    return out


def jobs_of(cfg, root, seeds, end_time, only):
    exp_dir = f"{root}/{cfg['name']}".replace("\\", "/")
    jobs = []
    for r in runs_of(cfg):
        if only and r["name"] not in only:
            continue
        v = {k: str(x).format(exp_dir=exp_dir) for k, x in {**cfg.get("vars", {}), **(r.get("vars") or {})}.items()} | {"exp_dir": exp_dir}
        fmt = lambda xs: [x.format(**v) for x in xs]
        env = {k: str(x) for k, x in (r.get("env") or {}).items()}
        for s in seeds:
            out = f"{exp_dir}/{r['name']}/seed{s}"
            ov = (fmt(cfg.get("prefix", [])) + [f"end_time={end_time or cfg['end_time']}", f"output_dir={out}"] + fmt(cfg.get("common", []))
                  + fmt(r.get("overrides", [])) + arb(r.get("arbiter"), cfg.get("regions", 3)) + ([f"seed={s}"] if s else []))
            jobs.append({"name": r["name"], "seed": s, "out": out, "overrides": ov, "env": env, "script": r.get("script", cfg.get("script", "run.py")),
                         "ram_gb": float(r.get("ram_gb") or cfg.get("ram_gb", 2.5)), "ref": r.get("ref"), "exp_dir": exp_dir})
    return jobs


def done(out):
    try:
        with open(f"{out}/run.log", "rb") as f:
            f.seek(max(0, os.path.getsize(f"{out}/run.log") - 8192))
            return b"completed at" in f.read()
    except OSError:
        return False


def sim_t(out):
    try:
        with open(f"{out}/run.log", "rb") as f:
            f.seek(max(0, os.path.getsize(f"{out}/run.log") - 65536))
            m = re.findall(rb"\] - Time: ([0-9.]+)", f.read())
        return float(m[-1]) if m else 0.0
    except OSError:
        return 0.0


def code_commit(out):
    try:
        return next((l.split("=", 1)[1].strip() for l in open(f"{out}/sage_env.txt", encoding="utf-8") if l.startswith("CODE_COMMIT=")), "")
    except OSError:
        return ""


def rename_partial(out):
    """Bài dở dang: đổi tên thư mục và log thành <bài>_loi_<giờ>, không xóa."""
    new, k = f"{out}_loi_{datetime.datetime.now():%H%M%S}", 1
    while os.path.exists(new) or os.path.exists(f"{new}.out"):        # hai lần đổi tên trong cùng một giây
        new, k = f"{out}_loi_{datetime.datetime.now():%H%M%S}_{k}", k + 1
    for a, b in ((out, new), (f"{out}.out", f"{new}.out")):
        if os.path.exists(a):
            os.rename(a, b)
    return new


def writer_of(out):
    """Luật 7: PID đang ghi vào out (có output_dir=out trong dòng lệnh), nếu có."""
    for p in psutil.process_iter(["cmdline"]):
        if any(c.replace("\\", "/") == f"output_dir={out}" for c in (p.info["cmdline"] or [])):
            return p.pid
    return None


def check_ref(jobs, ref_root):
    """So override (bỏ output_dir, end_time giữ) và biến SAGE_* của từng bài với bài cũ <ref_root>/<ref>. Trả số bài lệch."""
    bad = 0
    for j in jobs:
        if not j["ref"]:
            print(f"  [không có ref] {j['name']}")
            continue
        ref = f"{ref_root}/{j['ref']}"
        try:
            old = [l[2:].strip() for l in open(f"{ref}/.hydra/overrides.yaml", encoding="utf-8") if l.startswith("- ")]
        except OSError:
            print(f"  [KHÔNG ĐỌC ĐƯỢC] {j['name']}: {ref}")
            bad += 1
            continue
        old_exp = ref_root + "/" + j["ref"].split("/")[0] if "/" in j["ref"] else ref_root
        norm_old = {o.replace(old_exp, "{exp}") for o in old if not o.startswith("output_dir=")}
        norm_new = {o.replace(j["exp_dir"], "{exp}") for o in j["overrides"] if not o.startswith("output_dir=")}
        try:
            env_old = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(f"{ref}/sage_env.txt", encoding="utf-8") if l.startswith("SAGE_")}
        except OSError:
            env_old = {}
        env_new = {k: v for k, v in j["env"].items() if k.startswith("SAGE_")}
        if norm_old == norm_new and env_old == env_new:
            print(f"  [TRÙNG] {j['name']} ↔ {j['ref']}")
        else:
            bad += 1
            print(f"  [LỆCH] {j['name']} ↔ {j['ref']}: chỉ bài cũ {sorted(norm_old - norm_new)}; chỉ runner {sorted(norm_new - norm_old)}; "
                  f"SAGE cũ {env_old} mới {env_new}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=os.environ.get("RESULTS_ROOT", "results"))
    ap.add_argument("--seeds", type=int, nargs="+")
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--end-time", type=int)
    ap.add_argument("--max-parallel", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--poll", type=float, default=5.0)
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    root = os.path.abspath(a.out).replace("\\", "/")
    jobs = jobs_of(cfg, root, a.seeds or cfg.get("seeds", [0]), a.end_time, a.only)
    exp_dir = f"{root}/{cfg['name']}"
    prep = [{"cmd": [x.format(py=a.python, exp_dir=exp_dir) for x in p["cmd"]], "creates": p.get("creates", "").format(exp_dir=exp_dir)}
            for p in cfg.get("prepare", [])]

    if a.dry_run:
        for p in prep:
            print(f"# chuẩn bị (nếu chưa có {p['creates'] or '-'}): {' '.join(p['cmd'])}")
        for j in jobs:
            print(" ".join([f"{k}={v}" for k, v in j["env"].items()] + [a.python, j["script"]] + j["overrides"]))
        if a.ref:
            print(f"So với {a.ref}:")
            return 1 if check_ref(jobs, a.ref.replace("\\", "/")) else 0
        return 0

    os.makedirs(exp_dir, exist_ok=True)
    log_path = f"{exp_dir}/runner_log.txt"

    def log(m):
        s = f"{datetime.datetime.now():%d/%m %H:%M:%S} {m}"
        print(s, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(s + "\n")

    for p in prep:
        if p["creates"] and os.path.exists(os.path.join(REPO, p["creates"])):
            continue
        log(f"chuẩn bị: {' '.join(p['cmd'])}")
        subprocess.run(p["cmd"], cwd=REPO, check=True)

    tot = psutil.virtual_memory().total / GB
    budget = min(0.85 * tot, tot - 2)
    max_par = max(1, min((os.cpu_count() or 4) - 2, 8, a.max_parallel, cfg.get("max_parallel", 8)))
    st = cfg.get("stagger") or {}
    index, queue = {}, []
    for j in jobs:
        key = (j["name"], j["seed"])
        if done(j["out"]):
            index[key] = {"trang_thai": "đã có", "thoi_gian_s": "", "ram_dinh_gb": "", "code_commit": code_commit(j["out"])}
            continue
        if writer_of(j["out"]):
            raise SystemExit(f"đang có tiến trình ghi vào {j['out']} (luật 7)")
        if os.path.exists(j["out"]) or os.path.exists(f"{j['out']}.out"):
            log(f"bài dở dang {j['out']} → {rename_partial(j['out'])}")
        queue.append(j)
    log(f"BẮT ĐẦU {cfg['name']}: {len(queue)} bài cần chạy, {len(index)} bài đã có; ngân sách {budget:.2f} GB, song song ≤ {max_par}")

    running, tries, gate = {}, {}, False
    while queue or running:
        for key, r in list(running.items()):                      # bài kết thúc
            if r["p"].poll() is None:
                continue
            del running[key]
            r["f"].close()                                          # Windows: phải đóng log trước khi đổi tên
            j, rc = r["job"], r["p"].returncode
            res = {"thoi_gian_s": f"{time.time() - r['t0']:.1f}", "ram_dinh_gb": f"{r['peak'] / GB:.2f}", "code_commit": code_commit(j["out"])}
            if rc == 0 and done(j["out"]):
                index[key] = {"trang_thai": "xong", **res}
                log(f"XONG {j['out']} ({res['thoi_gian_s']} s, RSS đỉnh {res['ram_dinh_gb']} GB)")
                continue
            tries[key] = tries.get(key, 0) + 1
            moi = rename_partial(j["out"])
            if tries[key] == 1:
                log(f"CHẾT {j['out']} (mã {rc}) → {moi}; chạy lại lần 2")
                queue.insert(0, j)
            else:
                index[key] = {"trang_thai": "THIẾU", **res}
                log(f"CHẾT lần 2 {j['out']} (mã {rc}) → {moi}; THIẾU")
        vm = psutil.virtual_memory()
        for r in running.values():
            try:
                r["rss"] = psutil.Process(r["p"].pid).memory_info().rss
                r["peak"] = max(r["peak"], r["rss"])
            except psutil.NoSuchProcess:
                r["rss"] = 0
        if vm.percent > 90 and not gate:
            gate = True
            log(f"CỔNG đóng: RAM máy {vm.percent:.1f}%")
        elif gate and vm.percent < 80:
            gate = False
            log(f"CỔNG mở: RAM máy {vm.percent:.1f}%")
        if queue and not gate and len(running) < max_par:
            j = queue[0]
            used = (vm.total - vm.available) / GB
            grow = sum(max(0.0, 1.15 * r["job"]["ram_gb"] - r["rss"] / GB) for r in running.values())
            need = used + grow + 1.15 * j["ram_gb"]
            past = all(r["rss"] / GB < st.get("peak_rss_gb", 1e9) and sim_t(r["job"]["out"]) >= st.get("peak_sim_t", 0)
                       and time.time() - r["t0"] >= st.get("min_gap_s", 0) for r in running.values())
            if need <= budget and past:
                queue.pop(0)
                os.makedirs(os.path.dirname(j["out"]), exist_ok=True)
                f = open(f"{j['out']}.out", "w", encoding="utf-8")
                p = subprocess.Popen([a.python, j["script"], *j["overrides"]], cwd=REPO, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     env={**os.environ, **j["env"], "PYTHONIOENCODING": "utf-8"})
                running[(j["name"], j["seed"])] = {"job": j, "p": p, "f": f, "t0": time.time(), "peak": 0, "rss": 0}
                log(f"khởi động {j['out']} (PID {p.pid}); cần {need:.2f} ≤ {budget:.2f} GB; RAM máy {vm.percent:.1f}%")
                continue
        time.sleep(a.poll)

    with open(f"{exp_dir}/INDEX.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bai", "seed", "trang_thai", "thoi_gian_s", "ram_dinh_gb", "code_commit", "thu_muc"])
        for j in jobs:
            r = index.get((j["name"], j["seed"]), {"trang_thai": "?"})
            w.writerow([j["name"], j["seed"], r["trang_thai"], r.get("thoi_gian_s", ""), r.get("ram_dinh_gb", ""), r.get("code_commit", ""), j["out"]])
    miss = [f"{n}/seed{s}" for (n, s), r in index.items() if r["trang_thai"] == "THIẾU"]
    log(f"HẾT {cfg['name']}: INDEX.csv; thiếu: {', '.join(miss) or 'không'}")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
