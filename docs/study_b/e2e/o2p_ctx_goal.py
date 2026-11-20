# -*- coding: utf-8 -*-
"""Context and goal dimensions of drift on real migration data (complements o2p_structure.py).

Context drift (Eq. (6)): D_ctx = conf * share of violated contextual assumptions that a unit relies on.
Assumptions are detected in the Oracle code by regular-expression rules; the actual value of every parameter in the
target environment is measured by running a control query on a deployed PostgreSQL 17 (testbed `ops/`), and the
Oracle value is taken from the documented behaviour of Oracle Database 19c.

Goal drift: the goal model of a unit consists of the verification-specification attributes of the
oracle-spec-project (pipeline/profiles.py: profiles table/view/routine/trigger/orchestrator,
conditional security goal of dynamic SQL). The profile is computed separately for Oracle and PostgreSQL code;
D_goal = (added + removed + goals with a changed achievement criterion) / |G_O U G_P|.

Output: out/e2e_ctx_checks.csv, out/e2e_units_9d.csv, out/e2e_drift9_summary.csv."""
import os, re, sys
import numpy as np, pandas as pd
try:
    import psycopg
except ImportError:          # offline mode (EAM_PG_OFFLINE=1) does not need a database driver
    psycopg = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "study_b", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv")
SPEC = os.path.join(HERE, "..", "third_party", "oracle_spec_pipeline")
sys.path.insert(0, SPEC)
from pipeline import profiles as PR          # real object-profile classifier, unchanged

DSN = os.environ.get("OPS_DSN", "host=localhost port=55432 user=postgres dbname=o2p")
I = re.IGNORECASE

# contextual assumptions
# key: (description, rule that detects the dependency in Oracle code, documented Oracle value, PostgreSQL control query)
CTX = {
    "empty_string_is_null": ("empty string is identical to NULL", r"''|\bNVL2?\s*\(|\bIS\s+(NOT\s+)?NULL\b",
                             "true", "SELECT ('' IS NULL)::text"),
    "concat_ignores_null": ("concatenation with NULL does not give NULL", r"\|\|", "true", "SELECT (('a' || NULL) IS NOT NULL)::text"),
    "date_keeps_time": ("DATE type keeps the time of day", r"\bDATE\b|\bSYSDATE\b", "true",
                        "SELECT ('2020-01-01 10:30'::date::timestamp <> '2020-01-01'::timestamp)::text"),
    "nls_date_format": ("default date format is DD-MON-RR", r"\bTO_CHAR\s*\(\s*[\w.]+\s*\)|\bTO_DATE\s*\(\s*[^,()]+\)",
                        "DD-MON-RR", "SELECT current_setting('DateStyle')"),
    "clock_statement_time": ("SYSDATE is the statement execution time", r"\bSYSDATE\b|\bSYSTIMESTAMP\b", "true",
                             None),     # measured separately inside a transaction
    "upper_identifier_fold": ("unquoted identifiers are folded to upper case", r'"[A-Z][A-Z0-9_$#]*"', "true",
                              None),
    "decimal_division": ("integer division gives a fractional result", r"\b(PLS_INTEGER|BINARY_INTEGER|INTEGER|INT)\b[\s\S]*?\w\s*/\s*\w",
                         "true", "SELECT ((1/2) <> 0)::text"),
    "ddl_autocommit": ("DDL implicitly commits the transaction", r"EXECUTE\s+IMMEDIATE\s+'\s*(CREATE|DROP|ALTER|TRUNCATE)|^\s*(TRUNCATE)\b",
                       "true", None),
    "commit_in_routine": ("COMMIT/ROLLBACK are allowed in any routine", r"\b(COMMIT|ROLLBACK)\b", "true", None),
    "no_data_found_raises": ("SELECT INTO without rows raises an exception", r"\bSELECT\b[^;]*?\bINTO\b", "true", None),
    "binary_sort": ("binary string ordering (NLS_SORT=BINARY)", r"\bORDER\s+BY\b", "true",
                    "SELECT (('a' COLLATE \"default\") > ('B' COLLATE \"default\"))::text"),
    # assumptions that hold (checks that the measure is not always 1)
    "read_committed_default": ("default isolation level is READ COMMITTED", r"\b(INSERT|UPDATE|DELETE|MERGE)\b",
                               "read committed", "SELECT current_setting('default_transaction_isolation')"),
    "nulls_last_asc": ("NULLs sort last with ORDER BY ASC", r"\bORDER\s+BY\b", "true",
                       "SELECT ((SELECT x FROM (VALUES (1),(NULL)) v(x) ORDER BY x LIMIT 1) IS NOT NULL)::text"),
    "like_case_sensitive": ("LIKE is case sensitive", r"\bLIKE\b", "true", "SELECT (NOT ('A' LIKE 'a'))::text"),
    "unique_multi_null": ("UNIQUE allows several NULLs", r"\bUNIQUE\b", "true", None),
}


def live_checks(conn):
    """Run the control queries on the deployed PostgreSQL and return the actual value of each parameter."""
    res = {}
    cur = conn.cursor()
    for k, (_, _, _, q) in CTX.items():
        if q:
            cur.execute(q)
            res[k] = str(cur.fetchone()[0])
    # "now" inside a transaction
    with conn.transaction():
        cur.execute("SELECT now()"); a = cur.fetchone()[0]
        cur.execute("SELECT pg_sleep(0.02)")
        cur.execute("SELECT now()"); b = cur.fetchone()[0]
    res["clock_statement_time"] = str(a != b).lower()
    # identifier case folding
    with conn.transaction():
        cur.execute('CREATE TEMP TABLE ctx_fold (x int)')
        cur.execute("SELECT count(*) FROM pg_class WHERE relname = 'CTX_FOLD'")
        res["upper_identifier_fold"] = str(cur.fetchone()[0] == 1).lower()
        cur.execute("DROP TABLE ctx_fold")
    # transactional DDL
    try:
        with conn.transaction():
            cur.execute("CREATE TABLE ctx_ddl (x int)")
            raise RuntimeError("rollback")
    except RuntimeError:
        pass
    cur.execute("SELECT to_regclass('ctx_ddl') IS NOT NULL")
    res["ddl_autocommit"] = str(cur.fetchone()[0]).lower()
    # COMMIT in a function
    cur.execute("CREATE OR REPLACE FUNCTION pg_temp.ctx_c() RETURNS int LANGUAGE plpgsql AS $$BEGIN COMMIT; RETURN 1; END$$")
    try:
        with conn.transaction():
            cur.execute("SELECT pg_temp.ctx_c()")
        res["commit_in_routine"] = "true"
    except psycopg.Error:
        res["commit_in_routine"] = "false"
    # SELECT INTO without rows
    cur.execute("CREATE OR REPLACE FUNCTION pg_temp.ctx_n() RETURNS int LANGUAGE plpgsql AS "
                "$$DECLARE v int; BEGIN SELECT 1 INTO v WHERE false; RETURN coalesce(v, -1); END$$")
    try:
        with conn.transaction():
            cur.execute("SELECT pg_temp.ctx_n()")
            res["no_data_found_raises"] = "false"
    except psycopg.Error:
        res["no_data_found_raises"] = "true"
    with conn.transaction():
        cur.execute("CREATE TEMP TABLE ctx_u (x int UNIQUE)")
        try:
            with conn.transaction():
                cur.execute("INSERT INTO ctx_u VALUES (NULL),(NULL)")
            res["unique_multi_null"] = "true"
        except psycopg.Error:
            res["unique_multi_null"] = "false"
        cur.execute("DROP TABLE ctx_u")
    return res


def strip_comments(code):
    return PR._strip_comments(code)


# goals (specification attributes)
def goals(code):
    """Profile and set of verification goals from the object-profile classifier (no LLM)."""
    c = strip_comments(code)
    # declarations in the anonymised production code often lack CREATE; normalised for classification only
    c = re.sub(r"^(\s*)(PROCEDURE|FUNCTION|PACKAGE|TRIGGER)\b", r"\1CREATE \2", c, flags=I | re.M)
    c = re.sub(r"\b(NON)?EDITIONABLE\s+", "", c, flags=I)
    inc = len(PR._ORCHESTRATOR_PATTERN.findall(c))
    prof = None
    for pat, p in PR._CLASSIFY_PATTERNS:
        if pat.search(c):
            prof = p
            break
    if prof is None:
        prof = "orchestrator" if inc else "table"
    G = set(PR.PROFILES[prof])
    if prof in ("routine", "trigger") and any(p.search(c) for p in PR._DYNAMIC_SQL_PATTERNS):
        G.add(PR.SECURITY_ATTRIBUTE)
    return prof, G


def output_channel(code, oracle):
    c = strip_comments(code)
    if oracle:
        if re.search(r"SYS_REFCURSOR|REF\s+CURSOR", c, I): return "refcursor"
        if re.search(r"\bPIPELINED\b", c, I): return "set"
        if re.search(r"\bFUNCTION\b[\s\S]*?\bRETURN\s+\w", c, I): return "scalar"
        if re.search(r"\bOUT\b", c, I): return "out"
        return "none"
    if re.search(r"RETURNS\s+(SETOF|TABLE)\b", c, I): return "set"
    if re.search(r"RETURNS\s+refcursor|\brefcursor\b", c, I): return "refcursor"
    if re.search(r"RETURNS\s+(void|trigger)\b", c, I):
        return "out" if re.search(r"\b(INOUT|OUT)\b", c, I) else "none"
    if re.search(r"\bRETURNS\s+\w", c, I): return "scalar"
    if re.search(r"\b(INOUT|OUT)\b", c, I): return "out"
    return "none"


def changed_criteria(ora, pg, unit_row):
    """Goals whose achievement criterion (the condition that is verified) has changed."""
    ch = set()
    if output_channel(ora, True) != output_channel(pg, False):
        ch.add(("Regression", "result_parity"))
    if unit_row.n_kind_changed + unit_row.n_unpacked > 0:
        ch.add(("Smoke", "critical_calls"))           # different call form (CALL / SELECT, name outside a package)
    if re.search(r"RAISE_APPLICATION_ERROR|\bPRAGMA\s+EXCEPTION_INIT\b|\bWHEN\s+(NO_DATA_FOUND|TOO_MANY_ROWS|DUP_VAL_ON_INDEX)\b",
                 ora, I):
        ch.add(("Unit", "exception_paths"))           # numeric ORA-20xxx codes -> SQLSTATE
    if unit_row.n_unpacked + unit_row.n_dissolved > 0:
        ch.add(("Compatibility", "package_mapping"))  # package state and namespace are not preserved
    if re.search(r"''|\bNVL2?\s*\(", ora, I):
        ch.add(("Compatibility", "null_behavior"))    # '' = NULL must be stated explicitly
    return ch


def main():
    raw = pd.read_csv(DS)
    U = pd.read_csv(os.path.join(OUT, "e2e_units.csv"), keep_default_na=False)
    if os.environ.get("EAM_PG_OFFLINE") == "1":   # use the checks recorded on the PostgreSQL 17.11 testbed
        rec = pd.read_csv(os.path.join(HERE, "..", "..", "..", "data", "study_b", "recorded", "e2e_ctx_checks.csv"), dtype=str, keep_default_na=False)
        live, ver = dict(zip(rec.assumption, rec.pg_value)), rec.pg_version.iloc[0]
    else:
        with psycopg.connect(DSN, autocommit=True) as conn:
            live = live_checks(conn)
            ver = conn.execute("SHOW server_version").fetchone()[0]
    chk = []
    for k, (desc, rx, ora_val, _) in CTX.items():
        chk.append(dict(assumption=k, description=desc, oracle_value=ora_val, pg_value=live[k],
                        violated=(live[k].lower() != ora_val.lower()), pg_version=ver))
    chk = pd.DataFrame(chk)
    chk.to_csv(os.path.join(OUT, "e2e_ctx_checks.csv"), index=False)
    viol = dict(zip(chk.assumption, chk.violated))
    rows = []
    for i, r in U.iterrows():
        ora = strip_comments(str(raw.input_db_query.iloc[i] or ""))
        pg = str(raw.output_db_query.iloc[i] or "")
        relied = [k for k, (_, rx, _, _) in CTX.items() if re.search(rx, ora, I | re.M)]
        nv = [k for k in relied if viol[k]]
        conf = 1.0                                   # both sides checked: PostgreSQL by execution, Oracle by documentation
        d_ctx = conf * len(nv) / len(relied) if relied else 0.0
        po, GO = goals(ora)
        pp, GP = goals(pg)
        ch = changed_criteria(ora, pg, r) & GO & GP
        union = GO | GP
        d_goal = (len(GO - GP) + len(GP - GO) + len(ch)) / len(union) if union else 0.0
        rows.append(dict(unit=r.unit, ctx_relied=";".join(relied), ctx_violated=";".join(nv), d_contextual=d_ctx,
                         prof_ora=po, prof_pg=pp, goals_ora=len(GO), goals_pg=len(GP), goals_added=len(GP - GO),
                         goals_removed=len(GO - GP), goals_changed=";".join(sorted(a for _, a in ch)), d_goal=d_goal))
    G = pd.DataFrame(rows)
    U9 = U.merge(G, on="unit")
    U9.to_csv(os.path.join(OUT, "e2e_units_9d.csv"), index=False)
    dims = ["d_configuration", "d_topological", "d_role", "d_policy", "d_architectural", "d_semantic", "d_security",
            "d_contextual", "d_goal"]
    S = pd.DataFrame([dict(dimension=d[2:], share_pos=(U9[d] > 0).mean(), mean=U9[d].mean(), p90=U9[d].quantile(0.9),
                           share_sig=(U9[d] > 0.10).mean()) for d in dims])
    S.to_csv(os.path.join(OUT, "e2e_drift9_summary.csv"), index=False)
    C = U9[dims].corr(method="spearman")
    C.to_csv(os.path.join(OUT, "e2e_drift9_corr.csv"))
    pd.set_option("display.width", 200)
    print(chk[["assumption", "oracle_value", "pg_value", "violated"]].to_string())
    print(S.round(3).to_string())
    print("profile change:", (U9.prof_ora != U9.prof_pg).mean().round(3))
    print(pd.Series(";".join(U9.goals_changed).split(";")).value_counts().head(8))
    print(C[["d_contextual", "d_goal"]].round(2).to_string())


if __name__ == "__main__":
    main()
