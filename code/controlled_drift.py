"""Controlled drift injection for the revision of PAPER021433-1.

Re-uses the nine-dimensional scenario of dissertation subsection 7.4.1 (dissertation/data/r7/multidrift_eval.py,
unchanged) and adds what the reviewers asked for:

  * C0 - reference indicators (dissertation (7.3)) aggregated by the linear EDI of the article, with the
    dimension-specific critical override of Algorithm 1;
  * per-dimension step-level precision / recall / F1 of drift detection;
  * coverage ablation - the same method restricted to the evidence classical tools observe;
  * sanctioned evolution - a planned release shifts two dimensions; the method either keeps a static reference
    or masks the dimensions during a transition window and re-estimates their reference (version-dependent
    reference model);
  * evidence gaps - two dimensions unobserved: treated as zero or excluded with re-normalised weights;
  * sensitivity to noise and drift amplitude; Friedman, Wilcoxon-Holm and bootstrap intervals over 40 seeds.

    python3 controlled_drift.py
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).parent
from paths import RESULTS
OUT = RESULTS
SRC = HERE / "multidrift_eval.py"
spec = importlib.util.spec_from_file_location("md", SRC)
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

N, ND, THETA = md.N, md.ND, md.THETA
NAMES = ["configuration", "topology", "role", "policy", "architecture", "context", "semantic", "goal", "security"]
AMP = np.array([0.35, 0.30, 0.20, 0.25, 0.35, 0.30, 0.25, 0.20, 0.40])
W = md.LAMBDA / md.LAMBDA.sum()
KAPPA = 0.8                       # critical value for the semantic, goal and security override (Algorithm 1)
CRIT = [6, 7, 8]
RELEASE_T, RELEASE_DIMS, RELEASE_SHIFT, TRANSITION = 25, [2, 7], 0.25, 8
TRAIN, TEST = range(101, 111), range(1, 41)


def injected(scale=1.0):
    """Injection plan of table 7.10 (identical to md.generate), returned separately for labelling."""
    inj = np.zeros((N, ND))
    for i, t in enumerate(range(1, N + 1)):
        inj[i, 0] += md.abrupt(t, 20, 0.35 * scale); inj[i, 1] += md.gradual(t, 35, 0.30 * scale)
        inj[i, 2] += md.abrupt(t, 50, 0.20 * scale); inj[i, 3] += md.gradual(t, 50, 0.25 * scale)
        inj[i, 4] += md.gradual(t, 65, 0.35 * scale); inj[i, 5] += md.transient(t, 80, 0.30 * scale)
        inj[i, 6] += md.gradual(t, 90, 0.25 * scale); inj[i, 7] += md.abrupt(t, 90, 0.20 * scale)
        inj[i, 8] += md.abrupt(t, 100, 0.40 * scale)
        if t >= 100:
            inj[i, 4] += 0.05 * scale; inj[i, 3] += 0.04 * scale; inj[i, 5] += 0.03 * scale
    return inj


def generate(seed, sigma=0.015, scale=1.0, release=False):
    rng = np.random.RandomState(seed)
    mu, alpha = np.full(ND, 0.10), np.full(ND, 0.85)
    base = np.zeros((N, ND))
    base[0] = mu + rng.normal(0, sigma, ND)
    for t in range(1, N):
        base[t] = alpha * base[t - 1] + (1 - alpha) * mu + rng.normal(0, sigma, ND)
    obs = base + injected(scale)
    if release:                    # sanctioned change: announced, not a drift
        obs[RELEASE_T - 1:, RELEASE_DIMS] += RELEASE_SHIFT
    return np.clip(obs, 0, 1)


def labels(scale=1.0):
    """Step-level ground truth per dimension: drift present from onset; the transient one while >= 10 % of amplitude."""
    inj = injected(scale)
    y = np.zeros((N, ND), bool)
    for i, on in enumerate(md.ONSET):
        y[on - 1:, i] = True
    y[:, 5] = inj[:, 5] >= 0.1 * 0.30 * scale
    return y


def ref_indicators(obs, reference_update=False, release=False):
    """Dissertation (7.3); with reference_update the released dimensions are masked (NaN) during the transition
    window and their reference is re-estimated on it - the version-dependent reference model."""
    ref = obs[:md.REF_END]
    mu, sd = ref.mean(0), ref.std(0)
    d = np.clip((np.abs(obs - mu) - 3 * sd) / md.DELTA_CRIT, 0, 1)
    if release and reference_update:
        a, b = RELEASE_T - 1, RELEASE_T - 1 + TRANSITION
        for i in RELEASE_DIMS:
            w = obs[a:b, i]
            d[a:b, i] = np.nan
            d[b:, i] = np.clip((np.abs(obs[b:, i] - w.mean()) - 3 * max(w.std(), sd[i])) / md.DELTA_CRIT, 0, 1)
    return d


def edi(d):
    """Linear EDI over the observed dimensions; weights are re-normalised where evidence is missing (NaN)."""
    w = np.where(np.isnan(d), 0.0, W)
    return (np.nan_to_num(d) * w).sum(1) / np.maximum(w.sum(1), 1e-9)


def override(states, d):
    crit = np.nan_to_num(d[:, CRIT]).max(1) > KAPPA
    return np.where(crit, 4, states)


# ------------------------------------------------------------------ variants
def variant_scores(name, obs, release=False):
    if name == "A":                    # change detector on sliding windows + PDI (dissertation prototype)
        d = md.ind_window(obs); return md.risk(md.pdi(d)), d
    if name == "B":                    # independent per-dimension monitors, worst one wins
        d = ref_indicators(obs); return md.risk(d.max(1)), d
    if name == "C":                    # reference indicators + PDI (dissertation, nonlinear interactions)
        d = ref_indicators(obs); return md.risk(md.pdi(d)), d
    if name == "C0":                   # reference indicators + linear EDI + critical override (this article)
        d = ref_indicators(obs); return md.risk(edi(d)), d
    if name == "C0-ref":               # C0 with the version-dependent reference model
        d = ref_indicators(obs, reference_update=True, release=release); return md.risk(edi(d)), d
    if name.startswith("C0|"):         # coverage ablation: only the listed dimensions are observed
        keep = np.zeros(ND, bool); keep[[NAMES.index(x) for x in name[3:].split(",")]] = True
        d = ref_indicators(obs); d[:, ~keep] = np.nan; return md.risk(edi(d)), d
    if name == "C0-gap0":              # context and goal unobserved, treated as zero drift
        d = ref_indicators(obs); d[:, [5, 7]] = 0.0; return md.risk(edi(d)), d
    if name == "C0-gapX":              # context and goal unobserved, excluded with re-normalised weights
        d = ref_indicators(obs); d[:, [5, 7]] = np.nan; return md.risk(edi(d)), d
    raise KeyError(name)


def run(variants, sigma=0.015, scale=1.0, release=False, tag="main"):
    y_state, y_dim = md.true_states(), labels(scale)
    rows, det = [], []
    for v in variants:
        th = md.calibrate([variant_scores(v, generate(s, sigma, scale, release), release)[0] for s in TRAIN], [y_state] * len(TRAIN))
        for seed in TEST:
            sc, d = variant_scores(v, generate(seed, sigma, scale, release), release)
            p = md.classify(sc, th)
            if v.startswith("C0"):
                p = override(p, d)
            crit = np.where(p[99:] == 4)[0]
            rows.append(dict(tag=tag, variant=v, seed=seed, accuracy=float((p == y_state).mean()), macro_f1=md.macro_f1(y_state, p),
                             critical_delay=int(crit[0]) if len(crit) else N - 99, false_critical=int((p[:99] == 4).sum())))
            for i in range(ND):            # an unobserved dimension detects nothing: its drifts count as misses
                pred = np.nan_to_num(d[:, i]) >= THETA
                tp = int((pred & y_dim[:, i]).sum()); fp = int((pred & ~y_dim[:, i]).sum()); fn = int((~pred & y_dim[:, i]).sum())
                on = md.ONSET[i] - 1; hit = np.where(pred[on:])[0]
                det.append(dict(tag=tag, variant=v, seed=seed, dim=NAMES[i], tp=tp, fp=fp, fn=fn,
                                delay=int(hit[0]) if len(hit) else N - on))
    return pd.DataFrame(rows), pd.DataFrame(det)


def prf(D):
    g = D.groupby(["tag", "variant", "dim"])[["tp", "fp", "fn"]].sum()
    g["P"] = g.tp / (g.tp + g.fp).clip(lower=1); g["R"] = g.tp / (g.tp + g.fn).clip(lower=1)
    g["F1"] = (2 * g.P * g.R / (g.P + g.R)).fillna(0)
    return g.join(D.groupby(["tag", "variant", "dim"]).delay.mean()).reset_index()


def seed_macro_f1(D):
    """Per-seed macro-F1 of drift detection over all nine dimensions (for statistical tests)."""
    D = D.copy()
    D["P"] = D.tp / (D.tp + D.fp).clip(lower=1); D["R"] = D.tp / (D.tp + D.fn).clip(lower=1)
    D["F1"] = (2 * D.P * D.R / (D.P + D.R)).fillna(0)
    return D.groupby(["tag", "variant", "seed"]).F1.mean().reset_index(name="det_macro_f1")


def boot_ci(x, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x))).mean(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def tests(R, metric, ref, tag):
    T = R[R.tag == tag].pivot(index="seed", columns="variant", values=metric)
    chi, p = stats.friedmanchisquare(*[T[c] for c in T.columns]) if T.shape[1] >= 3 else (np.nan, np.nan)
    out = [dict(tag=tag, metric=metric, comparison="Friedman", stat=chi, p=p, diff=np.nan, ci_low=np.nan, ci_high=np.nan, a12=np.nan)]
    others = [c for c in T.columns if c != ref]
    ps = []
    for c in others:
        diff = T[ref] - T[c]
        p = stats.wilcoxon(T[ref], T[c], zero_method="zsplit").pvalue if diff.abs().sum() else 1.0
        a12 = float(((T[ref].values[:, None] > T[c].values[None, :]).mean() + 0.5 * (T[ref].values[:, None] == T[c].values[None, :]).mean()))
        lo, hi = boot_ci(diff.values)
        ps.append(p); out.append(dict(tag=tag, metric=metric, comparison=f"{ref} - {c}", stat=np.nan, p=p, diff=float(diff.mean()),
                                      ci_low=lo, ci_high=hi, a12=a12))
    order = np.argsort(ps); m = len(ps); adj = np.empty(m); run_max = 0
    for k, idx in enumerate(order):
        run_max = max(run_max, min(1.0, (m - k) * ps[idx])); adj[idx] = run_max
    for k, row in enumerate(out[1:]):
        row["p_holm"] = adj[k]
    return out


def weight_sensitivity(draws=100, seed=0):
    """C0 with random weight vectors (Dirichlet(1)); thresholds re-calibrated for each draw as in the protocol."""
    global W
    w0, rng, y = W.copy(), np.random.default_rng(seed), md.true_states()
    train = [ref_indicators(generate(s)) for s in TRAIN]
    test = [ref_indicators(generate(s)) for s in TEST]
    rows = []
    for k in range(draws + 1):
        W = w0 if k == 0 else rng.dirichlet(np.ones(ND))
        th = md.calibrate([md.risk(edi(d)) for d in train], [y] * len(train))
        f1 = [md.macro_f1(y, override(md.classify(md.risk(edi(d)), th), d)) for d in test]
        rows.append(dict(draw=k, weights="profile" if k == 0 else "dirichlet", macro_f1=float(np.mean(f1)),
                         **{f"w_{n}": float(x) for n, x in zip(NAMES, W)}))
    W = w0
    return pd.DataFrame(rows)


def theta_sensitivity(thetas=(0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50)):
    y = labels(); rows = []
    for th in thetas:
        tp = fp = fn = 0
        for s in TEST:
            pred = ref_indicators(generate(s)) >= th
            tp += (pred & y).sum(); fp += (pred & ~y).sum(); fn += (~pred & y).sum()
        p, r = tp / (tp + fp), tp / (tp + fn)
        rows.append(dict(theta=th, precision=p, recall=r, f1=2 * p * r / (p + r)))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(exist_ok=True)
    Ws = weight_sensitivity(); Ws.to_csv(OUT / "controlled_weight_sensitivity.csv", index=False)
    Ts = theta_sensitivity(); Ts.to_csv(OUT / "controlled_theta_sensitivity.csv", index=False)
    print("weights: profile", round(Ws.macro_f1.iloc[0], 3), "dirichlet median/IQR/min",
          Ws.macro_f1.iloc[1:].quantile([.5, .25, .75]).round(3).tolist(), round(Ws.macro_f1.iloc[1:].min(), 3))
    print(Ts.round(3).to_string(index=False))
    assert np.allclose(generate(7), md.generate(7)), "generator differs from the dissertation"
    core = ["A", "B", "C", "C0"]
    coverage = ["C0|context", "C0|configuration,topology,architecture", "C0|context,configuration,topology,architecture", "C0"]
    R1, D1 = run(core, tag="main")
    R2, D2 = run(coverage, tag="coverage")
    R3, D3 = run(["C0", "C0-ref"], release=True, tag="sanctioned")
    R4, D4 = run(["C0-gap0", "C0-gapX"], tag="evidence_gap")
    sens_R, sens_D = [], []
    for sigma in (0.015, 0.03, 0.05):
        for scale in (0.5, 1.0):
            r, d = run(["A", "B", "C", "C0"], sigma, scale, tag=f"sigma={sigma},amp={scale}")
            sens_R.append(r); sens_D.append(d)
    R = pd.concat([R1, R2, R3, R4, *sens_R]); D = pd.concat([D1, D2, D3, D4, *sens_D])
    R.to_csv(OUT / "controlled_runs.csv", index=False); D.to_csv(OUT / "controlled_detection_runs.csv", index=False)
    F = prf(D); F.to_csv(OUT / "controlled_prf_by_dim.csv", index=False)
    S = seed_macro_f1(D); R = R.merge(S, on=["tag", "variant", "seed"], how="left")
    summary = R.groupby(["tag", "variant"])[["accuracy", "macro_f1", "det_macro_f1", "critical_delay", "false_critical"]].agg(["mean", "std"]).round(3)
    summary.to_csv(OUT / "controlled_summary.csv")
    T = []
    for tag, ref in (("main", "C0"), ("coverage", "C0"), ("sanctioned", "C0-ref"), ("evidence_gap", "C0-gapX")):
        for metric in ("macro_f1", "det_macro_f1"):
            T += tests(R, metric, ref, tag)
    pd.DataFrame(T).to_csv(OUT / "controlled_tests.csv", index=False)
    pd.set_option("display.width", 250)
    print(summary.to_string())
    print(F[F.tag == "main"].pivot(index="dim", columns="variant", values=["P", "R", "F1"]).round(2).to_string())
    print(pd.DataFrame(T).round(4).to_string())
    # sanctioned evolution: false alarms on the released dimensions between the release and their true onsets
    fa = D3.assign(fp_rate=D3.fp / (D3.fp + D3.tp + D3.fn).clip(lower=1))
    print(fa[fa.dim.isin(["role", "goal"])].groupby(["variant", "dim"])[["fp", "tp", "fn"]].mean().round(2).to_string())


if __name__ == "__main__":
    main()
