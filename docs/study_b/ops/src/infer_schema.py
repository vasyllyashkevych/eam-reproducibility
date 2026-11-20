# -*- coding: utf-8 -*-
"""Infer the schema of anonymised tables from execution feedback (testbed extension).

Most units of the production database refer to tables whose schema is not part of the corpus. For every
routine/view/trigger in o2p_tpl a control call is executed as `postgres`; on error 42P01 a stub table is created in
the unit schema, on 42703 a column is added (type taken from the usage context in the code; a text column for a
positional INSERT), on 42702 the ambiguous column is removed from all stubs except the first. At most MAX_ITER
iterations per object. The stubs are filled with 30 rows. Output: out/ops_inferred_tables.csv."""
import os, re, sys, random
import pandas as pd
import psycopg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testbed_run as TR

MAX_ITER = 30
I = re.IGNORECASE


def guess_type(col, src):
    c = re.escape(col)
    if re.search(rf"(date|_dt|_d|time|_ts)$", col, I) or re.search(rf"\b{c}\b\s*(<|>|=|BETWEEN)\s*(now\(\)|current_date|current_timestamp|to_date|to_timestamp|'\d{{4}}-)", src, I):
        return "timestamp"
    if re.search(rf"\b{c}\b\s*([-+*/<>]|=\s*-?\d)|([-+*/<>]|=)\s*\b\w+\.?{c}\b|\b(SUM|AVG|MAX|MIN|ROUND|TRUNC)\s*\(\s*(\w+\.)?{c}\b", src, I):
        return "numeric"
    if re.search(rf"(_id|_no|_num|_cnt|_qty|_amt|^id|^n_)$", col, I):
        return "numeric"
    return "text"


def main():
    D = TR.load_objects()
    c = TR.conn(TR.TPL, "infer", "postgres")
    info = TR.introspect(c, D)
    rnd = random.Random(3)
    stubs = {}          # unit -> [identifiers of stub tables]
    log = []
    for j, o in sorted(info.items()):
        q = TR.op_sql(o, rnd) if o["kind"] != "trigger" else TR.trigger_sql(o, rnd)
        if q is None:
            continue
        src = ""
        if o["kind"] in ("function", "procedure"):
            src = c.execute("SELECT pg_get_functiondef(%s)", (o["oid"],)).fetchone()[0]
        elif o["kind"] == "view":
            continue                                   # the view was created successfully, so its dependencies exist
        elif o["kind"] == "trigger":
            src = c.execute("SELECT pg_get_functiondef(tgfoid) FROM pg_trigger WHERE tgname=%s AND tgrelid=%s::regclass",
                            (o["tg"], o["ident"])).fetchone()[0]
        home = o["schema"]
        for it in range(MAX_ITER):
            cur = c.cursor()
            try:
                if o.get("txn"):
                    cur.execute("SET statement_timeout = 1500")
                    cur.execute(f"SET search_path = {o['path']}")
                else:
                    cur.execute("BEGIN"); cur.execute("SET LOCAL statement_timeout = 1500")
                cur.execute(q)
                if not o.get("txn"):
                    cur.execute("ROLLBACK")
                break
            except psycopg.Error as e:
                if not o.get("txn"):
                    c.execute("ROLLBACK")
                msg = str(e).splitlines()[0]
                st = e.sqlstate
                if st == "42P01":
                    m = re.search(r'relation "([\w.]+)" does not exist', msg)
                    if not m:
                        break
                    name = m.group(1).lower()
                    if "." in name:
                        sch, tb = name.split(".", 1)
                        sch = sch if sch.startswith("u") and re.match(r"u\d{4}", sch) else f"{home.split('_')[0]}_{sch}"
                        c.execute(f'CREATE SCHEMA IF NOT EXISTS "{sch}"')
                    else:
                        sch, tb = home, name
                    ident = f'"{sch}"."{tb}"'
                    if c.execute("SELECT to_regclass(%s)", (ident,)).fetchone()[0] is not None:
                        break                              # the table exists in another schema, so it is not a stub
                    c.execute(f"CREATE TABLE {ident} ()")
                    stubs.setdefault(o["unit"], []).append(ident)
                    log.append(dict(unit=o["unit"], j=j, action="table", target=ident, column=""))
                elif st == "42703":
                    m = re.search(r'column "?([\w]+)"?\.?"?(\w+)?"? (?:of relation "(\w+)" )?does not exist', msg)
                    if not m:
                        break
                    if m.group(2):
                        alias, col = m.group(1).lower(), m.group(2).lower()
                    else:
                        alias, col = None, m.group(1).lower()
                    cand = stubs.get(o["unit"], [])
                    if m.group(3):
                        cand = [s for s in cand if s.endswith(f'"{m.group(3).lower()}"')] or cand
                    elif alias:
                        mm = re.search(rf"\b(?:FROM|JOIN|UPDATE|INTO)\s+(?:\w+\.)?(\w+)\s+(?:AS\s+)?{re.escape(alias)}\b", src, I)
                        tn = mm.group(1).lower() if mm else alias
                        cand = [s for s in cand if s.endswith(f'"{tn}"')] or cand
                    if not cand:
                        break
                    tgt = cand[-1]
                    ty = guess_type(col, src)
                    try:
                        c.execute(f'ALTER TABLE {tgt} ADD COLUMN IF NOT EXISTS "{col}" {ty}')
                    except psycopg.Error:
                        break
                    log.append(dict(unit=o["unit"], j=j, action="column", target=tgt, column=f"{col} {ty}"))
                elif st == "42601" and "more expressions than target columns" in msg:
                    iq = e.diag.internal_query or ""
                    m = re.search(r"INSERT\s+INTO\s+(?:\w+\.)?(\w+)", iq, I)
                    cand = [x for x in stubs.get(o["unit"], []) if m and x.endswith(f'"{m.group(1).lower()}"')]
                    if not cand:
                        break
                    k = c.execute("SELECT count(*) FROM pg_attribute WHERE attrelid = %s::regclass AND attnum > 0",
                                  (cand[0],)).fetchone()[0]
                    c.execute(f'ALTER TABLE {cand[0]} ADD COLUMN "c{k + 1}" text')
                    log.append(dict(unit=o["unit"], j=j, action="column", target=cand[0], column=f"c{k + 1} text"))
                elif st == "42702":
                    m = re.search(r'column reference "(\w+)" is ambiguous', msg)
                    if not m:
                        break
                    col = m.group(1).lower()
                    for s in stubs.get(o["unit"], [])[1:]:
                        c.execute(f'ALTER TABLE {s} DROP COLUMN IF EXISTS "{col}"')
                    log.append(dict(unit=o["unit"], j=j, action="drop_ambiguous", target="", column=col))
                else:
                    break
    # fill the stubs and grant privileges
    allst = sorted({s for v in stubs.values() for s in v})
    n = 0
    for s in allst:
        cols = c.execute("""SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute
                            WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum""", (s,)).fetchall()
        if not cols:
            continue
        for k in range(30):
            vals = []
            for a, t in cols:
                if t == "numeric": vals.append(k % 10 + 1)
                elif t.startswith("timestamp"): vals.append(f"2024-03-{k % 28 + 1:02d} 10:30:00")
                else: vals.append(str(k % 10 + 1))
            try:
                c.execute("INSERT INTO {} ({}) VALUES ({})".format(s, ",".join(f'"{a}"' for a, _ in cols), ",".join(["%s"] * len(cols))), vals)
                n += 1
            except psycopg.Error:
                pass
    # procedures with COMMIT run with invoker rights: grants to app on the tables and sequences of their units
    cf = pd.read_csv(os.path.join(TR.OUT, "ops_definer_txn_conflict.csv"))
    dep = pd.read_csv(os.path.join(TR.OUT, "ops_deploy.csv"), keep_default_na=False).set_index("unit")
    for u in sorted({int(re.match(r"u(\d{4})", x).group(1)) for x in cf.ident}):
        for s_ in dep.loc[u, "search_path"].split(",")[:-1]:
            c.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{s_}" TO app')
            c.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA "{s_}" TO app')
    L = pd.DataFrame(log)
    L.to_csv(os.path.join(TR.OUT, "ops_inferred_tables.csv"), index=False)
    print("stub tables:", len(allst), "columns:", int((L.action == "column").sum()) if len(L) else 0, "rows:", n)


if __name__ == "__main__":
    main()
