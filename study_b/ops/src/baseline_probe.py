# -*- coding: utf-8 -*-
"""Базова придатність об'єктів стенда до виконання: частка успішних викликів від імені app (без дефектів)."""
import os, sys, random, collections
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testbed_run as TR

D = TR.load_objects()
c = TR.conn(TR.TPL, "baseline", "postgres")
info = TR.introspect(c, D)
wl = TR.conn(TR.TPL, "baseline", "app")
rnd = random.Random(1)
rows = []
for j, o in info.items():
    q = TR.op_sql(o, rnd)
    if q is None:
        continue
    res = [TR.run_op(wl, TR.op_sql(o, rnd), True, o.get("txn", False), o.get("path")) for _ in range(3)]
    rows.append(dict(j=j, unit=o["unit"], kind=o["kind"], ok=sum(r[0] for r in res) / 3,
                     state=collections.Counter(r[1] for r in res if not r[0]).most_common(1)[0][0] if not all(r[0] for r in res) else ""))
B = pd.DataFrame(rows)
B.to_csv(os.path.join(TR.OUT, "ops_baseline_exec.csv"), index=False)
print(B.groupby("kind").ok.agg(["mean", "size"]))
print(B[B.ok < 1].state.value_counts().head(12))
