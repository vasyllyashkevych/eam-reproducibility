"""CVSS-based security drift on the histories of five real repositories (revision of PAPER021433-1).

For every snapshot of the repository-history experiment (soft/ftc/experiment, 5 repos x 50 snapshots)
the latest release reachable from the snapshot commit is taken as the deployed version. Known
vulnerabilities of that version are fetched from OSV (PyPI ecosystem); aliases (CVE/GHSA/PYSEC) are
merged into one advisory whose publication date is the earliest one and whose score is the highest
CVSS v3 base score. The intended reference security state is "no known vulnerability in the
deployed version", so the security drift of snapshot t is the exposure

    D_sec(t) = 1 - prod_i (1 - s_i / 10),   over advisories published no later than ts(t),

and its rate of change is dD_sec(t) = D_sec(t) - D_sec(t-1). The script writes per-snapshot values and
compares them with the six code-derived drift components and the alerts of the static and EWMA
strategies already stored in the knowledge base.

    python3 security_cvss.py            # offline: frozen OSV cache, fixed evaluation date (paths.OSV_AS_OF)
    EAM_ONLINE=1 python3 security_cvss.py   # optional: fill missing cache entries from api.osv.dev (results may then differ)
"""
import json
import os
import math
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).parent
from paths import DATA, RESULTS, OSV_AS_OF
SC = DATA / "study_c"
OUT = RESULTS
CACHE = SC / "osv_cache.json"          # frozen OSV responses; never overwritten in offline mode
OFFLINE = os.environ.get("EAM_ONLINE", "0") != "1"
NOW = pd.Timestamp(OSV_AS_OF)          # fixed evaluation instant instead of the wall clock
PYPI = {"urllib3": "urllib3", "tqdm": "tqdm", "attrs": "attrs", "gunicorn": "gunicorn", "pyyaml": "PyYAML"}
GHSA_LEVEL = {"LOW": 3.0, "MODERATE": 5.5, "MEDIUM": 5.5, "HIGH": 7.5, "CRITICAL": 9.5}

# ---------------------------------------------------------------- CVSS v3.1 base score (FIRST specification)
W = {"AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}, "AC": {"L": 0.77, "H": 0.44},
     "UI": {"N": 0.85, "R": 0.62}, "C": {"H": 0.56, "L": 0.22, "N": 0.0}}
PR = {"U": {"N": 0.85, "L": 0.62, "H": 0.27}, "C": {"N": 0.85, "L": 0.68, "H": 0.5}}


def roundup(x):
    i = round(x * 100000)
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def cvss3(vector):
    m = dict(p.split(":") for p in vector.split("/")[1:])
    iss = 1 - (1 - W["C"][m["C"]]) * (1 - W["C"][m["I"]]) * (1 - W["C"][m["A"]])
    s = m["S"]
    impact = 6.42 * iss if s == "U" else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    expl = 8.22 * W["AV"][m["AV"]] * W["AC"][m["AC"]] * PR[s][m["PR"]] * W["UI"][m["UI"]]
    if impact <= 0:
        return 0.0
    return roundup(min(impact + expl, 10)) if s == "U" else roundup(min(1.08 * (impact + expl), 10))


# ---------------------------------------------------------------- data
_SNAP = pd.read_csv(SC / "snapshots_manifest.csv", dtype={"version_at_snapshot": str}, keep_default_na=False)
_VER = {(r, c): v for r, c, v in zip(_SNAP.repo, _SNAP.commit_hash, _SNAP.version_at_snapshot)}
_TAGS = pd.read_csv(SC / "release_tags.csv")


def version_at(repo, commit):
    """Release reachable from the snapshot commit (precomputed with `git describe --tags --abbrev=0`)."""
    return _VER[(repo, commit)]


def osv(name, version, cache):
    key = f"{name}=={version}"
    if key not in cache:
        if OFFLINE:
            raise KeyError(f"{key} missing from the frozen OSV cache; set EAM_ONLINE=1 to query api.osv.dev")
        body = json.dumps({"package": {"name": name, "ecosystem": "PyPI"}, "version": version}).encode()
        req = urllib.request.Request("https://api.osv.dev/v1/query", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            cache[key] = json.load(r).get("vulns", [])
        time.sleep(0.1)
    return cache[key]


def advisories(records):
    """Merge OSV records that are aliases of each other; earliest publication, highest score."""
    groups = []
    for r in records:
        ids = {r["id"], *r.get("aliases", [])}
        score = None
        for s in r.get("severity", []):
            if s["type"] == "CVSS_V3":
                score = max(score or 0, cvss3(s["score"]))
        if score is None:
            lvl = (r.get("database_specific") or {}).get("severity")
            score = GHSA_LEVEL.get(str(lvl).upper()) if lvl else None
        pub = pd.Timestamp(r.get("published")).tz_convert(None) if r.get("published") else None
        for g in groups:
            if g["ids"] & ids:
                g["ids"] |= ids
                g["pub"] = min(x for x in (g["pub"], pub) if x is not None) if (g["pub"] or pub) else None
                g["score"] = max(x for x in (g["score"], score) if x is not None) if (g["score"] or score) else None
                break
        else:
            groups.append({"ids": ids, "pub": pub, "score": score})
    for g in groups:
        g["cve"] = sorted(i for i in g["ids"] if i.startswith("CVE-"))[:1] or sorted(g["ids"])[:1]
        g["score"] = g["score"] if g["score"] is not None else 5.5   # unscored advisory -> MODERATE
    return groups


def exposure(scores):
    return 1 - float(np.prod([1 - s / 10 for s in scores])) if scores else 0.0


def releases(repo):
    """All release tags with dates, oldest first (pre-releases excluded)."""
    rel = []
    for tag, ts in _TAGS[_TAGS.repo == repo][["tag", "creatordate_unix"]].itertuples(index=False):
        ver = tag[1:] if tag.startswith("v") else tag
        if any(x in ver.lower() for x in ("rc", "a", "b", "dev", "retracted")) and not ver.replace(".", "").isdigit():
            continue
        rel.append((ver, pd.Timestamp(int(ts), unit="s")))
    return rel


def exposure_windows(cache):
    """Per advisory: days between public disclosure and the first release not affected by it, measured on the
    latest-release track (the newest release available on each day). Zero when the fix shipped before disclosure."""
    rows = []
    for repo, name in PYPI.items():
        rel = releases(repo)
        affected = {v: {a["cve"][0] for a in advisories(osv(name, v, cache))} for v, _ in rel}
        ids = set().union(*affected.values()) if affected else set()
        pubs = {}
        for v, _ in rel:
            for a in advisories(osv(name, v, cache)):
                pubs[a["cve"][0]] = (a["pub"], a["score"])
        for cve in sorted(ids):
            pub, score = pubs[cve]
            if pub is None:
                continue
            latest = [v for v, d in rel if d <= pub]
            if not latest or cve not in affected[latest[-1]]:
                rows.append(dict(repo=repo, advisory=cve, published=pub, cvss=score, window_days=0, fixed_in=latest[-1] if latest else ""))
                continue
            fix = next(((v, d) for v, d in rel if d > pub and cve not in affected[v]), None)
            end = fix[1] if fix else NOW
            rows.append(dict(repo=repo, advisory=cve, published=pub, cvss=score,
                             window_days=int((end - pub).days), fixed_in=fix[0] if fix else "unfixed"))
    return pd.DataFrame(rows)


def pinned_deployments(cache, horizons=(365, 730, 1825)):
    """A deployment that installs release v on its release date and never upgrades: its code, configuration and
    dependencies do not change, yet D_sec grows as advisories against v are disclosed (environment-driven drift)."""
    rows = []
    for repo, name in PYPI.items():
        for v, d in releases(repo):
            adv = [a for a in advisories(osv(name, v, cache)) if a["pub"] is not None]
            row = dict(repo=repo, version=v, released=d.date(), n_advisories=len(adv),
                       known_at_release=sum(a["pub"] <= d for a in adv),
                       days_to_first=min(((a["pub"] - d).days for a in adv if a["pub"] > d), default=None))
            for h in horizons:
                t = d + pd.Timedelta(days=h)
                row[f"d_sec_{h}d"] = exposure([a["score"] for a in adv if a["pub"] <= t]) if t <= NOW else None
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(exist_ok=True)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    snaps = _SNAP[["repo", "seq", "commit_hash", "ts", "tag"]].sort_values(["repo", "seq"])
    drift = pd.read_csv(SC / "code_drift_snapshots.csv")
    runs = pd.read_csv(SC / "monitoring_alerts.csv")
    rows, adv_rows = [], []
    for repo, g in snaps.groupby("repo"):
        for _, s in g.iterrows():
            ver = version_at(repo, s.commit_hash)
            ts = pd.Timestamp(int(s.ts), unit="s")
            adv = advisories(osv(PYPI[repo], ver, cache)) if ver else []
            known = [a for a in adv if a["pub"] is not None and a["pub"] <= ts]
            rows.append(dict(repo=repo, seq=int(s.seq), date=ts.date(), version=ver, n_latent=len(adv),
                             n_known=len(known), d_sec_known=exposure([a["score"] for a in known]),
                             d_sec_latent=exposure([a["score"] for a in adv]),
                             max_cvss_known=max([a["score"] for a in known], default=0.0),
                             known_ids=";".join(a["cve"][0] for a in known)))
            for a in adv:
                adv_rows.append(dict(repo=repo, version=ver, advisory=a["cve"][0], published=a["pub"], cvss=a["score"]))
    S = pd.DataFrame(rows).sort_values(["repo", "seq"])
    S["dd_sec"] = S.groupby("repo").d_sec_known.diff().fillna(0.0)
    S["interval_days"] = S.groupby("repo").date.diff().apply(lambda x: x.days if pd.notna(x) else 0)
    S = S.merge(drift[["repo", "seq", "code_drift", "architecture_drift", "semantic_drift", "complexity_drift",
                       "configuration_drift", "size_drift", "idi", "has_release"]], on=["repo", "seq"], how="left")
    for strat, col in (("static", "alert_static"), ("ewma", "alert_ewma")):
        a = runs[runs.strategy.str.contains(strat, case=False)][["repo", "seq", "alert"]].rename(columns={"alert": col})
        S = S.merge(a, on=["repo", "seq"], how="left")
    S.to_csv(OUT / "security_drift_snapshots.csv", index=False)
    pd.DataFrame(adv_rows).drop_duplicates(["repo", "advisory"]).to_csv(OUT / "security_advisories.csv", index=False)

    T = S[S.seq > 0].copy()
    ev = T[T.dd_sec != 0]
    up = T[T.dd_sec > 0]
    rep = {"transitions": int(len(T)), "security_events": int(len(ev)), "exposure_increases": int(len(up)),
           "exposure_decreases": int((T.dd_sec < 0).sum()),
           "snapshots_with_known_exposure": int((S.d_sec_known > 0).sum()),
           "advisories": int(pd.DataFrame(adv_rows).drop_duplicates(["repo", "advisory"]).shape[0]) if adv_rows else 0}
    for c in ("idi", "code_drift", "configuration_drift", "semantic_drift"):
        r, p = stats.spearmanr(T[c], T.d_sec_known.abs())
        rep[f"spearman_{c}_vs_dsec"] = [round(float(r), 3), float(p)]
        r, p = stats.spearmanr(T[c], T.dd_sec.abs())
        rep[f"spearman_{c}_vs_abs_dd_sec"] = [round(float(r), 3), float(p)]
    for col in ("alert_static", "alert_ewma"):
        if col in T and len(ev):
            rep[f"{col}_recall_on_security_events"] = round(float(ev[col].fillna(0).mean()), 3)
            rep[f"{col}_rate_elsewhere"] = round(float(T[T.dd_sec == 0][col].fillna(0).mean()), 3)
    rep["security_events_without_release"] = int((ev.has_release == 0).sum()) if len(ev) else 0
    rep["exposure_increases_without_code_change"] = int((up.idi.fillna(0) < 0.05).sum())
    rep["known_exposure_days"] = int(T.loc[S.loc[T.index - 1, "d_sec_known"].values > 0, "interval_days"].sum()) if len(T) else 0
    per_repo = S.groupby("repo").agg(snapshots=("seq", "size"), versions=("version", "nunique"),
                                     advisories=("n_latent", "max"), exposed=("d_sec_known", lambda x: int((x > 0).sum())),
                                     max_exposure=("d_sec_known", "max")).reset_index()
    per_repo.to_csv(OUT / "security_drift_per_repo.csv", index=False)
    Wn = exposure_windows(cache)
    Wn.to_csv(OUT / "security_exposure_windows.csv", index=False)
    pos = Wn[Wn.window_days > 0]
    rep["advisories_with_release_track"] = int(len(Wn))
    rep["advisories_with_positive_window"] = int(len(pos))
    rep["window_days_median_positive"] = float(pos.window_days.median()) if len(pos) else 0.0
    rep["window_days_iqr_positive"] = [float(pos.window_days.quantile(.25)), float(pos.window_days.quantile(.75))] if len(pos) else []
    rep["window_cvss_weighted_days"] = round(float((pos.window_days * pos.cvss / 10).sum()), 1)
    P = pinned_deployments(cache)
    P.to_csv(OUT / "security_pinned_deployments.csv", index=False)
    rep["pinned_releases"] = int(len(P))
    rep["pinned_with_any_advisory"] = int((P.n_advisories > 0).sum())
    rep["pinned_days_to_first_median"] = float(P.days_to_first.dropna().median())
    for h in (365, 730, 1825):
        col = P[f"d_sec_{h}d"].dropna()
        rep[f"pinned_{h}d"] = {"evaluable": int(len(col)), "share_exposed": round(float((col > 0).mean()), 3),
                               "share_ge_0.7": round(float((col >= 0.7).mean()), 3), "mean": round(float(col.mean()), 3)}
    rep["pinned_by_repo_730d"] = P.groupby("repo")["d_sec_730d"].apply(lambda c: round(float((c.dropna() > 0).mean()), 3)).to_dict()
    (OUT / "security_drift_summary.json").write_text(json.dumps(rep, indent=2, default=str))
    print(per_repo.to_string(index=False))
    print(json.dumps(rep, indent=2, default=str))


if __name__ == "__main__":
    main()
