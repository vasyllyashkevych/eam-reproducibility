# -*- coding: utf-8 -*-
"""Deploy the testbed of the operational evaluation on PostgreSQL 17.

1. Every unit of O2P_GOLDEN_TESTSET_v03 is deployed into its own schema namespace: u#### and
   u####_<schema> for explicitly qualified schemas of the code (so that units do not overwrite each other).
2. Routines get SECURITY DEFINER and the search_path of the unit namespace; this reproduces the Oracle definer-rights
   semantics and name resolution in the owner schema that a correct migration should preserve
   (in the source code all units with routines are definer units).
3. Tables are filled with deterministic test data (30 rows, respecting the column types).
4. The application role `app` has only EXECUTE on routines, SELECT on views and INSERT/UPDATE on tables
   with triggers; it has no direct access to other tables.
5. The catalogue of deployed objects is matched with the G1 objects (e2e_objects.csv) by unit and name.
Result: template database o2p_tpl, out/ops_deploy.csv, out/ops_objects.csv.
"""
import os, re, random, subprocess
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
DS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "data", "study_b", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv")
OBJ = os.path.join(ROOT, "..", "e2e", "out", "e2e_objects.csv")
PSQL = os.environ.get("PSQL") or __import__("shutil").which("psql") or "psql"
PORT = "55432"
TPL = "o2p_tpl"
I = re.IGNORECASE
RESERVED = {"public", "pg_catalog", "information_schema", "pg_temp"}


def admin(sql, db="postgres"):
    with psycopg.connect(f"host=localhost port={PORT} user=postgres dbname={db}", autocommit=True) as c:
        c.execute(sql)


def isolate(code, u):
    """Rename explicitly qualified schemas to u####_<schema>."""
    sch = set(m.lower() for m in re.findall(r"CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)", code, I))
    sch |= set(m.lower() for m in re.findall(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?(?:MATERIALIZED\s+VIEW|FUNCTION|PROCEDURE|VIEW|TABLE|"
        r"TRIGGER|SEQUENCE|INDEX|TYPE)\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)\"?\s*\.\s*\"?\w", code, I))
    sch |= set(m.lower() for m in re.findall(r"\bON\s+\"?(\w+)\"?\.\"?\w+", code, I))
    sch -= RESERVED
    for s in sorted(sch, key=len, reverse=True):
        code = re.sub(rf'(?<![\w."])"?{re.escape(s)}"?\s*\.(?=\s*"?\w)', f"{u}_{s}.", code, flags=I)
        code = re.sub(rf"(CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?)\"?{re.escape(s)}\"?\b", rf"\1{u}_{s}", code, flags=I)
        code = re.sub(rf"(search_path\s*(?:TO|=)\s*)\"?{re.escape(s)}\"?\b", rf"\1{u}_{s}", code, flags=I)
    return code, sorted(sch)


def deploy_unit(i, code):
    u = f"u{i:04d}"
    code, sch = isolate(code, u)
    pre = f"DROP SCHEMA IF EXISTS {u} CASCADE; CREATE SCHEMA {u};\n"
    pre += "".join(f"DROP SCHEMA IF EXISTS {u}_{s} CASCADE; CREATE SCHEMA {u}_{s};\n" for s in sch)
    path = ",".join([u] + [f"{u}_{s}" for s in sch] + ["public"])
    pre += f"SET search_path={path}; SET statement_timeout='10s';\n"
    code = re.sub(r"CREATE\s+SCHEMA\s+(\w+)", r"CREATE SCHEMA IF NOT EXISTS \1", code, flags=I)
    code = re.sub(r"IF\s+NOT\s+EXISTS\s+IF\s+NOT\s+EXISTS", "IF NOT EXISTS", code, flags=I)
    try:
        p = subprocess.run([PSQL, "-p", PORT, "-U", "postgres", "-d", TPL, "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                           input=pre + code, capture_output=True, text=True, timeout=90)
        err = [l for l in p.stderr.splitlines() if "ERROR:" in l]
    except subprocess.TimeoutExpired:
        err = ["ERROR: timeout"]
    return dict(unit=i, schemas=";".join([u] + [f"{u}_{s}" for s in sch]), search_path=path, n_err=len(err),
                first_err=re.sub(r"^.*ERROR:\s*", "", err[0])[:200] if err else "")


GEN = {
    "int": lambda r, k: r.choice([0, 1, 2, 3, 5, 10, 42, 100, -1]),
    "num": lambda r, k: r.choice([0, 1, 2.5, 10.75, 100, 3.14159, -7.5]),
    "text": lambda r, k: r.choice(["a", "abc", "X1", "test", "j1n_2", "q1l", "001", "N"]),
    "date": lambda r, k: f"2024-0{r.randint(1, 9)}-1{r.randint(0, 9)}",
    "ts": lambda r, k: f"2024-0{r.randint(1, 9)}-1{r.randint(0, 9)} 1{r.randint(0, 9)}:30:00",
    "bool": lambda r, k: r.choice([True, False]),
}


def tclass(t):
    t = t.lower()
    if re.search(r"int|serial", t): return "int"
    if re.search(r"numeric|decimal|real|double|float|money", t): return "num"
    if re.search(r"timestamp", t): return "ts"
    if t.startswith("date"): return "date"
    if t.startswith("bool"): return "bool"
    if re.search(r"char|text|name|citext|uuid", t): return "text"
    return None


def seed_tables(conn, schemas, rnd):
    cur = conn.cursor()
    cur.execute("""SELECT c.oid, n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE c.relkind IN ('r','p') AND n.nspname = ANY(%s)""", (schemas,))
    n_rows = 0
    for oid, ns, rel in cur.fetchall():
        cur.execute("""SELECT attname, format_type(atttypid, atttypmod), attnotnull, atthasdef FROM pg_attribute
                       WHERE attrelid=%s AND attnum>0 AND NOT attisdropped AND attgenerated='' AND attidentity='' ORDER BY attnum""",
                    (oid,))
        cols = [(a, t, nn, d) for a, t, nn, d in cur.fetchall() if tclass(t) or nn]
        cols = [c for c in cols if tclass(c[1])]
        if not cols:
            continue
        for k in range(30):
            vals = []
            for a, t, nn, d in cols:
                v = GEN[tclass(t)](rnd, k)
                if tclass(t) == "int":
                    v = k + 1 if k < 10 else v
                if tclass(t) == "text":
                    m = re.search(r"\((\d+)\)", t)
                    v = (v + str(k))[: int(m.group(1))] if m else v + str(k)
                vals.append(v)
            q = 'INSERT INTO "{}"."{}" ({}) VALUES ({})'.format(ns, rel, ",".join(f'"{a}"' for a, *_ in cols),
                                                                  ",".join(["%s"] * len(cols)))
            try:
                with conn.transaction():
                    cur.execute(q, vals)
                n_rows += 1
            except psycopg.Error:
                pass
    return n_rows


def catalog(conn):
    q = """
    SELECT n.nspname, p.proname, CASE p.prokind WHEN 'p' THEN 'procedure' ELSE 'function' END,
           p.oid::regprocedure::text, pg_get_function_result(p.oid), p.prorettype::regtype::text
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname ~ '^u[0-9]{4}' AND p.prokind IN ('f','p')
    UNION ALL
    SELECT n.nspname, c.relname, CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'mview' WHEN 'S' THEN 'sequence' ELSE 'table' END,
           format('%I.%I', n.nspname, c.relname), '', ''
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname ~ '^u[0-9]{4}' AND c.relkind IN ('r','p','v','m','S')
    UNION ALL
    SELECT n.nspname, t.tgname, 'trigger', format('%I.%I', n.nspname, c.relname), t.tgfoid::regproc::text, ''
    FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE NOT t.tgisinternal AND n.nspname ~ '^u[0-9]{4}'
    """
    df = pd.DataFrame(conn.execute(q).fetchall(), columns=["schema", "name", "kind", "ident", "result", "rettype"])
    df["unit"] = df.schema.str.slice(1, 5).astype(int)
    return df


def main():
    admin(f"DROP DATABASE IF EXISTS {TPL}")
    admin(f"CREATE DATABASE {TPL}")
    admin("DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app') THEN CREATE ROLE app LOGIN; END IF; END$$")
    admin("CREATE EXTENSION IF NOT EXISTS pg_stat_statements", TPL)
    d = pd.read_csv(DS)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda t: deploy_unit(*t), enumerate(d["output_db_query"].fillna(""))))
    R = pd.DataFrame(res)
    R["source"] = d["source"]
    with psycopg.connect(f"host=localhost port={PORT} user=postgres dbname={TPL}", autocommit=True) as conn:
        rnd = random.Random(7)
        R["seed_rows"] = [seed_tables(conn, r.schemas.split(";"), rnd) for r in R.itertuples()]
        C = catalog(conn)
        paths = dict(zip(R.unit, R.search_path))
        txn_conflict = []
        # privileges: definer rights for routines (names resolved in the owner schema, as in Oracle),
        # minimal privileges for the application role
        for r in C.itertuples():
            try:
                if r.kind in ("function", "procedure"):
                    src = conn.execute("SELECT pg_get_functiondef(to_regprocedure(%s))", (r.ident,)).fetchone()[0] or ""
                    if r.kind == "procedure" and re.search(r"\b(COMMIT|ROLLBACK)\b", src, I):
                        # PostgreSQL forbids COMMIT in a procedure with SECURITY DEFINER or SET: the Oracle definer
                        # rights are not reproduced here, the procedure runs with invoker rights
                        txn_conflict.append(r.ident)
                        for s_ in paths[r.unit].split(",")[:-1]:
                            conn.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{s_}" TO app')
                    else:
                        conn.execute(f"ALTER ROUTINE {r.ident} SECURITY DEFINER")
                        conn.execute(f"ALTER ROUTINE {r.ident} SET search_path = {paths[r.unit]}")
                    conn.execute(f"GRANT EXECUTE ON ROUTINE {r.ident} TO app")
                elif r.kind in ("view", "mview"):
                    conn.execute(f"GRANT SELECT ON {r.ident} TO app")
            except psycopg.Error:
                pass
        for s in sorted(set(C.schema)):
            conn.execute(f'GRANT USAGE ON SCHEMA "{s}" TO app')
        for r in C[C.kind == "trigger"].itertuples():
            try:
                conn.execute(f"GRANT SELECT, INSERT, UPDATE ON {r.ident} TO app")
            except psycopg.Error:
                pass
    O = pd.read_csv(OBJ, keep_default_na=False)
    O["obj_id"] = range(len(O))
    O = O[O.pg_kind.isin(["procedure", "function", "view", "mview", "table", "trigger", "sequence"])]
    C["lname"] = C.name.str.lower()
    O["lname"] = O.pg_name.str.lower().str.split(".").str[-1]
    M = O.merge(C, left_on=["unit", "lname"], right_on=["unit", "lname"], how="left", suffixes=("", "_db"))
    M["deployed"] = M.ident.notna()
    pd.DataFrame({"ident": txn_conflict}).to_csv(os.path.join(OUT, "ops_definer_txn_conflict.csv"), index=False)
    print("definer+COMMIT conflicts:", len(txn_conflict))
    R.to_csv(os.path.join(OUT, "ops_deploy.csv"), index=False)
    C.to_csv(os.path.join(OUT, "ops_catalog.csv"), index=False)
    M.to_csv(os.path.join(OUT, "ops_objects.csv"), index=False)
    print("clean units:", (R.n_err == 0).sum(), "of", len(R), "| seeded rows:", R.seed_rows.sum())
    print("catalog objects:", len(C), C.kind.value_counts().to_dict())
    print("G1 objects matched to deployed:", int(M.deployed.sum()), "of", len(M))


if __name__ == "__main__":
    main()
