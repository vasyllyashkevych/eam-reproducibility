# -*- coding: utf-8 -*-
"""Empirical check of the refined `commit_in_routine` rule on the PostgreSQL 17 testbed.

The call status does not show the result of a COMMIT: in the pattern typical of Oracle code
BEGIN ... COMMIT; ... EXCEPTION WHEN OTHERS THEN ROLLBACK; ... END the handler catches error 2D000,
so the call finishes without an error but with a changed result. Routines with COMMIT/ROLLBACK are
therefore run in a clone of the template database with instrumentation that does not change their semantics:
after every COMMIT/ROLLBACK a RAISE NOTICE reports successful completion of the transaction, and at the start of
every WHEN OTHERS handler a RAISE NOTICE reports the SQLSTATE of the caught error. Calls are made as in the testbed:
CALL outside an explicit transaction as the application role, three calls with different arguments.
Output: out/ops_txn_validation.csv (routine x call: COMMIT executed, 2D000 caught / not caught)."""
import os, re, sys, random
import pandas as pd
import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testbed_run as TR            # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "e2e"))
from o2p_ctx_txn import txn_positions   # noqa: E402

DB = "o2p_txnval"
I = re.IGNORECASE


def instrument(src):
    head, sep, rest = src.partition("$")
    pos = txn_positions(rest)
    k = iter(pos)

    def mark(m):                     # each match corresponds to one position from txn_positions, in the same order
        p = next(k)
        return m.group(0) + (f" RAISE NOTICE 'ctxobs:ok:{p}';" if m.group(2) else "")
    body = re.sub(r"\b(COMMIT|ROLLBACK)\b(\s*;)?", mark, rest, flags=I)
    body = re.sub(r"\bWHEN\s+OTHERS\s+THEN\b", lambda m: f"{m.group(0)} RAISE NOTICE 'ctxobs:caught:%', SQLSTATE;",
                  body, flags=I)
    return head + sep + body


def main():
    with TR.conn("postgres", "txnval") as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB}")
        c.execute(f"CREATE DATABASE {DB} TEMPLATE {TR.TPL}")
    D = TR.load_objects()
    adm = TR.conn(DB, "txnval", "postgres")
    info = TR.introspect(adm, D)
    targets = {}
    for j, o in info.items():
        if o["kind"] not in ("function", "procedure"):
            continue
        src = adm.execute("SELECT pg_get_functiondef(%s)", (o["oid"],)).fetchone()[0]
        if re.search(r"\b(COMMIT|ROLLBACK)\b", src, I):
            try:
                adm.execute(instrument(src))
                targets[j] = o
            except psycopg.Error as e:
                print("skip", o["ident"], e.sqlstate)
    wl = TR.conn(DB, "txnval", "app")
    notes = []
    wl.add_notice_handler(lambda d: notes.append(d.message_primary or ""))
    rows = []
    for j, o in targets.items():
        rnd = random.Random(j)
        for k in range(3):
            q = TR.op_sql(o, rnd)
            if q is None:
                continue
            notes.clear()
            ok, state, *_ = TR.run_op(wl, q, True, o["kind"] == "procedure", o.get("path"))
            obs = [n for n in notes if n.startswith("ctxobs:")]
            rows.append(dict(j=j, unit=o["unit"], ident=o["ident"], kind=o["kind"], call=k, ok=ok, state=state,
                             ok_plain=sum(n == "ctxobs:ok:plain" for n in obs),
                             ok_handler=sum(n == "ctxobs:ok:handler" for n in obs),
                             ok_protected=sum(n == "ctxobs:ok:protected" for n in obs),
                             caught_other=sum(n.startswith("ctxobs:caught:") and n != "ctxobs:caught:2D000" for n in obs),
                             caught_2d000=sum(n == "ctxobs:caught:2D000" for n in obs),
                             uncaught_2d000=int(state == "2D000")))
    adm.close(); wl.close()
    with TR.conn("postgres", "txnval") as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB}")
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(TR.OUT, "ops_txn_validation.csv"), index=False)
    g = R.groupby(["kind"]).agg(calls=("ok", "size"), ok_plain=("ok_plain", lambda s: (s > 0).sum()),
                                ok_protected=("ok_protected", lambda s: (s > 0).sum()),
                                caught=("caught_2d000", lambda s: (s > 0).sum()), uncaught=("uncaught_2d000", "sum"))
    print(len(targets), "routines"); print(g.to_string())


if __name__ == "__main__":
    main()
