# -*- coding: utf-8 -*-
"""Етапи 1–2 наскрізної перевірки (підрозділ 7.7.6): еволюційна подія і дрейф.

Еволюційна подія — реальна міграція Oracle PL/SQL -> PostgreSQL з еталонного
набору O2P_GOLDEN_TESTSET_v03 (1802 одиниці міграції, вихідний Oracle-код і
еталонний PostgreSQL-код). Детерміновано (без ВММ) будуються структурні моделі
G0 (Oracle) і G1 (PostgreSQL): об'єкти, їх типи, приналежність до пакетів,
залежності та конструкції; виконується зіставлення об'єктів і обчислюються
часткові дрейфи за сімома вимірами, для яких у коді є артефакти:
конфігураційний, топологічний, рольовий, політик, архітектурний, семантичний,
безпековий. Контекстний і цільовий виміри не обчислюються: відповідних
артефактів у наборі немає.

Результати: e2e_objects.csv, e2e_units.csv, e2e_drift_summary.csv.
"""
import os, re, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

FLAGS = re.I | re.S
ID = r'"?([\w$#]+)"?(?:\s*\.\s*"?([\w$#]+)"?)?'

# --- конструкції та їх класи складності (за реєстром pipeline/no_equivalent.py
#     проєкту oracle-spec-project, доповнено безпековими й транзакційними) ---
ORA_CONSTRUCTS = {
    "nvl": r"\bNVL2?\s*\(", "decode": r"\bDECODE\s*\(", "sysdate": r"\bSYS(DATE|TIMESTAMP)\b",
    "dual": r"\bFROM\s+DUAL\b", "varchar2": r"\bVARCHAR2\b", "nextval_seq": r"\.\s*NEXTVAL\b",
    "rownum": r"\bROWNUM\b", "connect_by": r"\bCONNECT\s+BY\b", "outer_join_plus": r"\(\+\)",
    "number_type": r"\bNUMBER\b", "lob_type": r"\b[BC]LOB\b", "merge": r"\bMERGE\s+INTO\b",
    "bulk_collect": r"\bBULK\s+COLLECT\b|\bFORALL\b", "utl_package": r"\bUTL_\w+",
    "dbms_package": r"\bDBMS_(?!OUTPUT)\w+", "dbms_output": r"\bDBMS_OUTPUT\b",
    "autonomous_tx": r"AUTONOMOUS_TRANSACTION", "dynamic_sql": r"EXECUTE\s+IMMEDIATE|\bDBMS_SQL\b|OPEN\s+\w+\s+FOR\s+(?!SELECT)\w+",
    "txn_control": r"\b(COMMIT|ROLLBACK)\b", "exception": r"\bEXCEPTION\b", "cursor": r"\bCURSOR\b|SYS_REFCURSOR|REF\s+CURSOR",
    "dblink": r"\b\w+@\w+", "type_anchor": r"%(ROW)?TYPE", "raise_app": r"RAISE_APPLICATION_ERROR",
    "job": r"DBMS_(JOB|SCHEDULER)", "grant": r"\bGRANT\b", "revoke": r"\bREVOKE\b",
}
DIFFICULTY = {
    "nvl": "DIRECT", "decode": "DIRECT", "sysdate": "DIRECT", "dual": "DIRECT", "varchar2": "DIRECT",
    "nextval_seq": "DIRECT", "type_anchor": "DIRECT", "grant": "DIRECT", "revoke": "DIRECT",
    "rownum": "REWRITE", "connect_by": "REWRITE", "outer_join_plus": "REWRITE", "number_type": "REWRITE",
    "lob_type": "REWRITE", "merge": "REWRITE", "bulk_collect": "REWRITE", "dynamic_sql": "REWRITE",
    "txn_control": "REWRITE", "exception": "REWRITE", "cursor": "REWRITE", "raise_app": "REWRITE",
    "dbms_output": "REWRITE",
    "utl_package": "NO_EQUIVALENT", "dbms_package": "NO_EQUIVALENT", "autonomous_tx": "NO_EQUIVALENT",
    "dblink": "NO_EQUIVALENT", "job": "NO_EQUIVALENT",
}
# конструкції, наслідки заміни яких змінюють семантику без синтаксичної помилки
SILENT_SEMANTIC = {"nvl", "sysdate", "varchar2", "number_type", "rownum", "merge", "txn_control",
                   "exception", "outer_join_plus", "decode"}

ORA_KIND = [
    ("package_body", r"\bPACKAGE\s+BODY\s+" + ID), ("package", r"\bPACKAGE\s+(?!BODY)" + ID),
    ("trigger", r"\bTRIGGER\s+" + ID), ("mview", r"\bMATERIALIZED\s+VIEW\s+" + ID),
    ("view", r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:FORCE\s+)?(?:EDITIONABLE\s+)?(?:NO\s*FORCE\s+)?VIEW\s+" + ID),
    ("table", r"\bCREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+" + ID), ("sequence", r"\bCREATE\s+SEQUENCE\s+" + ID),
    ("index", r"\bCREATE\s+(?:UNIQUE\s+|BITMAP\s+)?INDEX\s+" + ID), ("type", r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+)?TYPE\s+" + ID),
    ("synonym", r"\bSYNONYM\s+" + ID),
]
PG_KIND = [
    ("trigger", r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\s+" + ID), ("mview", r"\bMATERIALIZED\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?" + ID),
    ("view", r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP\w*\s+)?(?:RECURSIVE\s+)?VIEW\s+" + ID),
    ("table", r"\bCREATE\s+(?:UNLOGGED\s+|(?:GLOBAL\s+|LOCAL\s+)?TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + ID),
    ("sequence", r"\bCREATE\s+SEQUENCE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + ID), ("index", r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?" + ID),
    ("type", r"\bCREATE\s+TYPE\s+" + ID), ("schema", r"\bCREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?" + ID),
]
ROUTINE = r"(?:^|[\s;(])(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?)?(PROCEDURE|FUNCTION)\s+" + ID
GRANT = r"\bGRANT\s+([\w\s,]+?)\s+ON\s+(?:TABLE\s+|FUNCTION\s+|PROCEDURE\s+|ROUTINE\s+|SEQUENCE\s+|SCHEMA\s+|TYPE\s+|TABLESPACE\s+)?" + ID + r"(?:\s*\([^)]*\))?\s+TO\s+([\w\s,\"]+)"
GRANT_ROLE = r"\bGRANT\s+([\w\s,]+?)\s+TO\s+([\w\s,\"]+)"
REFS = r"\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM|REFERENCES|ON)\s+" + ID
CONFIG_TOKENS = r"\b(VARCHAR2?|NVARCHAR2?|CHAR|TEXT|NUMBER|NUMERIC|INTEGER|INT|BIGINT|SMALLINT|DECIMAL|FLOAT|DOUBLE|REAL|DATE|TIMESTAMP|INTERVAL|BOOLEAN|CLOB|BLOB|BYTEA|RAW|LONG|XMLTYPE|JSONB?|TABLESPACE|PCTFREE|STORAGE|PARTITION|LOGGING|NOLOGGING|COMPRESS|INITRANS|CACHE|NOCACHE|CYCLE|NOCYCLE|INCREMENT|MAXVALUE|MINVALUE|DEFAULT|NOT\s+NULL|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\b"
KW = set("""select from where and or not null into values insert update delete set join on as is in
begin end loop if then else elsif case when exit return returns language plpgsql declare
cursor open close fetch for commit rollback exception others raise table view dual
group by order having union all distinct exists like between count sum max min avg""".split())


def strip_comments(s):
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    return re.sub(r"--[^\n]*", " ", s)


def nm(a, b):
    """Нормалізоване ім'я (без схеми, у нижньому регістрі) та схема."""
    return ((b or a).lower(), (a.lower() if b else ""))


def routines(code):
    out = []
    for m in re.finditer(ROUTINE, code, FLAGS):
        n, sch = nm(m.group(2), m.group(3))
        if n not in KW:
            out.append((m.group(1).lower(), n, sch, m.start()))
    return out


def parse_oracle(code):
    code = strip_comments(code)
    objs, pkgs = [], []
    for kind, pat in ORA_KIND:
        for m in re.finditer(pat, code, FLAGS):
            n, sch = nm(m.group(1), m.group(2))
            if n in KW:
                continue
            if kind in ("package", "package_body"):
                pkgs.append((n, m.start(), kind))
            objs.append(dict(kind=kind, name=n, schema=sch, pkg=""))
    # підпрограми: всередині пакета — члени пакета
    pk_spans = sorted(pkgs, key=lambda x: x[1])
    seen = set()
    for k, n, sch, pos in routines(code):
        pkg = ""
        for pn, ps, _ in pk_spans:
            if ps < pos:
                pkg = pn
        key = (k, n, pkg)
        if key in seen:
            continue
        seen.add(key)
        objs.append(dict(kind=k, name=n, schema=sch, pkg=pkg))
    if not objs and code.strip():
        objs.append(dict(kind="anonymous", name="", schema="", pkg=""))
    return objs


def parse_pg(code):
    code = strip_comments(code)
    objs = []
    for kind, pat in PG_KIND:
        for m in re.finditer(pat, code, FLAGS):
            n, sch = nm(m.group(1), m.group(2))
            if n not in KW:
                objs.append(dict(kind=kind, name=n, schema=sch, pkg=""))
    seen = set()
    for k, n, sch, pos in routines(code):
        if (k, n) in seen:
            continue
        seen.add((k, n))
        objs.append(dict(kind=k, name=n, schema=sch, pkg=""))
    if not objs and code.strip():
        objs.append(dict(kind="anonymous", name="", schema="", pkg=""))
    return objs


def refs(code):
    code = strip_comments(code)
    return {nm(m.group(1), m.group(2))[0] for m in re.finditer(REFS, code, FLAGS)} - KW


def grants(code):
    code = strip_comments(code)
    g = set()
    for m in re.finditer(GRANT, code, FLAGS):
        obj = nm(m.group(2), m.group(3))[0]
        for p in re.split(r"[\s,]+", m.group(1).strip()):
            for r in re.split(r"[\s,]+", m.group(4).strip().strip('"')):
                if p and r:
                    g.add((p.lower(), obj, r.lower().strip('"')))
    roles = {(m.group(1).strip().lower(), m.group(2).strip().lower())
             for m in re.finditer(GRANT_ROLE, code, FLAGS) if " ON " not in m.group(0).upper()}
    return g, roles


def jacc(a, b):
    a, b = set(a), set(b)
    return 0.0 if not a and not b else 1 - len(a & b) / len(a | b)


def ms_dist(a, b):
    """Відстань між мультимножинами токенів (зважений Жаккар)."""
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    keys = set(ca) | set(cb)
    if not keys:
        return 0.0
    return 1 - sum(min(ca[k], cb[k]) for k in keys) / sum(max(ca[k], cb[k]) for k in keys)


def constructs(code):
    code = strip_comments(code)
    return {c for c, p in ORA_CONSTRUCTS.items() if re.search(p, code, FLAGS)}


def privilege_context(code, dialect):
    """Контекст привілеїв виконання підпрограм: definer / invoker."""
    code = strip_comments(code)
    if dialect == "ora":
        if re.search(r"AUTHID\s+CURRENT_USER", code, FLAGS):
            return "invoker"
        return "definer" if re.search(r"\b(PROCEDURE|FUNCTION|PACKAGE)\b", code, FLAGS) else ""
    if re.search(r"SECURITY\s+DEFINER", code, FLAGS):
        return "definer"
    return "invoker" if re.search(r"\b(PROCEDURE|FUNCTION)\b", code, FLAGS) else ""


def dynamic_sql_profile(code, dialect):
    """Безпековий профіль динамічного SQL: кількість викликів і частка без зв'язування."""
    code = strip_comments(code)
    if dialect == "ora":
        calls = re.findall(r"EXECUTE\s+IMMEDIATE\s+([^;]+);", code, FLAGS)
    else:
        calls = re.findall(r"\bEXECUTE\s+(?!PROCEDURE|FUNCTION)([^;]+);", code, FLAGS)
    unsafe = sum(1 for c in calls if "||" in c and not re.search(r"\bUSING\b|format\s*\(|quote_(ident|literal|nullable)", c, re.I))
    return len(calls), unsafe


def match_objects(o_objs, p_objs):
    """Зіставлення об'єктів G0 -> G1: за ім'ям і типом, за ім'ям, за ім'ям члена пакета."""
    pairs, used = [], set()
    pidx = {}
    for j, p in enumerate(p_objs):
        pidx.setdefault(p["name"], []).append(j)
    for i, o in enumerate(o_objs):
        if o["kind"] in ("package", "package_body"):
            pairs.append((i, None, "dissolved"))
            continue
        cand = [j for j in pidx.get(o["name"], []) if j not in used]
        same = [j for j in cand if p_objs[j]["kind"] == o["kind"]]
        if same:
            j, how = same[0], "same"
        elif cand:
            j, how = cand[0], "kind_changed"
        else:
            pairs.append((i, None, "lost"))
            continue
        used.add(j)
        if o["pkg"]:
            how = "unpacked" if how == "same" else "unpacked_kind_changed"
        pairs.append((i, j, how))
    new = [j for j in range(len(p_objs)) if j not in used]
    return pairs, new


def main():
    d = pd.read_csv(DATA)
    obj_rows, unit_rows = [], []
    for uid, r in d.iterrows():
        ora, pg = str(r.input_db_query), str(r.output_db_query)
        oo, po = parse_oracle(ora), parse_pg(pg)
        pairs, new = match_objects(oo, po)
        cons = constructs(ora)
        # --- часткові дрейфи одиниці міграції ---
        cfg_o = [t.upper().split()[0] for t in re.findall(CONFIG_TOKENS, strip_comments(ora), FLAGS)]
        cfg_p = [t.upper().split()[0] for t in re.findall(CONFIG_TOKENS, strip_comments(pg), FLAGS)]
        d_cfg = ms_dist(cfg_o, cfg_p)
        ro, rp = refs(ora), refs(pg)
        d_top = jacc(ro, rp)
        go, rlo = grants(ora)
        gp, rlp = grants(pg)
        d_role = jacc(rlo | {(g[0], g[2]) for g in go}, rlp | {(g[0], g[2]) for g in gp})
        pc_o, pc_p = privilege_context(ora, "ora"), privilege_context(pg, "pg")
        d_pol = jacc({x for x in go}, {x for x in gp}) if (go or gp) else 0.0
        d_pol = max(d_pol, 1.0 if (pc_o and pc_p and pc_o != pc_p) else 0.0)
        n_obj = max(len(oo), 1)
        changed = sum(1 for _, _, h in pairs if h != "same")
        d_arch = changed / n_obj
        sem = [c for c in cons if c in SILENT_SEMANTIC or DIFFICULTY.get(c) in ("REWRITE", "NO_EQUIVALENT")]
        d_sem = min(1.0, sum(1.0 if DIFFICULTY.get(c) == "NO_EQUIVALENT" else 0.5 if c in SILENT_SEMANTIC else 0.3
                             for c in sem) / 3.0)
        dyn_o, uns_o = dynamic_sql_profile(ora, "ora")
        dyn_p, uns_p = dynamic_sql_profile(pg, "pg")
        sec_terms = []
        if pc_o and pc_p and pc_o != pc_p:
            sec_terms.append(1.0)
        if dyn_o or dyn_p:
            sec_terms.append(abs(uns_o / max(dyn_o, 1) - uns_p / max(dyn_p, 1)))
        if "dblink" in cons or "utl_package" in cons:
            sec_terms.append(0.5)
        d_sec = max(sec_terms) if sec_terms else 0.0
        unit_rows.append(dict(unit=uid, source=r.source, lines=r.line_count, n_obj_ora=len(oo), n_obj_pg=len(po),
                              n_same=sum(h == "same" for _, _, h in pairs),
                              n_kind_changed=sum("kind_changed" in h for _, _, h in pairs),
                              n_unpacked=sum(h.startswith("unpacked") for _, _, h in pairs),
                              n_dissolved=sum(h == "dissolved" for _, _, h in pairs),
                              n_lost=sum(h == "lost" for _, _, h in pairs), n_new=len(new),
                              constructs=";".join(sorted(cons)),
                              n_direct=sum(DIFFICULTY.get(c) == "DIRECT" for c in cons),
                              n_rewrite=sum(DIFFICULTY.get(c) == "REWRITE" for c in cons),
                              n_noeq=sum(DIFFICULTY.get(c) == "NO_EQUIVALENT" for c in cons),
                              priv_ora=pc_o, priv_pg=pc_p, dyn_ora=dyn_o, dyn_unsafe_ora=uns_o,
                              dyn_pg=dyn_p, dyn_unsafe_pg=uns_p, grants_ora=len(go), grants_pg=len(gp),
                              d_configuration=d_cfg, d_topological=d_top, d_role=d_role, d_policy=d_pol,
                              d_architectural=d_arch, d_semantic=d_sem, d_security=d_sec))
        for i, j, how in pairs:
            o = oo[i]
            p = po[j] if j is not None else dict(kind="", name="", schema="")
            obj_rows.append(dict(unit=uid, ora_kind=o["kind"], ora_name=o["name"], ora_schema=o["schema"], ora_pkg=o["pkg"],
                                 pg_kind=p["kind"], pg_name=p["name"], pg_schema=p["schema"], match=how,
                                 constructs=";".join(sorted(cons)), refs=len(ro), priv_ora=pc_o, priv_pg=pc_p))
        for j in new:
            p = po[j]
            obj_rows.append(dict(unit=uid, ora_kind="", ora_name="", ora_schema="", ora_pkg="", pg_kind=p["kind"],
                                 pg_name=p["name"], pg_schema=p["schema"], match="new", constructs=";".join(sorted(cons)),
                                 refs=len(rp), priv_ora=pc_o, priv_pg=pc_p))
    U = pd.DataFrame(unit_rows)
    O = pd.DataFrame(obj_rows)
    U.to_csv(os.path.join(OUT, "e2e_units.csv"), index=False)
    O.to_csv(os.path.join(OUT, "e2e_objects.csv"), index=False)
    dims = ["d_configuration", "d_topological", "d_role", "d_policy", "d_architectural", "d_semantic", "d_security"]
    S = []
    for c in dims:
        x = U[c]
        S.append(dict(dimension=c[2:], mean=x.mean(), median=x.median(), p90=x.quantile(0.9),
                      share_nonzero=(x > 0).mean(), units_nonzero=int((x > 0).sum())))
    S = pd.DataFrame(S)
    S.to_csv(os.path.join(OUT, "e2e_drift_summary.csv"), index=False)
    corr = U[dims].corr(method="spearman")
    corr.to_csv(os.path.join(OUT, "e2e_drift_corr.csv"))
    stats = dict(units=len(U), objects_ora=int((O.ora_kind != "").sum()), objects_pg=int((O.pg_kind != "").sum()),
                 match=O.match.value_counts().to_dict(), kinds_ora=O[O.ora_kind != ""].ora_kind.value_counts().to_dict(),
                 kinds_pg=O[O.pg_kind != ""].pg_kind.value_counts().to_dict(),
                 priv_change=int(((U.priv_ora == "definer") & (U.priv_pg == "invoker")).sum()),
                 routines_ora=int(U.priv_ora.ne("").sum()), dyn_units_ora=int((U.dyn_ora > 0).sum()),
                 dyn_unsafe_ora=int(U.dyn_unsafe_ora.sum()), dyn_ora=int(U.dyn_ora.sum()),
                 dyn_unsafe_pg=int(U.dyn_unsafe_pg.sum()), dyn_pg=int(U.dyn_pg.sum()),
                 grants_ora=int(U.grants_ora.sum()), grants_pg=int(U.grants_pg.sum()),
                 difficulty_units=dict(direct_only=int(((U.n_direct > 0) & (U.n_rewrite == 0) & (U.n_noeq == 0)).sum()),
                                       rewrite=int(((U.n_rewrite > 0) & (U.n_noeq == 0)).sum()), noeq=int((U.n_noeq > 0).sum())))
    json.dump(stats, open(os.path.join(OUT, "e2e_structure_stats.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    print(S.round(3).to_string())


if __name__ == "__main__":
    main()
