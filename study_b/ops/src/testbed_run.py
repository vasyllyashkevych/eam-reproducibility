# -*- coding: utf-8 -*-
"""Стендова експлуатаційна перевірка варіантів моніторингу (підрозділ 7.7.7).

Для кожного зерна:
  1) з o2p_tpl створюється робоча база (CREATE DATABASE ... TEMPLATE), статистика скидається;
  2) конфігурації моніторингу варіантів S0–S3, S3-O, S3-9D та аналогів A-RB, A-RX, A-AM, A-RV
     беруться з e2e_adaptation.run_seed (той самий синтез, що й у 7.7.6) і обмежуються об'єктами,
     розгорнутими на стенді;
  3) T кроків навантаження: прикладна роль app викликає підпрограми, подання й тригери
     (частота за законом Ципфа з тим самим вектором використання, що й у симуляції);
  4) на кожному кроці збирається реальна телеметрія СУБД: pg_stat_user_functions,
     pg_stat_statements, pg_stat_user_tables, каталог (існування, SECURITY DEFINER, права, стан тригерів),
     CSV-журнал помилок сервера; зонди-твердження повторно виконують контрольні виклики;
  5) дефекти міграції вносяться як реальні мутації розгорнутого коду (DDL) у випадкові моменти t0;
  6) кожен варіант оцінює лише власні зонди з власною періодичністю (рівень вибірки 1/2/3 —
     кожні 4/2/1 кроки); обчислюються P, R, F1, MTTD, LA, FAR і виміряні накладні витрати (мс/крок).
Вихід: out/ops_runs.csv, out/ops_defects.csv, out/ops_alarms.csv, out/ops_overhead.csv.
"""
import os, re, sys, csv, json, time, pickle, hashlib, random, datetime, decimal
import numpy as np, pandas as pd
import psycopg
from psycopg import sql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
E2E = os.path.join(ROOT, "..", "e2e")
sys.path.insert(0, E2E)
import e2e_adaptation as EA            # noqa: E402

PORT = 55432
TPL = "o2p_tpl"
LOGDIR = os.environ.get("OPS_PGLOG", os.path.join(ROOT, "pgdata", "log"))   # csvlog directory of the test cluster
SEEDS = [int(s) for s in os.environ.get("OPS_SEEDS", "1,2,3,4,5,6,7,8,9,10").split(",")]
VARIANTS = os.environ.get("OPS_VARIANTS", "S0,S1,S2,S3,S3-O,A-RB,A-RX,A-AM,A-RV,S3-9D").split(",")
T = int(os.environ.get("OPS_T", 100))          # кроків експлуатації
W = 15                                          # калібрування базових ліній зондів
OPS_PER_STEP = int(os.environ.get("OPS_K", 120))
SUPPRESS = 10                                   # вікно пригнічення повторних тривог зонда
PERIOD = {1: 4, 2: 2, 3: 1}
I = re.IGNORECASE


def conn(db, app, user="postgres"):
    c = psycopg.connect(f"host=localhost port={PORT} user={user} dbname={db} application_name={app}", autocommit=True)
    return c


# ---------------------------------------------------------------- об'єкти стенда
def load_objects():
    O = pd.read_csv(os.path.join(E2E, "out", "e2e_objects.csv"), keep_default_na=False)
    O["row"] = range(len(O))
    post_rows = [r for r, k in zip(O.row, O.pg_kind) if k in EA.MONITORED]        # порядок obj_post у build_model
    j_of_row = {r: j for j, r in enumerate(post_rows)}
    D = pd.read_csv(os.path.join(OUT, "ops_objects.csv"), keep_default_na=False)
    D = D[D.deployed.astype(str) == "True"].drop_duplicates("obj_id")
    D["j"] = D.obj_id.map(j_of_row)
    D = D[D.j.notna()].copy()
    D["j"] = D.j.astype(int)
    P = pd.read_csv(os.path.join(OUT, "ops_deploy.csv"), keep_default_na=False)[["unit", "search_path"]]
    return D.merge(P, on="unit", how="left")


def introspect(c, D):
    """Сигнатури підпрограм, таблиці тригерів, джерела функцій."""
    cur = c.cursor()
    info = {}
    for r in D.itertuples():
        if r.kind in ("function", "procedure"):
            cur.execute("""SELECT p.oid, l.lanname, p.prokind, p.proretset, p.prorettype::regtype::text,
                                  coalesce(p.proallargtypes, p.proargtypes::oid[])::regtype[]::text[],
                                  coalesce(p.proargmodes, array_fill('i'::"char", array[p.pronargs]))::text[],
                                  p.pronargdefaults
                           FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang WHERE p.oid = to_regprocedure(%s)""", (r.ident,))
            x = cur.fetchone()
            if not x or x[1] not in ("plpgsql", "sql"):
                continue
            oid, lan, kind, retset, rett, types, modes, ndef = x
            src = cur.execute("SELECT pg_get_functiondef(%s)", (oid,)).fetchone()[0]
            info[r.j] = dict(kind=r.kind, ident=r.ident, oid=oid, lang=lan, retset=retset, rettype=rett,
                             txn=(kind == "p" and bool(re.search(r"\b(COMMIT|ROLLBACK)\b", src, I))), path=r.search_path,
                             types=types or [], modes=modes or [], unit=r.unit, schema=r.schema, name=r.name)
        elif r.kind in ("view", "mview"):
            info[r.j] = dict(kind="view", ident=r.ident, unit=r.unit, schema=r.schema, name=r.name)
        elif r.kind == "table":
            info[r.j] = dict(kind="table", ident=r.ident, unit=r.unit, schema=r.schema, name=r.name)
        elif r.kind == "trigger":
            cur.execute("""SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
                           WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                             AND a.attgenerated = '' AND a.attidentity = '' ORDER BY attnum""", (r.ident,))
            cols = cur.fetchall()
            info[r.j] = dict(kind="trigger", ident=r.ident, tg=r.name, fn=r.result, cols=cols, unit=r.unit,
                             schema=r.schema, name=r.name)
    return info


# ---------------------------------------------------------------- генерація викликів
def arg_literal(t, rnd, mode):
    tl = t.lower()
    if re.search(r"int|serial", tl): v = str(rnd.choice([1, 2, 3, 5, 10, 0])); return f"{v}::{t}"
    if re.search(r"numeric|decimal|real|double|money", tl): return f"{rnd.choice(['1', '2.5', '10.75', '100'])}::{t}"
    if "timestamp" in tl: return f"'2024-03-15 10:30:00'::{t}"
    if tl.startswith("date"): return f"'2024-03-15'::{t}"
    if tl.startswith("bool"): return f"{rnd.choice(['true', 'false'])}::{t}"
    if tl == "refcursor": return f"'c{rnd.randint(0, 9999)}'::refcursor"
    if re.search(r"char|text|name", tl): return f"'{rnd.choice(['a1', 'abc2', 'X13', 'test4', 'j1n_25', '001'])}'::{t}"
    return f"NULL::{t}"


CANARY = {   # детерміновані аргументи тверджень за властивістю
    "null_semantics": {"text": "''", "int": "NULL", "num": "NULL"},
    "numeric_precision": {"num": "2.5", "int": "3", "text": "'a1'"},
    "temporal_semantics": {"int": "1", "text": "'a1'"},
}


def canary_literal(t, prop, k):
    tl = t.lower()
    c = CANARY.get(prop, {})
    if re.search(r"int|serial", tl): return f"{c.get('int', str(k + 1))}::{t}"
    if re.search(r"numeric|decimal|real|double|money", tl): return f"{c.get('num', '10.75')}::{t}"
    if "timestamp" in tl: return f"'2024-03-15 10:30:00'::{t}"
    if tl.startswith("date"): return f"'2024-03-15'::{t}"
    if tl.startswith("bool"): return f"true::{t}"
    if tl == "refcursor": return f"'canary{k}'::refcursor"
    if re.search(r"char|text|name", tl): return f"{c.get('text', repr('abc2'))}::{t}"
    return f"NULL::{t}"


def call_sql(o, lit):
    ins = [(t, m) for t, m in zip(o["types"], o["modes"]) if m in ("i", "b", "v")]
    args = []
    if o["kind"] == "procedure":
        for t, m in zip(o["types"], o["modes"]):
            args.append(lit(t, m) if m in ("i", "b") else f"NULL::{t}")
        name = re.sub(r"\(.*$", "", o["ident"])
        return f"CALL {name}({', '.join(args)})"
    args = [lit(t, m) for t, m in ins]
    name = re.sub(r"\(.*$", "", o["ident"])
    if o["retset"] or o["rettype"] in ("record",):
        return f"SELECT * FROM {name}({', '.join(args)}) LIMIT 200"
    return f"SELECT {name}({', '.join(args)})"


def trigger_sql(o, rnd, canary=False):
    cols = [(a, t) for a, t in o["cols"] if re.search(r"int|numeric|char|text|date|timestamp|bool", t, I)]
    if not cols:
        return None
    vals = []
    for k, (a, t) in enumerate(cols):
        vals.append(canary_literal(t, "", k) if canary else arg_literal(t, rnd, "i"))
    return 'INSERT INTO {} ({}) VALUES ({}) RETURNING *'.format(o["ident"], ", ".join(f'"{a}"' for a, _ in cols), ", ".join(vals))


def op_sql(o, rnd):
    if o["kind"] in ("function", "procedure"):
        return call_sql(o, lambda t, m: arg_literal(t, rnd, m))
    if o["kind"] == "view":
        return f"SELECT * FROM {o['ident']} LIMIT 200"
    if o["kind"] == "trigger":
        return trigger_sql(o, rnd)
    return None


def norm(v):
    if isinstance(v, datetime.datetime): return "ts:" + v.date().isoformat()
    if isinstance(v, datetime.date): return "d:" + v.isoformat()
    if isinstance(v, decimal.Decimal): return "n:" + format(v, "f")
    if isinstance(v, float): return "f:" + repr(round(v, 9))
    return type(v).__name__ + ":" + str(v)


def run_op(c, q, fetch_cursor=False, txn=False, path=None):
    """Виконання операції в транзакції з відкатом; повертає (ok, sqlstate, відбиток результату, мс).
    Процедури з COMMIT/ROLLBACK викликаються поза явною транзакцією (вимога PostgreSQL до CALL)."""
    t0 = time.perf_counter()
    cur = c.cursor()
    ok, state, h = True, "", ""
    try:
        if txn:
            cur.execute("SET statement_timeout = 1500")
            cur.execute(f"SET search_path = {path}")
        else:
            cur.execute("BEGIN")
            cur.execute("SET LOCAL statement_timeout = 1500")
        cur.execute(q)
        rows = cur.fetchall() if cur.description else []
        desc = [d.type_code for d in cur.description] if cur.description else []
        if fetch_cursor and rows and len(rows) == 1 and isinstance(rows[0][0], str) and desc and desc[0] == 1790:
            cur.execute(sql.SQL("FETCH ALL FROM {}").format(sql.Identifier(rows[0][0])))
            rows = cur.fetchall()
            desc = [d.type_code for d in cur.description] if cur.description else []
        h = hashlib.md5(json.dumps([desc, sorted([[norm(v) for v in r] for r in rows])]).encode()).hexdigest()
        shape = hashlib.md5(json.dumps([desc, len(rows)]).encode()).hexdigest()
    except psycopg.Error as e:
        ok, state = False, e.sqlstate or "XX000"
        h = shape = "ERR:" + state
    finally:
        if txn:
            try:
                cur.execute("RESET search_path")
            except psycopg.Error:
                pass
        else:
            try:
                cur.execute("ROLLBACK")
            except psycopg.Error:
                pass
    return ok, state, h, shape, (time.perf_counter() - t0) * 1000


# ---------------------------------------------------------------- мутації (дефекти міграції)
def body_mutations(src):
    m = []
    if re.search(r"\bIS\s+NULL\b", src, I): m.append(("null_semantics", lambda s: re.sub(r"\bIS\s+NULL\b", "= ''", s, count=1, flags=I)))
    elif re.search(r"\bCOALESCE\s*\(", src, I): m.append(("null_semantics", lambda s: re.sub(r"\bCOALESCE\s*\(", "NULLIF(", s, count=1, flags=I)))
    if re.search(r"\b(now\(\)|current_timestamp|clock_timestamp\(\)|localtimestamp)", src, I):
        m.append(("temporal_semantics", lambda s: re.sub(r"\b(now\(\)|current_timestamp|clock_timestamp\(\)|localtimestamp)", "current_date", s, flags=I)))
    elif re.search(r"\bcurrent_date\b", src, I):
        m.append(("temporal_semantics", lambda s: re.sub(r"\bcurrent_date\b", "(current_date + 1)", s, flags=I)))
    if re.search(r"\bnumeric\b(\s*\(\s*\d+\s*,\s*\d+\s*\))?", src, I):
        m.append(("numeric_precision", lambda s: re.sub(r"\bnumeric\b(\s*\(\s*\d+\s*,\s*\d+\s*\))?", "integer", s, flags=I)))
    return m


def plpgsql_insert(src, stmt):
    """Вставка оператора після першого BEGIN тіла plpgsql."""
    m = re.search(r"\$(\w*)\$(.*?)\bBEGIN\b", src, re.S | I)
    if not m:
        return None
    k = m.end()
    return src[:k] + f"\n  {stmt}\n" + src[k:]


def applicable(o, c):
    """Перелік (властивість, DDL) мутацій, застосовних до розгорнутого об'єкта."""
    out = []
    cur = c.cursor()
    if o["kind"] in ("function", "procedure"):
        cur.execute("SELECT pg_get_functiondef(%s)", (o["oid"],))
        src = cur.fetchone()[0]
        out.append(("availability", f"DROP ROUTINE {o['ident']} CASCADE"))
        if not o.get("txn"):
            out.append(("privilege_context", f"ALTER ROUTINE {o['ident']} SECURITY INVOKER"))
        if o["lang"] == "plpgsql":
            s2 = plpgsql_insert(src, "RAISE EXCEPTION USING ERRCODE = '0A000', MESSAGE = 'unsupported construct after migration';")
            if s2: out.append(("exec_errors", s2))
            s3 = plpgsql_insert(src, "PERFORM pg_sleep(0.04);")
            if s3: out.append(("latency", s3))
        for p, f in body_mutations(src):
            s4 = f(src)
            if s4 != src:
                out.append((p, s4))
    elif o["kind"] == "view":
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", (o["ident"],))
        d = cur.fetchone()[0].rstrip().rstrip(";")
        out.append(("result_cardinality", f"CREATE OR REPLACE VIEW {o['ident']} AS SELECT * FROM ({d}) q OFFSET 1"))
        out.append(("availability", f"DROP VIEW {o['ident']} CASCADE"))
    elif o["kind"] == "trigger":
        out.append(("trigger_firing", f'ALTER TABLE {o["ident"]} DISABLE TRIGGER "{o["tg"]}"'))
    elif o["kind"] == "table":
        tbl = o["name"]
        out.append(("identifier_resolution", f'ALTER TABLE {o["ident"]} RENAME TO "{tbl.upper()}_MIG"'))
    return out


# ---------------------------------------------------------------- телеметрія
class Telemetry:
    def __init__(self, db, info):
        self.c = conn(db, "collector")
        self.db = db
        self.info = info
        self.prev = {}
        self.logpos = {}
        for f in os.listdir(LOGDIR):
            if f.endswith(".csv"):
                self.logpos[f] = os.path.getsize(os.path.join(LOGDIR, f))
        self.qmap = {}
        self.ident_re = {j: re.escape(re.sub(r"\(.*$", "", o["ident"])) for j, o in info.items()}
        self.name_to_j = {}
        for j, o in info.items():
            self.name_to_j.setdefault(re.sub(r"\(.*$", "", o["ident"]).replace('"', "").lower(), []).append(j)
        self.fam_ms = {}

    def _timed(self, fam, q, args=None):
        t0 = time.perf_counter()
        r = self.c.execute(q, args).fetchall()
        self.fam_ms[fam] = self.fam_ms.get(fam, 0.0) + (time.perf_counter() - t0) * 1000
        return r

    def errors(self):
        """Нові рядки CSV-журналу сервера: помилки робочої бази з прив'язкою до об'єкта за текстом запиту."""
        t0 = time.perf_counter()
        res = []
        for f in sorted(os.listdir(LOGDIR)):
            if not f.endswith(".csv"):
                continue
            p = os.path.join(LOGDIR, f)
            pos = self.logpos.get(f, 0)
            with open(p, newline="", encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                data = fh.read()
                self.logpos[f] = fh.tell()
            for row in csv.reader(data.splitlines(True)):
                if len(row) < 23 or row[2] != self.db or row[11] != "ERROR":
                    continue
                text = (row[19] or "") + " " + (row[18] or "")
                js = set()
                for m in re.finditer(r"(u\d{4}\w*)\.\"?(\w+)", text):
                    js |= set(self.name_to_j.get(f"{m.group(1)}.{m.group(2)}".lower(), []))
                res.append(dict(app=row[22], state=row[12], objs=js))
        self.fam_ms["errors"] = self.fam_ms.get("errors", 0.0) + (time.perf_counter() - t0) * 1000
        return res

    def snapshot(self):
        self.c.execute("SELECT pg_stat_clear_snapshot()")
        s = {}
        s["fn"] = {r[0]: (r[1], r[2]) for r in self._timed("fn", "SELECT funcid, calls, self_time FROM pg_stat_user_functions")}
        q = self._timed("pgss", """SELECT queryid, query, calls, total_exec_time, rows FROM pg_stat_statements s
                                    JOIN pg_database d ON d.oid = s.dbid WHERE d.datname = %s AND s.toplevel""", (self.db,))
        agg = {}
        for qid, text, calls, tt, rows in q:
            if qid not in self.qmap:
                js = set()
                for m in re.finditer(r"(u\d{4}\w*)\.\"?(\w+)", text):
                    js |= set(self.name_to_j.get(f"{m.group(1)}.{m.group(2)}".lower(), []))
                self.qmap[qid] = js
            for j in self.qmap[qid]:
                a = agg.setdefault(j, [0, 0.0, 0])
                a[0] += calls; a[1] += tt; a[2] += rows
        s["pgss"] = agg
        s["tab"] = {r[0]: r[1] for r in self._timed("tab", "SELECT relid, n_tup_ins + n_tup_upd FROM pg_stat_user_tables")}
        cat = {}
        rows = self._timed("cat", """SELECT j, CASE WHEN k IN ('function','procedure') THEN to_regprocedure(i) IS NOT NULL
                                                 ELSE to_regclass(i) IS NOT NULL END,
                                            (SELECT prosecdef FROM pg_proc WHERE oid = to_regprocedure(i)),
                                            (SELECT has_function_privilege('app', to_regprocedure(i), 'EXECUTE')
                                               WHERE to_regprocedure(i) IS NOT NULL)
                                     FROM unnest(%s::int[], %s::text[], %s::text[]) AS x(j, i, k)""",
                           ([int(j) for j in self.info], [o["ident"] for o in self.info.values()],
                            [o["kind"] for o in self.info.values()]))
        for j, ex, sd, pr in rows:
            cat[j] = [ex, sd, pr, None]
        trg = self._timed("cat", """SELECT t.tgname, c.oid::regclass::text, t.tgenabled FROM pg_trigger t
                                    JOIN pg_class c ON c.oid = t.tgrelid WHERE NOT t.tgisinternal""")
        tg = {(a, b): e for a, b, e in trg}
        for j, o in self.info.items():
            if o["kind"] == "trigger":
                cat[j][3] = tg.get((o["tg"], o["ident"]), "missing")
        s["cat"] = cat
        s["db"] = self._timed("db", "SELECT xact_commit, xact_rollback FROM pg_stat_database WHERE datname = %s", (self.db,))[0]
        s["err"] = self.errors()
        return s


# ---------------------------------------------------------------- зонди
FAMILY = {"pg_log_errors": "errors", "pg_stat_statements": "pgss", "pg_stat_user_functions": "fn", "pg_stat_user_tables": "tab",
          "pg_catalog_objects": "cat", "role_table_grants": "cat", "pgaudit": "cat", "pg_log_statement": "pgss",
          "pg_stat_database_xact": "db", "data_assertion": "assert", "pg_sequences": "cat", "pg_cron_runs": "db",
          "pg_stat_activity_fdw": "db", "pg_log_notice": "errors"}


def window_stats(series, t, p):
    """Сума приростів за останні p кроків."""
    return sum(series[max(0, t - p + 1): t + 1])


def make_alarm_fn(kind, prop, sig, j, info):
    """Повертає функцію f(H, t, p, base) -> bool, де H — ряди телеметрії, base — словник базової лінії."""
    o = info.get(j) if j is not None else None

    if j is None:                                   # агреговані зонди рівня екземпляра
        def agg(H, t, p, base):
            x = window_stats(H["err_total"], t, p)
            if sig == "pg_catalog_objects":
                return H["n_exist"][t] < base.setdefault("n_exist", H["n_exist"][W - 1])
            if sig in ("pg_log_errors", "pg_stat_database_xact"):
                b = base.get("agg")
                return b is not None and x > b
            return False
        return agg

    if sig in ("pg_log_errors", "pg_log_notice") and prop in ("exec_errors", "error_handling", "identifier_resolution",
                                                             "refcursor_lifecycle", "privilege_context"):
        def f(H, t, p, base):
            x = window_stats(H["err"].get(j, [0] * (t + 1)), t, p)
            b = base.get("thr")
            return b is not None and x > b
        return f
    if sig in ("pg_stat_statements", "pg_stat_user_functions", "pg_log_statement"):
        def f(H, t, p, base):
            key = "pgss" if sig != "pg_stat_user_functions" else "fn"
            calls = window_stats(H[key + "_calls"].get(j, [0] * (t + 1)), t, p)
            inv = window_stats(H["inv"].get(j, [0] * (t + 1)), t, p)
            if prop in ("call_volume", "availability", "trigger_firing", "exec_errors", "txn_semantics", "dynamic_sql_safety",
                        "error_handling"):
                return inv >= 2 and calls == 0 and base.get("calls_ok", False)
            if prop == "latency":
                tt = window_stats(H[key + "_time"].get(j, [0] * (t + 1)), t, p)
                mu, sd = base.get("lat", (None, None))
                return mu is not None and calls > 0 and tt / calls > max(mu + 4 * sd, 2 * mu, mu + 5.0)
            if prop == "result_cardinality" and key == "pgss":
                rows = window_stats(H["pgss_rows"].get(j, [0] * (t + 1)), t, p)
                mu = base.get("rpc")
                return mu is not None and calls > 0 and abs(rows / calls - mu) > max(0.2 * mu, 0.5)
            return False
        return f
    if sig == "pg_stat_user_tables" and o is not None and o["kind"] == "trigger":
        def f(H, t, p, base):
            mod = window_stats(H["tab_mod"].get(j, [0] * (t + 1)), t, p)
            fc = window_stats(H["fn_calls"].get(j, [0] * (t + 1)), t, p)
            return mod >= 1 and fc == 0 and base.get("fires", False)
        return f
    if sig == "pg_catalog_objects":
        def f(H, t, p, base):
            c = H["cat"][t].get(j)
            if c is None:
                return False
            return (not c[0]) or (c[3] is not None and c[3] != base.setdefault("tg", H["cat"][W - 1][j][3]))
        return f
    if sig in ("role_table_grants", "pgaudit"):
        def f(H, t, p, base):
            c = H["cat"][t].get(j)
            if c is None:
                return False
            b = base.setdefault("priv", tuple(H["cat"][W - 1][j][:3]))
            return tuple(c[:3]) != b
        return f
    if sig == "data_assertion":
        def f(H, t, p, base):
            h = H["assert"].get((j, prop), {}).get(t)
            if h is None:
                return False
            ref = base.get("hashes")
            if ref is None:
                return False
            return (h[0] not in ref) if base.get("stable") else (h[1] not in base.get("shapes", set()))
        return f
    return lambda H, t, p, base: False


def calibrate(kind, prop, sig, j, H, p, base, info):
    """Базова лінія за кроками калібрування 1..W."""
    if j is None:
        xs = [window_stats(H["err_total"], t, p) for t in range(p - 1, W)]
        base["agg"] = max(xs) + 3 * (np.std(xs) + 1) if xs else None
        base["n_exist"] = H["n_exist"][W - 1]
        return
    if sig in ("pg_log_errors", "pg_log_notice"):
        e = H["err"].get(j, [0] * W)
        xs = [window_stats(e, t, p) for t in range(p - 1, W)]
        mu = float(np.mean(xs)) if xs else 0.0
        base["thr"] = max(xs) + (int(np.ceil(3 * np.sqrt(mu))) if mu > 0 else 0)   # чиста базова лінія: аномалія — будь-яка помилка
    elif sig in ("pg_stat_statements", "pg_stat_user_functions", "pg_log_statement"):
        key = "pgss" if sig != "pg_stat_user_functions" else "fn"
        cs = H[key + "_calls"].get(j, [0] * W)[:W]
        ts = H[key + "_time"].get(j, [0] * W)[:W]
        base["calls_ok"] = sum(cs) > 0
        per = [tt / cc for tt, cc in zip(ts, cs) if cc > 0]
        if per:
            base["lat"] = (float(np.mean(per)), float(np.std(per)))
        if key == "pgss":
            rs = H["pgss_rows"].get(j, [0] * W)[:W]
            rp = [r / cc for r, cc in zip(rs, cs) if cc > 0]
            if rp and np.std(rp) <= 0.1 * (np.mean(rp) + 1e-9):
                base["rpc"] = float(np.mean(rp))
    elif sig == "pg_stat_user_tables":
        base["fires"] = sum(H["fn_calls"].get(j, [0] * W)[:W]) > 0
    elif sig == "data_assertion":
        hs = [H["assert"].get((j, prop), {}).get(t) for t in range(W)]
        hs = [h for h in hs if h is not None]
        if hs:
            base["hashes"] = {h[0] for h in hs}
            base["shapes"] = {h[1] for h in hs}
            base["stable"] = len(base["hashes"]) == 1


# ---------------------------------------------------------------- один прогін
def run(seed, M, D):
    db = f"o2p_run{seed}"
    adm = conn("postgres", "admin")
    adm.execute(f"DROP DATABASE IF EXISTS {db}")
    adm.execute(f"CREATE DATABASE {db} TEMPLATE {TPL}")
    ac = conn(db, "admin")
    ac.execute("SELECT pg_stat_statements_reset()")
    ac.execute("SELECT pg_stat_reset()")
    info = introspect(ac, D)
    # конфігурації варіантів (той самий синтез, що й у 7.7.6)
    EA.PROBE_SINK = {}
    EA.VARIANTS = VARIANTS
    EA.run_seed(seed, M)
    cfg = {v: [(i, p, s, l, how) for (i, p, s, l, how) in EA.PROBE_SINK[(seed, v)] if i is None or i in info] for v in VARIANTS}
    union = {}
    for v, ps in cfg.items():
        for (i, p, s, l, how) in ps:
            union.setdefault((i, p, s), set()).add(PERIOD[l])
    rnd = random.Random(seed)
    rng = np.random.default_rng(seed + 4000)
    # навантаження: вектор використання одиниць — той самий, що в run_seed
    r0 = np.random.default_rng(seed)
    usage = np.minimum(r0.zipf(1.6, len(M["U"])).astype(float), 50)
    ops = [j for j, o in info.items() if o["kind"] in ("function", "procedure", "view", "trigger")]
    w = np.array([usage[info[j]["unit"]] for j in ops])
    w = w / w.sum()
    # дефекти: одиниці стенда за ризиком конструкцій (як inject_defects), мутація з урахуванням класу властивості
    U = M["U"]
    risk = (1 + 0.4 * U.n_direct + 1.0 * U.n_rewrite + 2.0 * U.n_noeq).to_numpy()
    units = sorted({o["unit"] for o in info.values()})
    pu = np.clip(EA.DEFECT_RATE * risk[units] / risk[units].mean(), 0, 0.95)
    hit = [u for u, pr in zip(units, pu) if rng.random() < pr]
    by_unit = {}
    for j, o in info.items():
        by_unit.setdefault(o["unit"], []).append(j)
    defects = []
    for u in hit:
        cand = []
        for j in by_unit[u]:
            for prop, ddl in applicable(info[j], ac):
                cand.append((j, prop, ddl))
        if not cand:
            continue
        wts = np.array([3.0 if EA.PROPS[p][1] in ("silent", "policy", "security") else 1.0 for _, p, _ in cand])
        j, prop, ddl = cand[rng.choice(len(cand), p=wts / wts.sum())]
        defects.append(dict(unit=u, j=j, prop=prop, ddl=ddl, t0=int(rng.integers(W + 5, T - 25)), applied=False,
                            t_act=None, kind=info[j]["kind"]))
    by_t0 = {}
    for d in defects:
        by_t0.setdefault(d["t0"], []).append(d)
    # підключення: навантаження, твердження, телеметрія
    wl = conn(db, "workload", "app")
    pr = conn(db, "probe", "app")
    tel = Telemetry(db, info)
    assert_keys = sorted({(i, p) for (i, p, s) in union if s == "data_assertion" and i is not None})
    H = {"err": {}, "err_total": [], "inv": {}, "pgss_calls": {}, "pgss_time": {}, "pgss_rows": {}, "fn_calls": {},
         "fn_time": {}, "tab_mod": {}, "cat": [], "n_exist": [], "assert": {}}
    prev = None
    assert_ms = {}
    wl_ms = []
    oid_of = {j: o.get("oid") for j, o in info.items()}
    trig_fn = {}
    for j, o in info.items():
        if o["kind"] == "trigger":
            x = ac.execute("SELECT tgfoid, tgrelid FROM pg_trigger WHERE tgname=%s AND tgrelid=%s::regclass",
                           (o["tg"], o["ident"])).fetchone()
            trig_fn[j] = x
    for t in range(T):
        for d in by_t0.get(t, []):
            try:
                ac.execute(d["ddl"])
                d["applied"] = True
            except psycopg.Error as e:
                d["err"] = (e.sqlstate or "") + " " + str(e).splitlines()[0][:120]
        # навантаження кроку
        t1 = time.perf_counter()
        inv = {}
        for j in rng.choice(ops, size=OPS_PER_STEP, p=w):
            q = op_sql(info[j], rnd)
            if q is None:
                continue
            inv[j] = inv.get(j, 0) + 1
            run_op(wl, q, fetch_cursor=True, txn=info[j].get("txn", False), path=info[j].get("path"))
        # операції подань/підпрограм одиниці «зачіпають» таблиці одиниці
        for j in list(inv):
            for k in by_unit[info[j]["unit"]]:
                if info[k]["kind"] == "table":
                    inv[k] = inv.get(k, 0) + 1
        wl.execute("SELECT pg_stat_force_next_flush()")
        wl.execute("SELECT 1")
        wl_ms.append((time.perf_counter() - t1) * 1000)
        for d in defects:
            if d["applied"] and d["t_act"] is None and t >= d["t0"] and inv.get(d["j"], 0) > 0:
                d["t_act"] = t
        # твердження
        for (j, p) in assert_keys:
            o = info[j]
            if o["kind"] in ("function", "procedure"):
                q = call_sql(o, lambda tt, m, p=p: canary_literal(tt, p, 0))
            elif o["kind"] == "view":
                q = f"SELECT * FROM {o['ident']} LIMIT 200"
            elif o["kind"] == "trigger":
                q = trigger_sql(o, rnd, canary=True)
            elif o["kind"] == "table":
                q = f"SELECT count(*) FROM {o['ident']}"
            else:
                q = None
            if q is None:
                continue
            ok, st, h, shape, ms = run_op(pr if o["kind"] != "table" else ac, q, fetch_cursor=True, txn=o.get("txn", False), path=o.get("path"))
            H["assert"].setdefault((j, p), {})[t] = (h, shape)
            assert_ms[(j, p)] = assert_ms.get((j, p), 0.0) + ms
        pr.execute("SELECT pg_stat_force_next_flush()")
        pr.execute("SELECT 1")
        time.sleep(0.05)
        s = tel.snapshot()
        # прирости
        for j, o in info.items():
            H["inv"].setdefault(j, [0] * t).append(inv.get(j, 0))
        def delta(cur, old):
            return cur - old if old is not None else 0
        for j, o in info.items():
            if o["kind"] in ("function", "procedure"):
                c = s["fn"].get(o["oid"], (0, 0.0))
                pv = prev["fn"].get(o["oid"], (0, 0.0)) if prev else (0, 0.0)
                H["fn_calls"].setdefault(j, [0] * t).append(c[0] - pv[0])
                H["fn_time"].setdefault(j, [0.0] * t).append(c[1] - pv[1])
            elif o["kind"] == "trigger" and trig_fn.get(j):
                fo, rel = trig_fn[j]
                c = s["fn"].get(fo, (0, 0.0)); pv = prev["fn"].get(fo, (0, 0.0)) if prev else (0, 0.0)
                H["fn_calls"].setdefault(j, [0] * t).append(c[0] - pv[0])
                m_ = s["tab"].get(rel, 0); pm = prev["tab"].get(rel, 0) if prev else 0
                H["tab_mod"].setdefault(j, [0] * t).append(m_ - pm)
            g = s["pgss"].get(j, [0, 0.0, 0]); pg_ = prev["pgss"].get(j, [0, 0.0, 0]) if prev else [0, 0.0, 0]
            H["pgss_calls"].setdefault(j, [0] * t).append(g[0] - pg_[0])
            H["pgss_time"].setdefault(j, [0.0] * t).append(g[1] - pg_[1])
            H["pgss_rows"].setdefault(j, [0] * t).append(g[2] - pg_[2])
        ecount = {}
        tot = 0
        for e in s["err"]:
            if e["app"] != "workload":
                continue
            tot += 1
            for j in e["objs"]:
                ecount[j] = ecount.get(j, 0) + 1
        for j in info:
            H["err"].setdefault(j, [0] * t).append(ecount.get(j, 0))
        H["err_total"].append(tot)
        H["cat"].append(s["cat"])
        H["n_exist"].append(sum(1 for v in s["cat"].values() if v[0]))
        prev = s
    # ------------------------------------------------------------ збереження телеметрії для офлайн-оцінювання детекторів
    events = [d for d in defects if d["applied"] and d["t_act"] is not None]
    fam_ms_step = {k: v / T for k, v in tel.fam_ms.items()}
    os.makedirs(os.path.join(OUT, "telemetry"), exist_ok=True)
    with open(os.path.join(OUT, "telemetry", f"H_seed{seed}.pkl"), "wb") as fh:
        pickle.dump(dict(seed=seed, T=T, H=H, cfg=cfg, defects=[{k: v for k, v in d.items() if k != "ddl"} for d in defects],
                         info={j: dict(unit=o["unit"], kind=o["kind"]) for j, o in info.items()}, by_unit=by_unit,
                         assert_ms=assert_ms, fam_ms_step=fam_ms_step, wl_ms=wl_ms), fh)
    # ------------------------------------------------------------ оцінювання варіантів
    rows, alarms_log = [], []
    fam_ms_step = {k: v / T for k, v in tel.fam_ms.items()}
    for v in VARIANTS:
        probes = cfg[v]
        alarms = []                                  # (t, j або None)
        cost_ms = 0.0
        fams = set()
        for (i, p, s_, l, how) in probes:
            per = PERIOD[l]
            fn = make_alarm_fn(None, p, s_, i, info)
            base = {}
            calibrate(None, p, s_, i, H, per, base, info)
            fams.add(FAMILY.get(s_, "db"))
            if s_ == "data_assertion" and i is not None:
                cost_ms += assert_ms.get((i, p), 0.0) / T / per
            last = -10 ** 6
            for t in range(W, T):
                if (t % per) != 0 or t - last < SUPPRESS:
                    continue
                try:
                    a = fn(H, t, per, base)
                except (KeyError, IndexError, TypeError, ZeroDivisionError):
                    a = False
                if a:
                    alarms.append((t, i, p, s_))
                    last = t
        cost_ms += sum(fam_ms_step.get(f, 0.0) for f in fams if f != "assert")
        # зіставлення тривог з дефектами
        tp = loc = 0
        delays = []
        used = set()
        det = {}
        for d in sorted(events, key=lambda d: d["t_act"]):
            unit_objs = set(by_unit[d["unit"]])
            hit = [a for a in alarms if a[0] >= d["t0"] and a[1] in unit_objs and (a[0], a[1], a[2], a[3]) not in used]
            hit_agg = [a for a in alarms if a[0] >= d["t0"] and a[1] is None and (a[0], a[1], a[2], a[3]) not in used]
            cands = sorted(hit + hit_agg, key=lambda a: a[0])
            if cands:
                a = cands[0]
                used.add((a[0], a[1], a[2], a[3]))
                tp += 1
                delays.append(max(0, a[0] - d["t_act"]))
                loc += int(a[1] == d["j"])
                det[id(d)] = a
        fp = sum(1 for a in alarms if (a[0], a[1], a[2], a[3]) not in used and not any(
            a[1] in set(by_unit[d["unit"]]) and a[0] >= d["t0"] for d in defects if d["applied"]))
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / len(events) if events else 0.0
        F1 = 2 * P * R / (P + R) if P + R else 0.0
        rows.append(dict(seed=seed, variant=v, probes=len(probes), probes_obj=sum(1 for x in probes if x[0] is not None),
                         events=len(events), TP=tp, FP=fp, P=P, R=R, F1=F1,
                         MTTD=float(np.mean(delays)) if delays else np.nan, LA=loc / len(events) if events else 0.0,
                         FAR=fp / (tp + fp) if tp + fp else 0.0, overhead_ms_step=cost_ms,
                         workload_ms_step=float(np.mean(wl_ms))))
        for d in events:
            a = det.get(id(d))
            alarms_log.append(dict(seed=seed, variant=v, unit=d["unit"], j=d["j"], prop=d["prop"], kind=d["kind"],
                                   t0=d["t0"], t_act=d["t_act"], detected=a is not None,
                                   t_det=a[0] if a else None, by_signal=a[3] if a else None,
                                   by_prop=a[2] if a else None, localized=(a is not None and a[1] == d["j"])))
    dfs = pd.DataFrame([dict(seed=seed, unit=d["unit"], j=d["j"], kind=d["kind"], prop=d["prop"], t0=d["t0"],
                             applied=d["applied"], t_act=d["t_act"], err=d.get("err", "")) for d in defects])
    for c in (wl, pr, ac):
        c.close()
    tel.c.close()
    adm.execute(f"DROP DATABASE IF EXISTS {db} WITH (FORCE)")
    adm.close()
    meta = dict(seed=seed, testbed_objects=len(info), op_objects=len(ops), units=len(units),
                defects=len(defects), applied=int(dfs.applied.sum()) if len(dfs) else 0, events=len(events),
                assert_probes=len(assert_keys), fam_ms_step=fam_ms_step, workload_ms_step=float(np.mean(wl_ms)))
    return rows, dfs, pd.DataFrame(alarms_log), meta


def main():
    M = EA.build_model()
    D = load_objects()
    allr, alld, alla, metas = [], [], [], []
    tag = os.environ.get("OPS_TAG", "")
    for s in SEEDS:
        t0 = time.perf_counter()
        r, d, a, meta = run(s, M, D)
        allr += r; alld.append(d); alla.append(a); metas.append(meta)
        print(f"seed {s}: {meta['events']} events, {meta['testbed_objects']} objects, {time.perf_counter() - t0:.0f} s", flush=True)
        pd.DataFrame(allr).to_csv(os.path.join(OUT, f"ops_runs{tag}.csv"), index=False)
        pd.concat(alld).to_csv(os.path.join(OUT, f"ops_defects{tag}.csv"), index=False)
        pd.concat(alla).to_csv(os.path.join(OUT, f"ops_alarms{tag}.csv"), index=False)
        json.dump(metas, open(os.path.join(OUT, f"ops_meta{tag}.json"), "w"), indent=1, default=str)
    R = pd.DataFrame(allr)
    pd.set_option("display.width", 220)
    print(R.groupby("variant")[["probes_obj", "events", "P", "R", "F1", "MTTD", "LA", "FAR", "overhead_ms_step"]].mean()
          .reindex(VARIANTS).round(3).to_string())


if __name__ == "__main__":
    main()
