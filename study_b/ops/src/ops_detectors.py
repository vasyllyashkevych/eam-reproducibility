# -*- coding: utf-8 -*-
"""Етап виявлення відхилень: альтернативні детектори на реальній телеметрії стенда (підрозділ 7.7.8).

Телеметрія кожного зерна (out/telemetry/H_seed*.pkl) зберігається testbed_run.py, тому всі детектори
оцінюються на тих самих рядах, з тими самими зондами, дефектами, періодичністю й вікном пригнічення.
Статистичні сімейства зондів (кількість помилок об'єкта, сумарні помилки, латентність виклику, рядки на виклик)
оцінюються альтернативними детекторами; детерміновані перевірки (каталог, права, стан тригера,
твердження, відсутність викликів) однакові для всіх детекторів.

Детектори:
  base      — правило базової лінії стенда: max + ceil(3*sqrt(mean)), на чистій базовій лінії — будь-яка помилка;
  base2     — те саме з мінімальним приростом 1 (на чистій базовій лінії — щонайменше дві помилки у вікні);
  shewhart  — mean + 3*sigma з нижньою межею sigma;
  rewma     — самонавчальний робастний EWMA методу (додаток Б.3): медіана/MAD, поріг mu + 3*sigma, alpha = 0,3;
  cusum     — односторонній CUSUM (k = 0,5 sigma, h = 5 sigma);
  ph        — тест Пейджа–Хінклі (delta = 0,5 sigma, lambda = 5 sigma).
Поділ зерен: 1–5 — налаштувальні (вибір детектора), 6–10 — контрольні.
Вихід: out/ops_detectors.csv (зерно × варіант × детектор), out/ops_fp_sources.csv.
"""
import os, sys, glob, pickle
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testbed_run as TR                 # noqa: E402

OUT = TR.OUT
W, SUPPRESS, PERIOD = TR.W, TR.SUPPRESS, TR.PERIOD
DETECTORS = ["base", "base2", "shewhart", "rewma", "cusum", "ph"]
ERR_PROPS = ("exec_errors", "error_handling", "identifier_resolution", "refcursor_lifecycle", "privilege_context")


def ws(series, t, p):
    return sum(series[max(0, t - p + 1): t + 1])


def family(i, p, s, info):
    """Статистичне сімейство зонда або None для детермінованої перевірки."""
    if i is None:
        return "agg" if s in ("pg_log_errors", "pg_stat_database_xact") else None
    if s in ("pg_log_errors", "pg_log_notice") and p in ERR_PROPS:
        return "err"
    if s in ("pg_stat_statements", "pg_stat_user_functions", "pg_log_statement"):
        if p == "latency":
            return "lat"
        if p == "result_cardinality" and s != "pg_stat_user_functions":
            return "rpc"
    return None


def series_value(fam, H, i, s, t, p):
    if fam == "agg":
        return ws(H["err_total"], t, p)
    if fam == "err":
        return ws(H["err"].get(i, [0] * (t + 1)), t, p)
    key = "fn" if s == "pg_stat_user_functions" else "pgss"
    calls = ws(H[key + "_calls"].get(i, [0] * (t + 1)), t, p)
    if calls <= 0:
        return None
    if fam == "lat":
        return ws(H[key + "_time"].get(i, [0.0] * (t + 1)), t, p) / calls
    return ws(H["pgss_rows"].get(i, [0] * (t + 1)), t, p) / calls


def floor_sigma(fam, mu):
    return {"agg": 1.0, "err": 1.0, "lat": max(0.25 * abs(mu), 1.0), "rpc": max(0.2 * abs(mu), 0.5)}[fam]


def stat_alarms(fam, det, cal, seq):
    """cal — значення калібрування; seq — [(t, x)] оцінюваних кроків. Повертає кроки, де детектор сигналізує."""
    cal = [x for x in cal if x is not None]
    if not cal:
        return []
    mu, sd = float(np.mean(cal)), float(np.std(cal))
    out = []
    if det == "base2":                     # лише сімейство err; решта — оригінальні правила стенда
        thr = max(cal) + max(1, int(np.ceil(3 * np.sqrt(mu))) if mu > 0 else 1)
        return [t for t, x in seq if x is not None and x > thr]
    two_sided = fam == "rpc"
    s = max(sd, floor_sigma(fam, mu))
    if det == "shewhart":
        return [t for t, x in seq if x is not None and (abs(x - mu) if two_sided else x - mu) > 3 * s]
    if det == "rewma":
        med = float(np.median(cal))
        mad = float(np.median([abs(x - med) for x in cal])) * 1.4826
        m, var = med, max(mad, floor_sigma(fam, med)) ** 2
        for t, x in seq:
            if x is None:
                continue
            thr = 3 * max(np.sqrt(var), floor_sigma(fam, m))
            if (abs(x - m) if two_sided else x - m) > thr:
                out.append(t)
            nm = 0.3 * x + 0.7 * m
            var = 0.3 * (x - m) ** 2 + 0.7 * var
            m = nm
        return out
    if det == "cusum":
        gp = gn = 0.0
        for t, x in seq:
            if x is None:
                continue
            z = (x - mu) / s
            gp = max(0.0, gp + z - 0.5)
            gn = max(0.0, gn - z - 0.5) if two_sided else 0.0
            if gp > 5 or gn > 5:
                out.append(t)
                gp = gn = 0.0
        return out
    if det == "ph":
        cum, mn, n, mean = 0.0, 0.0, len(cal), mu
        cum2, mx = 0.0, 0.0
        for t, x in seq:
            if x is None:
                continue
            n += 1
            mean += (x - mean) / n
            cum += x - mean - 0.5 * s
            mn = min(mn, cum)
            cum2 += x - mean + 0.5 * s
            mx = max(mx, cum2)
            if cum - mn > 5 * s or (two_sided and mx - cum2 > 5 * s):
                out.append(t)
                cum = mn = cum2 = mx = 0.0
        return out
    raise ValueError(det)


def evaluate(D, variant, det, fp_log=None, ev_log=None):
    H, T, info, by_unit = D["H"], D["T"], D["info"], D["by_unit"]
    defects = D["defects"]
    events = [d for d in defects if d["applied"] and d["t_act"] is not None]
    alarms = []
    for (i, p, s, l, how) in D["cfg"][variant]:
        per = PERIOD[l]
        fam = family(i, p, s, info)
        if fam is None or det == "base" or (det == "base2" and fam != "err"):     # оригінальні правила стенда
            fn = TR.make_alarm_fn(None, p, s, i, info)
            base = {}
            TR.calibrate(None, p, s, i, H, per, base, info)
            hits = []
            for t in range(W, T):
                if t % per:
                    continue
                try:
                    if fn(H, t, per, base):
                        hits.append(t)
                except (KeyError, IndexError, TypeError, ZeroDivisionError):
                    pass
        else:
            cal = [series_value(fam, H, i, s, t, per) for t in range(per - 1, W)]
            seq = [(t, series_value(fam, H, i, s, t, per)) for t in range(W, T) if t % per == 0]
            hits = stat_alarms(fam, det, cal, seq)
        last = -10 ** 6
        for t in hits:
            if t - last >= SUPPRESS:
                alarms.append((t, i, p, s))
                last = t
    tp = loc = 0
    delays, used = [], set()
    for d in sorted(events, key=lambda d: d["t_act"]):
        uo = set(by_unit[d["unit"]])
        c = sorted([a for a in alarms if a[0] >= d["t0"] and (a[1] in uo or a[1] is None) and a not in used], key=lambda a: a[0])
        if c:
            used.add(c[0])
            tp += 1
            delays.append(max(0, c[0][0] - d["t_act"]))
            loc += int(c[0][1] == d["j"])
        if ev_log is not None:
            a = c[0] if c else None
            ev_log.append(dict(seed=D["seed"], variant=variant, detector=det, unit=d["unit"], j=d["j"], prop=d["prop"],
                               kind=d["kind"], t0=d["t0"], t_act=d["t_act"], detected=a is not None,
                               t_det=a[0] if a else None, by_signal=a[3] if a else None, by_prop=a[2] if a else None,
                               localized=(a is not None and a[1] == d["j"])))
    applied = [d for d in defects if d["applied"]]
    fps = [a for a in alarms if a not in used and not any(a[1] in set(by_unit[d["unit"]]) and a[0] >= d["t0"] for d in applied)]
    if fp_log is not None:
        for a in fps:
            fp_log.append(dict(seed=D["seed"], variant=variant, detector=det, signal=a[3], prop=a[2],
                               family=family(a[1], a[2], a[3], info) or "deterministic"))
    fp = len(fps)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / len(events) if events else 0.0
    return dict(seed=D["seed"], variant=variant, detector=det, events=len(events), TP=tp, FP=fp, P=P, R=R,
                F1=2 * P * R / (P + R) if P + R else 0.0, MTTD=float(np.mean(delays)) if delays else np.nan,
                LA=loc / len(events) if events else 0.0, FAR=fp / (tp + fp) if tp + fp else 0.0)


METHOD_DET = "rewma"                      # детектор методу (додаток Б.3), визначений до оцінювання
VARIANTS = os.environ.get("DET_VARIANTS", ",".join(TR.VARIANTS)).split(",")


def one_seed(f):
    D = pickle.load(open(f, "rb"))
    rows, fpl, evl = [], [], []
    for v in VARIANTS:
        for det in DETECTORS:
            rows.append(evaluate(D, v, det, fpl if v == "S3" else None, evl))
    print("seed", D["seed"], "done", flush=True)
    return rows, fpl, evl


def main():
    from multiprocessing import Pool
    files = sorted(glob.glob(os.path.join(OUT, "telemetry", "H_seed*.pkl")), key=lambda x: int(x.split("seed")[1][:-4]))
    with Pool(int(os.environ.get("DET_PROCS", 3))) as pool:
        res = pool.map(one_seed, files)
    rows = [r for x in res for r in x[0]]
    fpl = [r for x in res for r in x[1]]
    evl = [r for x in res for r in x[2]]
    R = pd.DataFrame(rows)
    R["split"] = np.where(R.seed <= 5, "dev", "test")
    R.to_csv(os.path.join(OUT, "ops_detectors.csv"), index=False)
    pd.DataFrame(fpl).to_csv(os.path.join(OUT, "ops_fp_sources.csv"), index=False)
    E = pd.DataFrame(evl)
    E.to_csv(os.path.join(OUT, "ops_events_det.csv"), index=False)
    # основні стендові результати (табл. 7.19г, рис. 7.19е) — з детектором методу; накладні витрати не залежать від детектора
    base = pd.read_csv(os.path.join(OUT, "ops_runs.csv"))[["seed", "variant", "probes", "probes_obj", "overhead_ms_step",
                                                          "workload_ms_step"]]
    R[R.detector == METHOD_DET].drop(columns=["detector", "split"]).merge(base, on=["seed", "variant"]) \
        .to_csv(os.path.join(OUT, "ops_runs_method.csv"), index=False)
    E[E.detector == METHOD_DET].drop(columns=["detector"]).to_csv(os.path.join(OUT, "ops_alarms_method.csv"), index=False)
    pd.set_option("display.width", 220)
    print(R.groupby(["variant", "detector", "split"])[["P", "R", "F1", "MTTD", "FAR"]].mean().round(3).to_string())
    F = pd.DataFrame(fpl)
    if len(F):
        print(F.groupby(["detector", "family", "signal"]).size().unstack(0).fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
