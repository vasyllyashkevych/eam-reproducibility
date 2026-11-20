# -*- coding: utf-8 -*-
"""Baseline comparison of ways to aggregate multidimensional drift (supporting module of Study A).

Scenario generator: nine AR(1) baseline components, an injection plan and an amplification after t = 100,
with a parameterised seed. `controlled_drift.py` imports this module (as `md`) for the generator, the
risk score, the threshold calibration and the macro-F1 helpers. Three variants are compared here:
  A - windowed partial indicators (deviation from a sliding window, as in the prototype) + PDI;
  B - reference partial indicators (deviation from the reference model) + maximum over components;
  C - reference partial indicators + PDI with interaction terms.
State thresholds are calibrated on training runs (seeds 101-110) and tested on seeds 1-40.
"""
import os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
N = 120; ND = 9; WINDOW = 8; EPS = 1e-6
NAMES = ["Configuration", "Topology", "Role", "Policy", "Architecture",
         "Context", "Semantic", "Goal", "Security"]
ONSET = [20, 35, 50, 50, 65, 80, 90, 90, 100]
LAMBDA = np.array([0.10, 0.12, 0.08, 0.10, 0.14, 0.10, 0.10, 0.10, 0.16])
MU_CORR, MU_STRUCT, MU_SEM = 0.08, 0.07, 0.05
STATES = ["Normal", "Degraded", "Vulnerable", "Anomalous", "Critical"]
REF_END = 19          # reference period: steps 1..19 (before the first drift)
DELTA_CRIT = 0.40     # tolerated deviation from the reference model that corresponds to d = 1
THETA = 0.35          # detection threshold for a partial drift

def abrupt(t, t0, a): return a if t >= t0 else 0.0
def gradual(t, t0, a, beta=0.15): return a * (1 - np.exp(-beta * (t - t0))) if t >= t0 else 0.0
def transient(t, t0, a, gamma=0.18): return a * np.exp(-gamma * (t - t0)) if t >= t0 else 0.0

def generate(seed):
    rng = np.random.RandomState(seed)
    mu = np.full(ND, 0.10); alpha = np.full(ND, 0.85); sigma = np.full(ND, 0.015)
    base = np.zeros((N, ND)); inj = np.zeros((N, ND))
    base[0] = mu + rng.normal(0, sigma, ND)
    for t in range(1, N):
        base[t] = alpha * base[t - 1] + (1 - alpha) * mu + rng.normal(0, sigma, ND)
    for i, t in enumerate(range(1, N + 1)):
        inj[i, 0] += abrupt(t, 20, 0.35); inj[i, 1] += gradual(t, 35, 0.30)
        inj[i, 2] += abrupt(t, 50, 0.20); inj[i, 3] += gradual(t, 50, 0.25)
        inj[i, 4] += gradual(t, 65, 0.35); inj[i, 5] += transient(t, 80, 0.30)
        inj[i, 6] += gradual(t, 90, 0.25); inj[i, 7] += abrupt(t, 90, 0.20)
        inj[i, 8] += abrupt(t, 100, 0.40)
        if t >= 100: inj[i, 4] += 0.05; inj[i, 3] += 0.04; inj[i, 5] += 0.03
    return np.clip(base + inj, 0, 1)

def true_states():
    t = np.arange(1, N + 1)
    return np.select([t < 20, t < 50, t < 80, t < 100], [0, 1, 2, 3], 4)

def ind_window(obs):
    d = np.zeros_like(obs)
    for i in range(ND):
        for t in range(N):
            ref = obs[:t + 1, i] if t < WINDOW else obs[t - WINDOW:t, i]
            d[t, i] = min(1.0, abs(obs[t, i] - ref.mean()) / (ref.std() + EPS) / 3.0)
    return d

def ind_reference(obs):
    ref = obs[:REF_END]
    mu, sd = ref.mean(axis=0), ref.std(axis=0)
    return np.clip((np.abs(obs - mu) - 3 * sd) / DELTA_CRIT, 0, 1)

def pdi(d):
    active = (d > THETA).sum(axis=1)
    i_corr = d.mean(axis=1) * (active >= 3)
    i_struct = (d[:, 0] + d[:, 1] + d[:, 4]) / 3
    i_sem = (d[:, 3] + d[:, 6] + d[:, 7]) / 3
    return np.clip((d * LAMBDA).sum(axis=1) + MU_CORR * i_corr + MU_STRUCT * i_struct + MU_SEM * i_sem, 0, 1)

def risk(score):
    r = np.zeros(N)
    for t in range(N):
        dp = score[t] - score[t - 1] if t else 0.0
        r[t] = np.clip(0.55 * score[t] + 0.25 * max(dp, 0) + 0.20 * score[max(0, t - 5):t + 1].mean(), 0, 1)
    return r

VARIANTS = {
    "A: windowed indicators + PDI": lambda o: (ind_window(o), "pdi"),
    "B: reference indicators + maximum": lambda o: (ind_reference(o), "max"),
    "C: reference indicators + PDI": lambda o: (ind_reference(o), "pdi"),
}

def score_of(d, agg):
    return risk(pdi(d) if agg == "pdi" else d.max(axis=1))

def calibrate(scores, y):
    """Ordinal calibration: each threshold maximises the balanced accuracy of the split {<=k} / {>k}."""
    s = np.concatenate(scores); yy = np.concatenate(y); th = []
    grid = np.linspace(0, 1, 201)
    for k in range(4):
        best, bt = -1, 0.5
        for g in grid:
            pos = yy > k; pred = s >= g
            tpr = (pred & pos).sum() / max(pos.sum(), 1); tnr = (~pred & ~pos).sum() / max((~pos).sum(), 1)
            if (tpr + tnr) / 2 > best: best, bt = (tpr + tnr) / 2, g
        th.append(bt)
    return np.maximum.accumulate(np.array(th))

def classify(s, th): return np.searchsorted(th, s, side="right")

def macro_f1(y, p):
    f = []
    for k in range(5):
        tp = ((p == k) & (y == k)).sum(); fp = ((p == k) & (y != k)).sum(); fn = ((p != k) & (y == k)).sum()
        pr = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        f.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return float(np.mean(f))

def drift_detection(d):
    out = []
    for i in range(ND):
        on = ONSET[i] - 1
        after = np.where(d[on:, i] >= THETA)[0]
        delay = int(after[0]) if len(after) else N - on
        fa = int((d[:on, i] >= THETA).sum())
        out.append((delay, fa, on))
    return out

def main():
    y = true_states()
    rows, det_rows, calib = [], [], {}
    for v, f in VARIANTS.items():
        tr = [score_of(*f(generate(s))) for s in range(101, 111)]
        th = calibrate(tr, [y] * len(tr)); calib[v] = th
        for seed in range(1, 41):
            obs = generate(seed); d, agg = f(obs); sc = score_of(d, agg); p = classify(sc, th)
            crit = np.where(p[99:] == 4)[0]
            rows.append(dict(variant=v, seed=seed, accuracy=float((p == y).mean()), macro_f1=macro_f1(y, p),
                             critical_delay=int(crit[0]) if len(crit) else N - 99,
                             false_critical=int((p[:99] == 4).sum())))
            for i, (delay, fa, on) in enumerate(drift_detection(d)):
                det_rows.append(dict(variant=v, seed=seed, drift=NAMES[i], delay=delay, false_alarms=fa,
                                     fa_rate=fa / on))
    R = pd.DataFrame(rows); Dd = pd.DataFrame(det_rows)
    R.to_csv(os.path.join(HERE, "multidrift_eval_runs.csv"), index=False)
    Dd.to_csv(os.path.join(HERE, "multidrift_detection_runs.csv"), index=False)
    pd.set_option("display.width", 250)
    print({k: np.round(v, 3).tolist() for k, v in calib.items()})
    print(R.groupby("variant")[["accuracy", "macro_f1", "critical_delay", "false_critical"]].agg(["mean", "std"]).round(3).to_string())
    print(Dd.groupby(["variant", "drift"])[["delay", "fa_rate"]].mean().round(3).unstack(0).to_string())
    print(Dd.groupby("variant")[["delay", "fa_rate"]].mean().round(3).to_string())
    # per-element tables for the figures (seed 42)
    obs = generate(42)
    out = pd.DataFrame(obs, columns=[f"S_{n}" for n in NAMES])
    for v, f in VARIANTS.items():
        d, agg = f(obs); sc = score_of(d, agg)
        out[f"score_{v[0]}"] = sc; out[f"state_{v[0]}"] = classify(sc, calib[v])
        if v[0] in "AC":
            for i, n in enumerate(NAMES): out[f"d{v[0]}_{n}"] = d[:, i]
            out[f"PDI_{v[0]}"] = pdi(d)
    out["true_state"] = y
    out.to_csv(os.path.join(HERE, "multidrift_seed42.csv"), index=False)
    pd.Series({k: list(v) for k, v in calib.items()}).to_json(os.path.join(HERE, "multidrift_thresholds.json"), force_ascii=False)

if __name__ == "__main__":
    main()
