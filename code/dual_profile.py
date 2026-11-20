"""Ablation of the two drift profiles of Algorithm 1 (release-change profile and runtime profile).

Study A injects drift for state classification and Study B reconfigures probes after migration, but neither isolates
what the two profiles contribute when they act together. This script runs both decisions on the same Study A runs
(sanctioned release at t = 25 on role and goal, +0.25, W = 8) and adds a property layer:

  * 36 monitored properties, four per dimension; nine of them also depend on a second dimension (mapping PHI);
  * a property probe becomes stale when one of its dimensions changes (approved release or injected drift onset)
    after the last rebuild of that probe; a stale probe observes nothing;
  * property defects arrive at random, last L steps and are found with probability Q per step by a valid probe.

2 x 3 factorial design plus references:
  reference for alarms  - static (release counted as drift) | versioned (12);
  input of the zone (14) - runtime profile only | release profile only | both;
  full regeneration      - all probes rebuilt on any trigger;
  incomplete mapping     - dual profile, PHI without the nine secondary links.

Scenario 2 (masking hazard): an unplanned goal shift of +0.45 at t = 28, inside the transition window. The dual
profile is run with the mask only, and with CriticalCheck against the declared reference of the new release.

    python3 dual_profile.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).parent
from paths import RESULTS
OUT = RESULTS
spec = importlib.util.spec_from_file_location("cd", HERE / "controlled_drift.py")
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)
md = cd.md

N, ND, THETA, KAPPA = cd.N, cd.ND, cd.THETA, cd.KAPPA
T_REL, REL_DIMS, SHIFT, WIN = cd.RELEASE_T, cd.RELEASE_DIMS, cd.RELEASE_SHIFT, cd.TRANSITION
GOAL = 7
NP_PER_DIM = 4
SECOND = {0: 4, 1: 4, 2: 3, 3: 8, 4: 1, 5: 6, 6: 7, 7: 2, 8: 3}   # C-A, T-A, R-P, P-Q, A-T, X-S, S-G, G-R, Q-P
LAM, L, Q = 0.006, 6, 0.5                                          # defect rate per property-step, duration, detection
DEF_FROM, DEF_TO, COUPLED_X, COUPLED_H = 20, 110, 4.0, 15
SHOCK_T, SHOCK = 28, 0.45


def mapping(complete=True):
    """PHI as a list of dimension sets, one per property; the last property of each dimension has a secondary link."""
    props = []
    for d in range(ND):
        for k in range(NP_PER_DIM):
            props.append({d, SECOND[d]} if complete and k == NP_PER_DIM - 1 else {d})
    return props


PHI_TRUE = mapping(True)
NPROP = len(PHI_TRUE)


def change_events():
    """Times at which the evidence paths of a dimension change: the approved release and the injected drift onsets."""
    ev = {d: [md.ONSET[d]] for d in range(ND)}
    for d in REL_DIMS:
        ev[d] = sorted(ev[d] + [T_REL])
    return ev


EVENTS = change_events()


def defects(seed, coupled):
    rng = np.random.RandomState(seed + 1000 if not coupled else seed + 2000)
    out = []
    for p, dims in enumerate(PHI_TRUE):
        for t in range(DEF_FROM, DEF_TO + 1):
            rate = LAM
            if coupled and any(0 <= t - e < COUPLED_H for d in dims for e in EVENTS[d]):
                rate *= COUPLED_X
            if rng.rand() < rate:
                out.append((p, t, rng.rand(L)))
    return out


def indicators(obs, versioned, check=False, shock=False):
    """Runtime profile; with check, the masked critical dimension is compared with the declared reference of the new
    release (old mean + declared shift). A violation keeps the declared reference instead of re-estimation (12)."""
    d = cd.ref_indicators(obs, reference_update=versioned, release=True)
    crit_in_window = np.zeros(N, bool)
    if versioned and check:
        ref = obs[:md.REF_END]; mu, sd = ref.mean(0), ref.std(0)
        a, b = T_REL - 1, T_REL - 1 + WIN
        for i in REL_DIMS:
            if i not in cd.CRIT:
                continue
            decl = np.clip((np.abs(obs[:, i] - (mu[i] + SHIFT)) - 3 * sd[i]) / md.DELTA_CRIT, 0, 1)
            hit = decl[a:b] > KAPPA
            if hit.any():
                crit_in_window[a:b] |= hit
                d[b:, i] = decl[b:]          # release declaration violated: re-estimation is not accepted
    return d, crit_in_window


def zone_triggers(d_run, use_run, use_rel):
    """Per-step list of dimensions whose probes are rebuilt. Release profile: declared shift / DELTA_CRIT at T_REL.
    Runtime profile: rising crossing of THETA, re-armed below THETA / 2 (masked steps keep the state)."""
    trig = [set() for _ in range(N)]
    if use_rel:
        for i in REL_DIMS:
            if SHIFT / md.DELTA_CRIT > THETA:
                trig[T_REL - 1].add(("rel", i))
    if use_run:
        armed = np.ones(ND, bool)
        for t in range(N):
            for i in range(ND):
                x = d_run[t, i]
                if np.isnan(x):
                    continue
                if armed[i] and x > THETA:
                    trig[t].add(("run", i)); armed[i] = False
                elif x < THETA / 2:
                    armed[i] = True
    return trig


def probe_validity(trig, phi_sel, full=False):
    """valid[t, p]; rebuilds counted per probe. A release rebuild is part of the deployment (valid at T_REL);
    a runtime rebuild takes effect at the next step."""
    cover = np.zeros(NPROP)                    # time up to which the evidence path of a probe is up to date
    valid = np.zeros((N, NPROP), bool)
    rebuilds = 0
    for t in range(1, N + 1):
        rel = {i for k, i in trig[t - 1] if k == "rel"}
        run = {i for k, i in trig[t - 1] if k == "run"}
        def rebuild(dims_hit):
            nonlocal rebuilds
            sel = range(NPROP) if full else [p for p in range(NPROP) if phi_sel[p] & dims_hit]
            for p in sel:
                cover[p] = t; rebuilds += 1
        if rel:
            rebuild(rel)
        for p in range(NPROP):
            valid[t - 1, p] = not any(cover[p] < e <= t for d in PHI_TRUE[p] for e in EVENTS[d])
        if run:
            rebuild(run)
    return valid, rebuilds


def detect(valid, defs):
    found, delays = 0, []
    for p, t0, u in defs:
        for k in range(L):
            t = t0 + k
            if t <= N and valid[t - 1, p] and u[k] < Q:
                found += 1; delays.append(k); break
    return found / max(len(defs), 1), (np.mean(delays) if delays else np.nan), len(defs)


VARIANTS = {   # name: (versioned reference, zone from runtime profile, zone from release profile, full, complete PHI)
    "static/run":      (False, True, False, False, True),
    "static/rel":      (False, False, True, False, True),
    "static/both":     (False, True, True, False, True),
    "versioned/run":   (True, True, False, False, True),
    "versioned/rel":   (True, False, True, False, True),
    "dual (proposed)": (True, True, True, False, True),
    "full regeneration": (True, True, True, True, True),
    "dual, incomplete PHI": (True, True, True, False, False),
}


def calibrated(versioned):
    y = md.true_states()
    sc = [md.risk(cd.edi(indicators(cd.generate(s, release=True), versioned)[0])) for s in cd.TRAIN]
    return md.calibrate(sc, [y] * len(sc))


def scenario_main():
    y = md.true_states()
    th = {v: calibrated(v) for v in (False, True)}
    rows = []
    for seed in cd.TEST:
        obs = cd.generate(seed, release=True)
        du, dc = defects(seed, False), defects(seed, True)
        for name, (ver, use_run, use_rel, full, complete) in VARIANTS.items():
            d, _ = indicators(obs, ver)
            p = cd.override(md.classify(md.risk(cd.edi(d)), th[ver]), d)
            valid, nreb = probe_validity(zone_triggers(d, use_run, use_rel), mapping(complete), full)
            ru, delay, n_u = detect(valid, du)
            rc, _, n_c = detect(valid, dc)
            rows.append(dict(variant=name, seed=seed, macro_f1=md.macro_f1(y, p), false_critical=int((p[:99] == 4).sum()),
                             coverage=float(valid[DEF_FROM - 1:].mean()), recall_uniform=ru, recall_coupled=rc,
                             delay=delay, rebuilds=nreb, n_defects_uniform=n_u, n_defects_coupled=n_c))
    return pd.DataFrame(rows)


def scenario_shock():
    th = calibrated(True)
    y_dim = cd.labels()
    rows = []
    for seed in cd.TEST:
        obs = cd.generate(seed, release=True)
        obs[SHOCK_T - 1:, GOAL] = np.clip(obs[SHOCK_T - 1:, GOAL] + SHOCK, 0, 1)
        truth = y_dim[:, GOAL].copy(); truth[SHOCK_T - 1:] = True
        for name, check in (("dual, mask only", False), ("dual + CriticalCheck", True)):
            d, cw = indicators(obs, True, check=check)
            p = cd.override(md.classify(md.risk(cd.edi(d)), th), d)
            p = np.where(cw, 4, p)
            a, b = SHOCK_T - 1, T_REL - 1 + WIN
            hit = np.where(p[a:] == 4)[0]
            post = np.nan_to_num(d[b:, GOAL]) >= THETA
            rows.append(dict(variant=name, seed=seed, flagged_in_window=bool((p[a:b] == 4).any()),
                             critical_delay=int(hit[0]) if len(hit) else N - a,
                             goal_recall_after_window=float(post[truth[b:]].mean())))
    return pd.DataFrame(rows)


def compare(R, metric, ref, others):
    T = R.pivot(index="seed", columns="variant", values=metric)
    out, ps = [], []
    cols = [ref] + others
    chi, pf = stats.friedmanchisquare(*[T[c] for c in cols])
    out.append(dict(metric=metric, comparison="Friedman", stat=chi, p=pf))
    for c in others:
        diff = (T[ref] - T[c]).values
        p = stats.wilcoxon(T[ref], T[c], zero_method="zsplit").pvalue if np.abs(diff).sum() else 1.0
        a12 = float((T[ref].values[:, None] > T[c].values[None, :]).mean() + 0.5 * (T[ref].values[:, None] == T[c].values[None, :]).mean())
        lo, hi = cd.boot_ci(diff)
        ps.append(p); out.append(dict(metric=metric, comparison=f"{ref} - {c}", diff=diff.mean(), ci_low=lo, ci_high=hi, a12=a12, p=p))
    order = np.argsort(ps); adj = np.empty(len(ps)); run_max = 0
    for k, i in enumerate(order):
        run_max = max(run_max, min(1.0, (len(ps) - k) * ps[i])); adj[i] = run_max
    for k, row in enumerate(out[1:]):
        row["p_holm"] = adj[k]
    return out


def interaction(R, metric):
    """(versioned/both - versioned/run) - (static/both - static/run): how much the release profile adds under
    the versioned reference beyond what it adds under the static one."""
    T = R.pivot(index="seed", columns="variant", values=metric)
    x = ((T["dual (proposed)"] - T["versioned/run"]) - (T["static/both"] - T["static/run"])).values
    lo, hi = cd.boot_ci(x)
    p = stats.wilcoxon(x, zero_method="zsplit").pvalue if np.abs(x).sum() else 1.0
    return dict(metric=metric, comparison="interaction", diff=x.mean(), ci_low=lo, ci_high=hi, p=p)


def main():
    OUT.mkdir(exist_ok=True)
    pd.set_option("display.width", 250)
    R = scenario_main()
    R.to_csv(OUT / "dual_profile_runs.csv", index=False)
    cols = ["macro_f1", "false_critical", "coverage", "recall_uniform", "recall_coupled", "delay", "rebuilds"]
    S = R.groupby("variant", sort=False)[cols].agg(["mean", "std"]).round(3)
    S.to_csv(OUT / "dual_profile_summary.csv")
    print(S.to_string())
    print("defects per run: uniform", R.n_defects_uniform.mean(), "coupled", R.n_defects_coupled.mean())
    others = [v for v in VARIANTS if v != "dual (proposed)"]
    T = []
    for m in ("macro_f1", "false_critical", "coverage", "recall_uniform", "recall_coupled", "rebuilds"):
        T += compare(R, m, "dual (proposed)", others)
    for m in ("macro_f1", "coverage", "recall_uniform", "recall_coupled"):
        T.append(interaction(R, m))
    T = pd.DataFrame(T); T.to_csv(OUT / "dual_profile_tests.csv", index=False)
    print(T.round(4).to_string())
    K = scenario_shock(); K.to_csv(OUT / "dual_profile_shock_runs.csv", index=False)
    print(K.groupby("variant")[["flagged_in_window", "critical_delay", "goal_recall_after_window"]].agg(["mean", "std"]).round(3).to_string())
    Tk = K.pivot(index="seed", columns="variant", values="goal_recall_after_window")
    x = (Tk["dual + CriticalCheck"] - Tk["dual, mask only"]).values
    print("shock: recall diff", round(x.mean(), 3), cd.boot_ci(x), "wilcoxon p", stats.wilcoxon(x, zero_method="zsplit").pvalue)
    # control: CriticalCheck on the runs without the shock must not add critical states
    th, y, fc, f1, flags = calibrated(True), md.true_states(), [], [], 0
    for seed in cd.TEST:
        d, cw = indicators(cd.generate(seed, release=True), True, check=True)
        p = np.where(cw, 4, cd.override(md.classify(md.risk(cd.edi(d)), th), d))
        fc.append((p[:99] == 4).sum()); f1.append(md.macro_f1(y, p)); flags += cw.any()
    print("no shock, CriticalCheck: false critical", np.mean(fc), "macro-F1", round(np.mean(f1), 3), "window flags", flags)


if __name__ == "__main__":
    main()
