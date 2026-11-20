# -*- coding: utf-8 -*-
"""Execution errors of the migrated code on PostgreSQL 17 in the baseline state (no defects injected): the raw
material of the independent reference used to evaluate property inference.

All testbed objects are executed in a clone of the template database as in ops_baseline_exec (three calls with different
arguments as the application role). To capture errors that Oracle-style code swallows in a WHEN OTHERS handler,
a RAISE NOTICE with the SQLSTATE and the error text is added at the start of every such handler (the code
semantics do not change). Uncaught and caught errors are recorded with their messages.
Output: out/ops_exec_errors.csv."""
import os, re, sys, random
import pandas as pd
import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testbed_run as TR            # noqa: E402

DB = "o2p_execgold"
I = re.IGNORECASE


def instrument(src):
    head, sep, rest = src.partition("$")
    body = re.sub(r"\bWHEN\s+OTHERS\s+THEN\b",
                  lambda m: f"{m.group(0)} RAISE NOTICE 'ctxerr|%|%', SQLSTATE, replace(SQLERRM, '|', '/');", rest, flags=I)
    return head + sep + body


def main():
    with TR.conn("postgres", "execgold") as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB}")
        c.execute(f"CREATE DATABASE {DB} TEMPLATE {TR.TPL}")
    D = TR.load_objects()
    adm = TR.conn(DB, "execgold", "postgres")
    info = TR.introspect(adm, D)
    for o in info.values():
        if o["kind"] in ("function", "procedure") and o.get("lang") == "plpgsql":
            src = adm.execute("SELECT pg_get_functiondef(%s)", (o["oid"],)).fetchone()[0]
            if re.search(r"WHEN\s+OTHERS", src, I):
                try:
                    adm.execute(instrument(src))
                except psycopg.Error:
                    pass
    wl = TR.conn(DB, "execgold", "app")
    notes = []
    wl.add_notice_handler(lambda d: notes.append(d.message_primary or ""))
    rows = []
    cur = wl.cursor()
    for j, o in info.items():
        rnd = random.Random(j)
        for k in range(3):
            q = TR.op_sql(o, rnd)
            if q is None:
                continue
            notes.clear()
            msg = ""
            try:                                                   # as in TR.run_op, but keeping the error text
                if o.get("txn"):
                    cur.execute("SET statement_timeout = 1500")
                    cur.execute(f"SET search_path = {o.get('path')}")
                else:
                    cur.execute("BEGIN")
                    cur.execute("SET LOCAL statement_timeout = 1500")
                cur.execute(q)
                state = ""
            except psycopg.Error as e:
                state, msg = e.sqlstate or "XX000", (e.diag.message_primary or str(e)).splitlines()[0]
            finally:
                try:
                    cur.execute("RESET search_path" if o.get("txn") else "ROLLBACK")
                except psycopg.Error:
                    pass
            rows.append(dict(j=j, unit=o["unit"], kind=o["kind"], call=k, where="uncaught" if state else "none",
                             sqlstate=state, message=msg))
            for n in notes:
                if n.startswith("ctxerr|"):
                    _, st, m = n.split("|", 2)
                    rows.append(dict(j=j, unit=o["unit"], kind=o["kind"], call=k, where="caught", sqlstate=st, message=m))
    adm.close(); wl.close()
    with TR.conn("postgres", "execgold") as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB}")
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(TR.OUT, "ops_exec_errors.csv"), index=False)
    E = R[R.sqlstate != ""]
    print(len(info), "objects;", E.j.nunique(), "with errors;", E.groupby("where").size().to_dict())
    print(E.sqlstate.value_counts().head(25).to_dict())


if __name__ == "__main__":
    main()
