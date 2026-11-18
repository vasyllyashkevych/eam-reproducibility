# -*- coding: utf-8 -*-
"""Контекстний і цільовий виміри дрейфу на реальних даних міграції (доповнення до o2p_structure.py).

Контекстний дрейф (2.13): D_ctx = conf · частка порушених контекстних припущень, на які спирається
одиниця. Припущення виявляються в коді Oracle регулярними правилами; фактичне значення кожного
параметра в цільовому середовищі вимірюється виконанням контрольного запиту на розгорнутому
PostgreSQL 17 (стенд ops/), значення Oracle — за документованою поведінкою Oracle Database 19c.

Цільовий дрейф: модель цілей одиниці — специфікаційні атрибути перевірки з лабораторного проєкту
daryna_tukalo/oracle-spec-project (pipeline/profiles.py: профілі table/view/routine/trigger/orchestrator,
умовна ціль безпеки динамічного SQL). Профіль обчислюється окремо для коду Oracle і PostgreSQL;
D_goal = (додані + вилучені + цілі зі зміненим критерієм досягнення) / |G_O ∪ G_P|.

Вихід: out/e2e_ctx_checks.csv, out/e2e_units_9d.csv, out/e2e_drift9_summary.csv.
"""
import os, re, sys
import numpy as np, pandas as pd
try:
    import psycopg
except ImportError:          # offline mode (EAM_PG_OFFLINE=1) does not need a database driver
    psycopg = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv")
SPEC = os.path.join(HERE, "..", "third_party", "oracle_spec_pipeline")
sys.path.insert(0, SPEC)
from pipeline import profiles as PR          # noqa: E402  (реальний класифікатор лабораторії, без змін)

DSN = os.environ.get("OPS_DSN", "host=localhost port=55432 user=postgres dbname=o2p")
I = re.IGNORECASE

# ---------------------------------------------------------------- контекстні припущення
# ключ: (опис, правило виявлення залежності в коді Oracle, значення Oracle (документоване), контрольний запит PG)
CTX = {
    "empty_string_is_null": ("порожній рядок тотожний NULL", r"''|\bNVL2?\s*\(|\bIS\s+(NOT\s+)?NULL\b",
                             "true", "SELECT ('' IS NULL)::text"),
    "concat_ignores_null": ("конкатенація з NULL не дає NULL", r"\|\|", "true", "SELECT (('a' || NULL) IS NOT NULL)::text"),
    "date_keeps_time": ("тип DATE зберігає час", r"\bDATE\b|\bSYSDATE\b", "true",
                        "SELECT ('2020-01-01 10:30'::date::timestamp <> '2020-01-01'::timestamp)::text"),
    "nls_date_format": ("формат дати за замовчуванням DD-MON-RR", r"\bTO_CHAR\s*\(\s*[\w.]+\s*\)|\bTO_DATE\s*\(\s*[^,()]+\)",
                        "DD-MON-RR", "SELECT current_setting('DateStyle')"),
    "clock_statement_time": ("SYSDATE — час виконання оператора", r"\bSYSDATE\b|\bSYSTIMESTAMP\b", "true",
                             None),     # вимірюється окремо в межах транзакції
    "upper_identifier_fold": ("неекрановані ідентифікатори приводяться до верхнього регістру", r'"[A-Z][A-Z0-9_$#]*"', "true",
                              None),
    "decimal_division": ("ділення цілих дає дробовий результат", r"\b(PLS_INTEGER|BINARY_INTEGER|INTEGER|INT)\b[\s\S]*?\w\s*/\s*\w",
                         "true", "SELECT ((1/2) <> 0)::text"),
    "ddl_autocommit": ("DDL неявно фіксує транзакцію", r"EXECUTE\s+IMMEDIATE\s+'\s*(CREATE|DROP|ALTER|TRUNCATE)|^\s*(TRUNCATE)\b",
                       "true", None),
    "commit_in_routine": ("COMMIT/ROLLBACK допустимі в будь-якій підпрограмі", r"\b(COMMIT|ROLLBACK)\b", "true", None),
    "no_data_found_raises": ("SELECT INTO без рядків породжує виключення", r"\bSELECT\b[^;]*?\bINTO\b", "true", None),
    "binary_sort": ("двійкове впорядкування рядків (NLS_SORT=BINARY)", r"\bORDER\s+BY\b", "true",
                    "SELECT (('a' COLLATE \"default\") > ('B' COLLATE \"default\"))::text"),
    # припущення, що зберігаються (контроль того, що міра не завжди дорівнює 1)
    "read_committed_default": ("рівень ізоляції за замовчуванням READ COMMITTED", r"\b(INSERT|UPDATE|DELETE|MERGE)\b",
                               "read committed", "SELECT current_setting('default_transaction_isolation')"),
    "nulls_last_asc": ("NULL останні при ORDER BY ASC", r"\bORDER\s+BY\b", "true",
                       "SELECT ((SELECT x FROM (VALUES (1),(NULL)) v(x) ORDER BY x LIMIT 1) IS NOT NULL)::text"),
    "like_case_sensitive": ("LIKE чутливий до регістру", r"\bLIKE\b", "true", "SELECT (NOT ('A' LIKE 'a'))::text"),
    "unique_multi_null": ("UNIQUE допускає кілька NULL", r"\bUNIQUE\b", "true", None),
}


def live_checks(conn):
    """Виконання контрольних запитів на розгорнутому PostgreSQL; повертає фактичне значення параметра."""
    res = {}
    cur = conn.cursor()
    for k, (_, _, _, q) in CTX.items():
        if q:
            cur.execute(q)
            res[k] = str(cur.fetchone()[0])
    # час «зараз» у межах транзакції
    with conn.transaction():
        cur.execute("SELECT now()"); a = cur.fetchone()[0]
        cur.execute("SELECT pg_sleep(0.02)")
        cur.execute("SELECT now()"); b = cur.fetchone()[0]
    res["clock_statement_time"] = str(a != b).lower()
    # згортання регістру ідентифікаторів
    with conn.transaction():
        cur.execute('CREATE TEMP TABLE ctx_fold (x int)')
        cur.execute("SELECT count(*) FROM pg_class WHERE relname = 'CTX_FOLD'")
        res["upper_identifier_fold"] = str(cur.fetchone()[0] == 1).lower()
        cur.execute("DROP TABLE ctx_fold")
    # транзакційність DDL
    try:
        with conn.transaction():
            cur.execute("CREATE TABLE ctx_ddl (x int)")
            raise RuntimeError("rollback")
    except RuntimeError:
        pass
    cur.execute("SELECT to_regclass('ctx_ddl') IS NOT NULL")
    res["ddl_autocommit"] = str(cur.fetchone()[0]).lower()
    # COMMIT у функції
    cur.execute("CREATE OR REPLACE FUNCTION pg_temp.ctx_c() RETURNS int LANGUAGE plpgsql AS $$BEGIN COMMIT; RETURN 1; END$$")
    try:
        with conn.transaction():
            cur.execute("SELECT pg_temp.ctx_c()")
        res["commit_in_routine"] = "true"
    except psycopg.Error:
        res["commit_in_routine"] = "false"
    # SELECT INTO без рядків
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


# ---------------------------------------------------------------- цілі (специфікаційні атрибути)
def goals(code):
    """Профіль і множина цілей перевірки за класифікатором лабораторії (без LLM)."""
    c = strip_comments(code)
    # у знеособленому коді виробничої БД оголошення часто без CREATE; нормалізація лише для класифікації
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
    """Цілі, для яких змінився критерій досягнення (перевірювана умова)."""
    ch = set()
    if output_channel(ora, True) != output_channel(pg, False):
        ch.add(("Regression", "result_parity"))
    if unit_row.n_kind_changed + unit_row.n_unpacked > 0:
        ch.add(("Smoke", "critical_calls"))           # інша форма виклику (CALL / SELECT, ім'я поза пакетом)
    if re.search(r"RAISE_APPLICATION_ERROR|\bPRAGMA\s+EXCEPTION_INIT\b|\bWHEN\s+(NO_DATA_FOUND|TOO_MANY_ROWS|DUP_VAL_ON_INDEX)\b",
                 ora, I):
        ch.add(("Unit", "exception_paths"))           # числові коди ORA-20xxx -> SQLSTATE
    if unit_row.n_unpacked + unit_row.n_dissolved > 0:
        ch.add(("Compatibility", "package_mapping"))  # стан і простір імен пакета не зберігаються
    if re.search(r"''|\bNVL2?\s*\(", ora, I):
        ch.add(("Compatibility", "null_behavior"))    # '' ≡ NULL має бути сформульовано явно
    return ch


def main():
    raw = pd.read_csv(DS)
    U = pd.read_csv(os.path.join(OUT, "e2e_units.csv"), keep_default_na=False)
    if os.environ.get("EAM_PG_OFFLINE") == "1":   # use the checks recorded on the PostgreSQL 17.11 testbed
        rec = pd.read_csv(os.path.join(HERE, "..", "recorded", "e2e_ctx_checks.csv"), dtype=str, keep_default_na=False)
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
        conf = 1.0                                   # обидві сторони перевірено: PG — виконанням, Oracle — документацією
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
