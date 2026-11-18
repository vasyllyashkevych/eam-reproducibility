# -*- coding: utf-8 -*-
"""Емпірична перевірка уточненого правила commit_in_routine на стенді PostgreSQL 17 (підрозділ 7.7.7).

Статус виклику не показує результату COMMIT: у типовому для коду Oracle шаблоні
BEGIN … COMMIT; … EXCEPTION WHEN OTHERS THEN ROLLBACK; … END помилку 2D000 перехоплює обробник,
і виклик завершується без помилки зі зміненим результатом. Тому підпрограми з COMMIT/ROLLBACK
виконуються в клоні шаблонної бази стенда з інструментуванням, що не змінює їх семантики:
після кожного COMMIT/ROLLBACK — RAISE NOTICE про успішне завершення транзакції, на початку кожного
обробника WHEN OTHERS — RAISE NOTICE з SQLSTATE перехопленої помилки. Виклики — як у стенді:
CALL поза явною транзакцією від імені прикладної ролі, три виклики з різними аргументами.
Вихід: out/ops_txn_validation.csv (підпрограма × виклик: COMMIT виконано, 2D000 перехоплено/неперехоплено).
"""
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

    def mark(m):                     # кожен збіг відповідає позиції з txn_positions, у тому самому порядку
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
    print(len(targets), "підпрограм"); print(g.to_string())


if __name__ == "__main__":
    main()
