# -*- coding: utf-8 -*-
"""Refinement of the contextual assumption `commit_in_routine` and recomputation of context drift.

The initial rule (o2p_ctx_goal.py) checked COMMIT only in a PostgreSQL function and therefore flagged a violation for
every unit whose Oracle code contains COMMIT/ROLLBACK. In PostgreSQL 17 whether transaction control is allowed
depends on the routine type, the way it is called, the security mode and the block structure. Each condition was measured
with a probe on a deployed PostgreSQL 17 (probe table), and then every Oracle routine with COMMIT/ROLLBACK was
classified by its counterpart in the reference PostgreSQL code:
  V - violated (a condition under which PostgreSQL forbids transaction control is confirmed in the code and by a probe);
  C - compatible when called with CALL outside an explicit transaction (this is how the testbed `ops/` calls procedures);
  U - undetermined (no counterpart of the routine was found in the PostgreSQL code).
A unit violates the assumption if at least one of its routines has class V. The variant that keeps the Oracle definer
rights (SECURITY DEFINER for routines without AUTHID CURRENT_USER) is given as a sensitivity analysis.
Empirical check: results of running procedures with COMMIT on the testbed (ops/out/ops_baseline_exec.csv).

Output: out/e2e_ctx_txn_probes.csv, out/e2e_ctx_txn_routines.csv, out/e2e_ctx_txn_units.csv,
       out/e2e_units_9d.csv (refined; the initial one is kept as e2e_units_9d_initial.csv),
       out/e2e_drift9_summary.csv (refined; the initial one as e2e_drift9_summary_initial.csv), out/e2e_ctx_txn_summary.csv."""
import os, re, shutil
import numpy as np, pandas as pd
try:
    import psycopg
except ImportError:          # offline mode (EAM_PG_OFFLINE=1) does not need a database driver
    psycopg = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
OPS = os.path.join(HERE, "..", "ops", "out")
DS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "study_b", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv")
DSN = os.environ.get("OPS_DSN", "host=localhost port=55432 user=postgres dbname=o2p")
I = re.IGNORECASE
TXN = re.compile(r"\b(COMMIT|ROLLBACK)\b", I)

# probes on PostgreSQL 17
PROBES = [
    # (key, description, DDL, call, run inside an explicit transaction)
    ("function", "COMMIT in a function",
     "CREATE FUNCTION ctx_txn.f() RETURNS int LANGUAGE plpgsql AS $$BEGIN COMMIT; RETURN 1; END$$",
     "SELECT ctx_txn.f()", False),
    ("procedure_call", "COMMIT in a procedure, CALL outside an explicit transaction",
     "CREATE PROCEDURE ctx_txn.p() LANGUAGE plpgsql AS $$BEGIN INSERT INTO ctx_txn.t VALUES (1); COMMIT; END$$",
     "CALL ctx_txn.p()", False),
    ("procedure_in_txn", "COMMIT in a procedure, CALL inside BEGIN ... COMMIT",
     None, "CALL ctx_txn.p()", True),
    ("security_definer", "COMMIT in a procedure with SECURITY DEFINER",
     "CREATE PROCEDURE ctx_txn.pd() LANGUAGE plpgsql SECURITY DEFINER AS $$BEGIN COMMIT; END$$",
     "CALL ctx_txn.pd()", False),
    ("set_clause", "COMMIT in a procedure with a SET clause",
     "CREATE PROCEDURE ctx_txn.ps() LANGUAGE plpgsql SET search_path = ctx_txn AS $$BEGIN COMMIT; END$$",
     "CALL ctx_txn.ps()", False),
    ("nested_call", "CALL of a procedure with COMMIT from another procedure (CALL outside a transaction)",
     "CREATE PROCEDURE ctx_txn.pn() LANGUAGE plpgsql AS $$BEGIN CALL ctx_txn.p(); END$$",
     "CALL ctx_txn.pn()", False),
    ("called_from_function", "CALL of a procedure with COMMIT from a function",
     "CREATE FUNCTION ctx_txn.fc() RETURNS int LANGUAGE plpgsql AS $$BEGIN CALL ctx_txn.p(); RETURN 1; END$$",
     "SELECT ctx_txn.fc()", False),
    ("exception_block", "COMMIT in the protected part of a block with EXCEPTION",
     "CREATE PROCEDURE ctx_txn.pe() LANGUAGE plpgsql AS $$BEGIN BEGIN COMMIT; EXCEPTION WHEN OTHERS THEN RAISE; END; END$$",
     "CALL ctx_txn.pe()", False),
    ("exception_handler", "ROLLBACK in an EXCEPTION handler",
     "CREATE PROCEDURE ctx_txn.ph() LANGUAGE plpgsql AS $$BEGIN BEGIN PERFORM 1/0; EXCEPTION WHEN OTHERS THEN ROLLBACK; END; END$$",
     "CALL ctx_txn.ph()", False),
    ("trigger", "COMMIT in a trigger function",
     "CREATE FUNCTION ctx_txn.tf() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN COMMIT; RETURN NEW; END$$;"
     "CREATE TRIGGER tg BEFORE INSERT ON ctx_txn.t2 FOR EACH ROW EXECUTE FUNCTION ctx_txn.tf()",
     "INSERT INTO ctx_txn.t2 VALUES (1)", False),
    ("do_block", "COMMIT in an anonymous DO block outside an explicit transaction",
     None, "DO $$BEGIN INSERT INTO ctx_txn.t VALUES (2); COMMIT; END$$", False),
    ("savepoint", "ROLLBACK TO SAVEPOINT in PL/pgSQL",
     "CREATE PROCEDURE ctx_txn.pv() LANGUAGE plpgsql AS $$BEGIN SAVEPOINT a; ROLLBACK TO a; END$$",
     "CALL ctx_txn.pv()", False),
]


def run_probes():
    rows = []
    with psycopg.connect(DSN, autocommit=True) as c:
        ver = c.execute("SHOW server_version").fetchone()[0]
        c.execute("DROP SCHEMA IF EXISTS ctx_txn CASCADE")
        c.execute("CREATE SCHEMA ctx_txn")
        c.execute("CREATE TABLE ctx_txn.t (x int)")
        c.execute("CREATE TABLE ctx_txn.t2 (x int)")
        for key, desc, ddl, call, in_txn in PROBES:
            created, ok, state, msg = True, False, "", ""
            if ddl:
                try:
                    for stmt in ddl.split(";CREATE"):
                        c.execute(stmt if stmt.startswith("CREATE") else "CREATE" + stmt)
                except psycopg.Error as e:
                    created, state, msg = False, e.sqlstate, str(e).splitlines()[0]
            if created:
                try:
                    if in_txn:
                        with c.transaction():
                            c.execute(call)
                    else:
                        c.execute(call)
                    ok = True
                except psycopg.Error as e:
                    state, msg = e.sqlstate, str(e).splitlines()[0]
            rows.append(dict(probe=key, description=desc, allowed=ok, created=created, sqlstate=state, message=msg,
                             pg_version=ver))
        c.execute("DROP SCHEMA ctx_txn CASCADE")
    return pd.DataFrame(rows)


# code parsing
def strip_code(code):
    code = re.sub(r"/\*.*?\*/", " ", code or "", flags=re.S)
    code = re.sub(r"--[^\n]*", " ", code)
    return re.sub(r"'(?:[^']|'')*'", "''", code)


def txn_positions(body):
    """Position of every COMMIT/ROLLBACK relative to EXCEPTION blocks: 'protected' (in the protected part of at least
    one enclosing block with a handler, i.e. an active subtransaction), 'handler' (in a handler), 'plain'."""
    toks = list(re.finditer(r"\bEND\s+(?:IF|LOOP|CASE)\b|\bEXCEPTION(?=\s+WHEN\b)|\b(?:BEGIN|END|COMMIT|ROLLBACK)\b",
                            body, I))
    stack, blocks, stmts = [], [], []
    for m in toks:
        u = " ".join(m.group(0).upper().split())
        if u == "BEGIN":
            stack.append([m.start(), None])
        elif u == "EXCEPTION" and stack:
            stack[-1][1] = m.start()
        elif u == "END" and stack:
            b = stack.pop()
            blocks.append((b[0], b[1], m.start()))
        elif u in ("COMMIT", "ROLLBACK"):
            stmts.append(m.start())
    blocks += [(b[0], b[1], len(body)) for b in stack]
    out = []
    for p in stmts:
        enc = [b for b in blocks if b[0] < p < b[2] and b[1] is not None]
        out.append("protected" if any(p < b[1] for b in enc) else ("handler" if enc else "plain"))
    return out


def block_txn(body):
    """(COMMIT/ROLLBACK in a protected part, COMMIT/ROLLBACK in a handler)."""
    pos = txn_positions(body)
    return "protected" in pos, "handler" in pos


def ora_segments(code):
    """Oracle routines with a body: [(name, type, text)]; anonymous block and trigger are handled separately."""
    c = strip_code(code)
    hdr = list(re.finditer(r"\b(PROCEDURE|FUNCTION)\s+(\"?[\w$#]+\"?(?:\.\"?[\w$#]+\"?)?)", c, I))
    segs = []
    for k, m in enumerate(hdr):
        end = hdr[k + 1].start() if k + 1 < len(hdr) else len(c)
        txt = c[m.start():end]
        if re.match(r"[^;]*?\)?\s*(RETURN\s+[\w.%]+\s*)?;", txt[len(m.group(0)):], I | re.S) and not re.search(r"\b(IS|AS)\b", txt.split(";")[0], I):
            continue                                            # declaration in a package specification
        segs.append((m.group(2).replace('"', '').split(".")[-1].lower(), m.group(1).lower(), txt))
    if re.search(r"\bCREATE\s+(OR\s+REPLACE\s+)?(EDITIONABLE\s+)?TRIGGER\b", c, I):
        segs = [("<trigger>", "trigger", c)]
    if not segs:
        segs = [("<anonymous>", "anonymous", c)]
    return segs


def pg_routines(code):
    """Routines of the reference PostgreSQL code: name -> properties."""
    c = re.sub(r"--[^\n]*", " ", code or "")
    R = {}
    for m in re.finditer(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(FUNCTION|PROCEDURE)\s+([\w.\"]+)\s*\(", c, I):
        rest = c[m.end():]
        bm = re.search(r"\bAS\s+(\$[\w]*\$)", rest, I)
        if not bm:
            continue
        tag = bm.group(1)
        e = rest.find(tag, bm.end())
        if e < 0:
            continue
        body = rest[bm.end():e]
        nxt = re.search(r";|\bCREATE\b", rest[e + len(tag):])
        header = rest[:bm.start()] + " " + rest[e + len(tag): e + len(tag) + (nxt.start() if nxt else 0)]
        name = m.group(2).replace('"', '').split(".")[-1].lower()
        R[name] = dict(kind=m.group(1).lower(), body=strip_code(body),
                       trigger=bool(re.search(r"RETURNS\s+trigger", header, I)),
                       definer=bool(re.search(r"SECURITY\s+DEFINER", header, I)),
                       set_clause=bool(re.search(r"\bSET\s+\w+\s*(=|TO\b)", header, I)))
    for k, m in enumerate(re.finditer(r"\bDO\s+(\$[\w]*\$)", c, I)):
        e = c.find(m.group(1), m.end())
        R[f"<do{k}>"] = dict(kind="do", body=strip_code(c[m.end():e if e > 0 else len(c)]), trigger=False,
                             definer=False, set_clause=False)
    for r in R.values():
        r["txn"] = bool(TXN.search(r["body"]))
    for n, r in R.items():                                      # calls within the unit
        r["callers"] = [m for m, x in R.items() if m != n and not n.startswith("<")
                        and re.search(rf"\b{re.escape(n)}\s*\(|\bCALL\s+[\w.]*\b{re.escape(n)}\b", x["body"], I)]
    return R


def match_pg(name, kind, R):
    if name in R:
        return name
    cand = [n for n in R if not n.startswith("<") and (n.endswith("_" + name) or n.endswith("__" + name))]
    if len(cand) == 1:
        return cand[0]
    if kind in ("anonymous", "trigger"):
        if kind == "anonymous" and any(n.startswith("<do") for n in R):
            return [n for n in R if n.startswith("<do")][0]
        trg = [n for n, r in R.items() if r["trigger"]]
        if kind == "trigger" and trg:
            return trg[0]
    rout = [n for n in R if not n.startswith("<")]
    if len(rout) == 1:
        return rout[0]
    return None


def classify(seg, R, probes, preserve_definer=False):
    name, kind, txt = seg
    if re.search(r"PRAGMA\s+AUTONOMOUS_TRANSACTION", txt, I):
        return "V", "autonomous_tx"
    if re.search(r"\bROLLBACK\s+TO\b", txt, I) and not probes["savepoint"]:
        return "V", "savepoint"
    m = match_pg(name, kind, R)
    if m is None:
        return "U", "no_pg_counterpart"
    r = R[m]
    if r["trigger"] or kind == "trigger":
        return "V", "trigger"
    if r["kind"] == "function":
        return "V", "function"
    if (r["definer"] or (preserve_definer and r["kind"] == "procedure")) and not probes["security_definer"]:
        return "V", "security_definer"
    if r["set_clause"] and not probes["set_clause"]:
        return "V", "set_clause"
    prot, hand = block_txn(r["body"] if r["txn"] else txt)
    if prot and not probes["exception_block"]:
        return "V", "exception_block"
    if hand and not probes["exception_handler"]:
        return "V", "exception_handler"
    seen, todo = {m}, list(r["callers"])
    while todo:                                                  # call context within the unit
        c = todo.pop()
        if c in seen:
            continue
        seen.add(c)
        if R[c]["kind"] == "function" and not probes["called_from_function"]:
            return "V", "called_from_function"
        todo += R[c]["callers"]
    return "C", "procedure_call" if r["kind"] == "procedure" else "do_block"


def main():
    if os.environ.get("EAM_PG_OFFLINE") == "1":   # probes recorded on the PostgreSQL 17.11 testbed
        P = pd.read_csv(os.path.join(HERE, "..", "..", "..", "data", "study_b", "recorded", "e2e_ctx_txn_probes.csv"), keep_default_na=False)
        P["allowed"] = P.allowed.astype(str).str.lower().isin(["true", "1"])
    else:
        P = run_probes()
    P.to_csv(os.path.join(OUT, "e2e_ctx_txn_probes.csv"), index=False)
    print(P[["probe", "allowed", "sqlstate", "message"]].to_string())
    pr = dict(zip(P.probe, P.allowed))
    assert pr["procedure_call"] and not pr["function"], "unexpected PostgreSQL behaviour"

    raw = pd.read_csv(DS)
    if not os.path.exists(os.path.join(OUT, "e2e_units_9d_initial.csv")):
        shutil.copy(os.path.join(OUT, "e2e_units_9d.csv"), os.path.join(OUT, "e2e_units_9d_initial.csv"))
        shutil.copy(os.path.join(OUT, "e2e_drift9_summary.csv"), os.path.join(OUT, "e2e_drift9_summary_initial.csv"))
    U9 = pd.read_csv(os.path.join(OUT, "e2e_units_9d_initial.csv"), keep_default_na=False)
    rr, ur = [], []
    for u in U9.itertuples():
        if "commit_in_routine" not in u.ctx_relied.split(";"):
            continue
        ora, pg = str(raw.input_db_query.iloc[u.unit] or ""), str(raw.output_db_query.iloc[u.unit] or "")
        R = pg_routines(pg)
        segs = [s for s in ora_segments(ora) if TXN.search(s[2])]
        if not segs:                                             # COMMIT only in string literals / outside routines
            segs = [("<anonymous>", "anonymous", strip_code(ora))]
        cls = {}
        for mode in ("ref", "definer"):
            cs = []
            for s in segs:
                k, why = classify(s, R, pr, preserve_definer=(mode == "definer" and not re.search(r"AUTHID\s+CURRENT_USER", s[2], I)))
                cs.append(k)
                if mode == "ref":
                    m = match_pg(s[0], s[1], R)
                    rr.append(dict(unit=u.unit, routine=s[0], ora_kind=s[1], pg_routine=m,
                                   pg_kind=R[m]["kind"] if m else "", pg_keeps_txn=R[m]["txn"] if m else None,
                                   cls=k, reason=why))
            cls[mode] = "V" if "V" in cs else ("U" if "U" in cs else "C")
        others = [a for a in u.ctx_violated.split(";") if a and a != "commit_in_routine"]
        ur.append(dict(unit=u.unit, cls=cls["ref"], cls_definer=cls["definer"], n_txn_routines=len(segs),
                       only_violation=(len(others) == 0)))
    RR, UR = pd.DataFrame(rr), pd.DataFrame(ur)
    RR.to_csv(os.path.join(OUT, "e2e_ctx_txn_routines.csv"), index=False)

    # empirical check on the testbed (ops/src/txn_validate.py): result of every COMMIT/ROLLBACK from the instrumentation
    V = pd.read_csv(os.path.join(OPS, "ops_txn_validation.csv"))
    V["name"] = V.ident.str.extract(r"\.([^.(]+)\(")[0].str.lower()
    V["e2d"] = V.caught_2d000 + V.uncaught_2d000
    G = V.groupby(["unit", "name", "kind"]).agg(calls=("ok", "size"), ok_plain=("ok_plain", "sum"),
                                                ok_handler=("ok_handler", "sum"), ok_protected=("ok_protected", "sum"),
                                                e2d=("e2d", "sum")).reset_index()
    G = G.merge(RR.drop_duplicates(["unit", "pg_routine"])[["unit", "pg_routine", "cls", "reason"]],
                left_on=["unit", "name"], right_on=["unit", "pg_routine"], how="left")
    G["reason"] = G.reason.fillna("unmatched")
    G["observed"] = np.where(G.e2d > 0, "2D000", np.where(G.ok_plain + G.ok_protected > 0, "commit_ok", "not_reached"))
    G.to_csv(os.path.join(OUT, "e2e_ctx_txn_validation.csv"), index=False)
    UR = UR.merge(G.groupby("unit").agg(exec_routines=("calls", "size"),
                                        exec_2d000=("observed", lambda s: int((s == "2D000").sum())),
                                        exec_commit_ok=("observed", lambda s: int((s == "commit_ok").sum()))).reset_index(),
                  on="unit", how="left")
    UR.to_csv(os.path.join(OUT, "e2e_ctx_txn_units.csv"), index=False)

    # recompute context drift
    viol = dict(zip(UR.unit, UR.cls))
    viol_d = dict(zip(UR.unit, UR.cls_definer))

    def recompute(rule):
        X = U9.copy()
        nv, d = [], []
        for r in X.itertuples():
            rel = [a for a in r.ctx_relied.split(";") if a]
            v = [a for a in r.ctx_violated.split(";") if a]
            if "commit_in_routine" in v and not rule(r.unit):
                v.remove("commit_in_routine")
            nv.append(";".join(v))
            d.append(len(v) / len(rel) if rel else 0.0)
        X["ctx_violated"], X["d_contextual"] = nv, d
        return X

    variants = {"initial": lambda u: True,
                "refined": lambda u: viol.get(u) == "V",
                "refined_upper": lambda u: viol.get(u) in ("V", "U"),
                "definer_preserved": lambda u: viol_d.get(u) == "V"}
    dims = ["d_configuration", "d_topological", "d_role", "d_policy", "d_architectural", "d_semantic", "d_security",
            "d_contextual", "d_goal"]
    S = []
    Xs = {}
    for k, rule in variants.items():
        X = recompute(rule)
        Xs[k] = X
        c = X[dims].corr("spearman")["d_contextual"].drop("d_contextual")
        S.append(dict(variant=k, units_pos=int((X.d_contextual > 0).sum()), share_pos=(X.d_contextual > 0).mean(),
                      mean=X.d_contextual.mean(), share_sig=(X.d_contextual > 0.10).mean(),
                      commit_violated_units=int(X.ctx_violated.str.contains("commit_in_routine").sum()),
                      max_rho_7d=c.drop("d_goal").max(), rho_goal=c["d_goal"], units_sig_any9=int((X[dims] > 0.10).any(axis=1).sum())))
    S = pd.DataFrame(S)
    S.to_csv(os.path.join(OUT, "e2e_ctx_txn_summary.csv"), index=False)
    X = Xs["refined"]
    X.to_csv(os.path.join(OUT, "e2e_units_9d.csv"), index=False)
    if not os.path.exists(os.path.join(OUT, "e2e_drift9_corr_initial.csv")):
        shutil.copy(os.path.join(OUT, "e2e_drift9_corr.csv"), os.path.join(OUT, "e2e_drift9_corr_initial.csv"))
    X[dims].corr("spearman").to_csv(os.path.join(OUT, "e2e_drift9_corr.csv"))
    pd.DataFrame([dict(dimension=d[2:], share_pos=(X[d] > 0).mean(), mean=X[d].mean(), p90=X[d].quantile(0.9),
                       share_sig=(X[d] > 0.10).mean()) for d in dims]).to_csv(os.path.join(OUT, "e2e_drift9_summary.csv"),
                                                                             index=False)
    pd.set_option("display.width", 220)
    print(UR.cls.value_counts().to_dict(), "| with definer rights preserved:", UR.cls_definer.value_counts().to_dict())
    print(RR.groupby(["cls", "reason"]).size().to_string())
    print("Only violation:", UR[UR.only_violation].cls.value_counts().to_dict())
    print("Testbed (instrumented execution):", "COMMIT in the protected part succeeded:", int(V.ok_protected.sum()))
    print(pd.crosstab(G.reason, G.observed).to_string())
    print(S.round(4).to_string())


if __name__ == "__main__":
    main()
