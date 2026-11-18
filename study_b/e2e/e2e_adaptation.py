# -*- coding: utf-8 -*-
"""Етапи 3–5 наскрізної перевірки (підрозділ 7.7.6): адаптація моніторингу.

Вхід — структурні моделі G0/G1 і часткові дрейфи з o2p_structure.py (реальний
код міграції Oracle -> PostgreSQL). Для кожного з 40 зерен:
  1) синтезується зріла конфігурація моніторингу M0 для Oracle-версії;
  2) застосовується еволюційна подія (міграція) і п'ять варіантів реакції:
     S0 — статичний моніторинг (M0 без адаптації + типовий шаблон PostgreSQL);
     S1 — часткова адаптація (заміна джерел за таблицею відповідностей і
          перепризначення зондів за ідентифікаторами, без перегляду властивостей);
     S2 — повна регенерація без локалізації дрейфу (онтологія + тензорний ГА
          для всієї конфігурації);
     S3 — запропонований метод (дрейф -> локалізація -> онтологічне виведення
          властивостей -> тензорний ГА лише для зміненої області -> валідація);
     S3-O — S3 без онтологічного контролю (лексичне виведення властивостей,
          без перевірки сумісності властивість–сигнал);
  3) після події моделюється експлуатація (T кроків) з дефектами міграції,
     частка яких калібрована за звітами лабораторії (семантична точність
     найкращого агентного конвеєра 73 %, тобто 27 % одиниць з дефектом);
  4) обчислюються PCR, PCRw, TPP, MRSR, VR, F1, P, R, MTTD, LA, FAR, ACS, OH,
     час адаптації і кількість обчислень функції пристосованості.
Результати: e2e_runs.csv, e2e_summary.csv, e2e_tests.csv, e2e_cost.csv.

Розширений прогін (E2E_VARIANTS, E2E_TAG=_ext) додає відтворення ключових механізмів найближчих
аналогів на тих самих даних, бюджеті й оцінювачі:
     A-RB — архітектурна самоадаптація з фіксованими тактиками (Rainbow [284, 285]): обмеження
            «кожен компонент G1 спостерігається» і тактики за типом компонента;
     A-RX — моделі відображення (reflexion models [403, 404]): перенесення M0 за структурним
            відображенням G0 -> G1 без перегляду властивостей;
     A-AM — адаптивний моніторинг (Ehlers et al. [208]): зміна деталізації наявних зондів у
            компонентах з ознаками відхилення, без нових властивостей і джерел;
     A-RV — верифікація під час виконання з фіксованою специфікацією [129, 130]: властивості
            вихідної специфікації повторно інструментуються на новому коді;
     S3-9D — S3 з локалізацією за дев'ятьма вимірами (додано контекстний і цільовий, o2p_ctx_goal.py).
"""
import os, time, json
import numpy as np, pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon, mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RUN_TAG = os.environ.get("E2E_TAG", "")
SEEDS = range(1, int(os.environ.get("E2E_SEEDS", 40)) + 1)
T = 240                       # кроків експлуатації після переходу
DEFECT_RATE = float(os.environ.get("E2E_DEFECT_RATE", 0.27))            # 1 - 0,73 (дволанковий агентний конвеєр, звіт O2P self-healing)
BUDGET_FRAC = float(os.environ.get("E2E_BUDGET_FRAC", 0.55))            # бюджет накладних витрат від вартості повного інструментування рівня 2
DRIFT_THR = 0.10              # поріг значущості часткового дрейфу для локалізації (S3)
FA_OBJ, FA_AGG = float(os.environ.get("E2E_FA_OBJ", 0.03)), 15.0   # інтенсивність хибних епізодів для об'єктних і агрегованих зондів
WARMUP = int(float(os.environ.get("E2E_WARMUP", 20)))                   # кроків калібрування базової лінії нового зонда
STALE_FA = 3.0                # множник хибних тривог зонда із застарілою базовою лінією
DIMS = ["configuration", "topological", "role", "policy", "architectural", "semantic", "security"]
DIMS9 = DIMS + ["contextual", "goal"]
VARIANTS = os.environ.get("E2E_VARIANTS", "S0,S1,S2,S3,S3-O").split(",")
# вплив виміру дрейфу на контрольовані властивості (локалізація зміненої області в S3)
IMPACT = {
    "configuration": {"numeric_precision", "null_semantics", "availability"},
    "topological":   {"result_cardinality", "latency", "availability"},
    "role":          {"privilege_context"},
    "policy":        {"privilege_context"},
    "architectural": {"call_volume", "latency", "exec_errors", "availability", "error_handling"},
    "semantic":      {"null_semantics", "temporal_semantics", "numeric_precision", "result_cardinality",
                      "txn_semantics", "error_handling"},
    "security":      {"dynamic_sql_safety", "privilege_context", "remote_dependency"},
    # виміри, обчислені в o2p_ctx_goal.py (використовуються лише варіантом S3-9D)
    "contextual":    {"null_semantics", "temporal_semantics", "numeric_precision", "txn_semantics", "error_handling"},
    "goal":          {"result_cardinality", "error_handling", "call_volume", "exec_errors", "availability"},
}
# тактики архітектурної самоадаптації за типом компонента (A-RB): (властивість, джерело)
TACTICS = {"procedure": [("exec_errors", "pg_log_errors"), ("latency", "pg_stat_statements")],
           "function": [("exec_errors", "pg_log_errors"), ("latency", "pg_stat_statements")],
           "view": [("latency", "pg_stat_statements"), ("availability", "pg_catalog_objects")],
           "mview": [("latency", "pg_stat_statements"), ("availability", "pg_catalog_objects")],
           "table": [("availability", "pg_catalog_objects")],
           "trigger": [("trigger_firing", "pg_stat_user_tables")],
           "sequence": [("sequence_monotonic", "pg_sequences")],
           "anonymous": [("exec_errors", "pg_log_errors")]}
# лексична евристика сумісності без онтології: властивість -> джерела зі спільним ключовим словом
LEXICAL = {
    "exec_errors": {"pg_log_errors"}, "error_handling": {"pg_log_errors"}, "latency": {"pg_stat_statements"},
    "call_volume": {"pg_stat_user_functions", "pg_stat_statements"}, "availability": {"pg_catalog_objects"},
    "txn_semantics": {"pg_stat_database_xact"}, "privilege_context": {"role_table_grants"},
    "dynamic_sql_safety": {"pg_log_statement"}, "trigger_firing": {"pg_stat_user_tables", "pg_stat_user_functions"},
    "sequence_monotonic": {"pg_sequences"}, "remote_dependency": {"pg_stat_activity_fdw"},
    "scheduled_job": {"pg_cron_runs"}, "diagnostic_output": {"pg_log_notice"},
}

# ---------------------------------------------------------------- онтологія
# властивість: (вага критичності, клас: loud/silent/policy/security/ops, джерела Oracle, джерела PostgreSQL)
PROPS = {
    "exec_errors":        (0.9, "loud",     ["dba_errors_alert"], ["pg_log_errors"]),
    "latency":            (0.5, "ops",      ["v_sqlstats"], ["pg_stat_statements"]),
    "call_volume":        (0.3, "ops",      ["v_sqlstats"], ["pg_stat_user_functions", "pg_stat_statements"]),
    "availability":       (0.6, "ops",      ["dba_objects_status"], ["pg_catalog_objects"]),
    "txn_semantics":      (0.8, "silent",   ["v_transaction", "unified_audit"], ["pg_log_statement", "pg_stat_database_xact"]),
    "error_handling":     (0.7, "loud",     ["dba_errors_alert"], ["pg_log_errors"]),
    "null_semantics":     (0.7, "silent",   ["data_assertion"], ["data_assertion"]),
    "temporal_semantics": (0.6, "silent",   ["data_assertion"], ["data_assertion"]),
    "numeric_precision":  (0.6, "silent",   ["data_assertion"], ["data_assertion"]),
    "result_cardinality": (0.8, "silent",   ["data_assertion"], ["data_assertion", "pg_stat_statements"]),
    "privilege_context":  (0.9, "policy",   ["unified_audit", "dba_tab_privs"], ["pgaudit", "role_table_grants"]),
    "dynamic_sql_safety": (1.0, "security", ["unified_audit"], ["pgaudit", "pg_log_statement"]),
    "trigger_firing":     (0.7, "loud",     ["dba_triggers_audit"], ["pg_stat_user_tables", "pg_log_statement"]),
    "sequence_monotonic": (0.5, "ops",      ["user_sequences"], ["pg_sequences"]),
    "remote_dependency":  (0.8, "loud",     ["v_dblink"], ["pg_stat_activity_fdw"]),
    "scheduled_job":      (0.7, "loud",     ["dba_scheduler_runs"], ["pg_cron_runs"]),
    "diagnostic_output":  (0.3, "ops",      ["dbms_output_buffer"], ["pg_log_notice"]),
    # відомі відмінності платформ, відсутні в онтології методу (лише в еталоні оцінювання)
    "identifier_resolution": (0.6, "loud",  [], ["pg_log_errors"]),
    "refcursor_lifecycle":   (0.5, "loud",  [], ["pg_log_errors", "pg_stat_activity_fdw"]),
}
GT_ONLY = {"identifier_resolution", "refcursor_lifecycle"}
PNAMES = list(PROPS)
PIDX = {p: i for i, p in enumerate(PNAMES)}

# джерело: (платформа, об'єктна гранулярність (трасованість), допустимі типи об'єктів, базова вартість, потужність, рівень шуму)
ROUT = {"procedure", "function"}
ALLK = {"procedure", "function", "trigger", "view", "mview", "table", "sequence", "anonymous"}
SIG = {
    "v_sqlstats":         ("ora", True, ROUT | {"view", "mview", "anonymous"}, 1.0, 0.75, 0.010),
    "dba_errors_alert":   ("ora", True, ALLK, 0.6, 0.85, 0.006),
    "dba_objects_status": ("ora", True, ALLK, 0.3, 0.90, 0.002),
    "v_transaction":      ("ora", False, ALLK, 0.5, 0.55, 0.020),
    "unified_audit":      ("ora", True, ALLK, 1.6, 0.80, 0.008),
    "dba_tab_privs":      ("ora", True, ALLK, 0.3, 0.70, 0.003),
    "dba_triggers_audit": ("ora", True, {"trigger"}, 0.8, 0.80, 0.006),
    "user_sequences":     ("ora", True, {"sequence", "table", "procedure", "function", "trigger", "anonymous"}, 0.2, 0.75, 0.002),
    "v_dblink":           ("ora", False, ALLK, 0.4, 0.70, 0.015),
    "dba_scheduler_runs": ("ora", True, ALLK, 0.4, 0.85, 0.004),
    "dbms_output_buffer": ("ora", True, ROUT | {"trigger", "anonymous"}, 0.5, 0.60, 0.010),
    "data_assertion":     ("both", True, ALLK, 1.2, 0.80, 0.006),
    "pg_stat_statements": ("pg", True, ROUT | {"view", "mview", "anonymous"}, 0.9, 0.75, 0.010),
    "pg_stat_user_functions": ("pg", True, ROUT, 0.4, 0.70, 0.006),
    "pg_log_errors":      ("pg", True, ALLK, 0.6, 0.85, 0.006),
    "pg_log_statement":   ("pg", True, ALLK, 2.0, 0.80, 0.012),
    "pg_stat_database_xact": ("pg", False, ALLK, 0.2, 0.50, 0.020),
    "pgaudit":            ("pg", True, ALLK, 1.6, 0.80, 0.008),
    "role_table_grants":  ("pg", True, ALLK, 0.3, 0.70, 0.003),
    "pg_stat_user_tables": ("pg", True, {"table", "trigger"}, 0.3, 0.65, 0.008),
    "pg_sequences":       ("pg", True, {"sequence", "table", "procedure", "function", "trigger", "anonymous"}, 0.2, 0.75, 0.002),
    "pg_stat_activity_fdw": ("pg", False, ALLK, 0.4, 0.60, 0.015),
    "pg_cron_runs":       ("pg", True, ALLK, 0.4, 0.85, 0.004),
    "pg_log_notice":      ("pg", True, ROUT | {"trigger", "anonymous"}, 0.4, 0.60, 0.010),
    "pg_catalog_objects": ("pg", True, ALLK, 0.3, 0.90, 0.002),
}
SNAMES = list(SIG)
SIDX = {s: i for i, s in enumerate(SNAMES)}
# таблиця відповідностей джерел для часткової адаптації (типова для перенесення інструментів)
REMAP = {"v_sqlstats": "pg_stat_statements", "dba_errors_alert": "pg_log_errors", "dba_objects_status": "pg_catalog_objects",
         "v_transaction": "pg_stat_database_xact", "unified_audit": "pg_log_statement", "dba_tab_privs": "role_table_grants",
         "user_sequences": "pg_sequences", "dbms_output_buffer": "pg_log_notice", "data_assertion": "data_assertion",
         "dba_triggers_audit": None, "v_dblink": None, "dba_scheduler_runs": None}
# сигнали, прив'язані до відбитка виклику (зміна типу підпрограми ламає прив'язку)
FINGERPRINT = {"pg_stat_statements", "v_sqlstats"}
LEVEL_COST = np.array([0.0, 1.0, 2.0, 4.0])
LEVEL_SPEED = np.array([0.0, 0.22, 0.42, 0.68])
LEVEL_FA = np.array([0.0, 0.8, 1.0, 1.5])
ORA_SPECIFIC_SQL = {"nvl", "sysdate", "rownum", "decode", "dual", "outer_join_plus", "connect_by"}
MONITORED = ALLK
PROBE_SINK = None             # стенд ops/: якщо словник — зберігаються конфігурації варіантів {(зерно, варіант): зонди}


def derive(kind, cons, priv_change, quoted, ontology, era):
    """Виведення контрольованих властивостей об'єкта.

    ontology: 'gt' — еталон оцінювання; 'method' — онтологія методу;
    'lexical' — без онтології (лише явні ключові слова)."""
    P = set()
    if kind in ROUT | {"trigger", "anonymous"}:
        P |= {"exec_errors"}
    if kind in ROUT | {"view", "mview", "anonymous"}:
        P |= {"latency"}
    if kind in ROUT:
        P |= {"call_volume"}
    if kind in {"table", "view", "mview", "sequence"} | ROUT:
        P |= {"availability"}
    if kind == "trigger":
        P |= {"trigger_firing"}
    if kind == "sequence" or "nextval_seq" in cons:
        P |= {"sequence_monotonic"}
    explicit = {"dynamic_sql": "dynamic_sql_safety", "exception": "error_handling", "raise_app": "error_handling",
                "txn_control": "txn_semantics", "autonomous_tx": "txn_semantics", "job": "scheduled_job",
                "dblink": "remote_dependency", "utl_package": "remote_dependency", "dbms_output": "diagnostic_output",
                "grant": "privilege_context", "revoke": "privilege_context"}
    if kind != "table" or cons & {"grant", "revoke"}:
        P |= {explicit[c] for c in cons if c in explicit}
    if era == "post" and ontology in ("gt", "method") and kind != "sequence":
        if cons & {"nvl", "varchar2", "decode"}:
            P.add("null_semantics")
        if "sysdate" in cons:
            P.add("temporal_semantics")
        if "number_type" in cons and kind != "index":
            P.add("numeric_precision")
        if cons & {"rownum", "connect_by", "outer_join_plus", "merge"} or kind in {"view", "mview"}:
            P.add("result_cardinality")
        if priv_change and kind in ROUT:
            P.add("privilege_context")
        if kind in ROUT and cons & {"txn_control"}:
            P.add("txn_semantics")
    if era == "post" and ontology == "gt":
        if quoted and kind != "sequence":
            P.add("identifier_resolution")
        if "cursor" in cons and kind in ROUT:
            P.add("refcursor_lifecycle")
    if era == "pre":
        P &= {p for p in PROPS if p not in GT_ONLY}
    return P


def compatible(p, s, kind, platform):
    plat, gran, kinds, *_ = SIG[s]
    srcs = PROPS[p][2] if platform == "ora" else PROPS[p][3]
    return s in srcs and kind in kinds and plat in (platform, "both")


# ---------------------------------------------------------------- модель
def build_model():
    O = pd.read_csv(os.path.join(OUT, "e2e_objects.csv"), keep_default_na=False)
    U = pd.read_csv(os.path.join(OUT, "e2e_units.csv"), keep_default_na=False)
    raw = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv"))
    quoted = raw.input_db_query.fillna("").str.contains(r'"[A-Za-z_]\w*"', regex=True).to_numpy()
    dims = ["d_configuration", "d_topological", "d_role", "d_policy", "d_architectural", "d_semantic", "d_security"]
    U["drift"] = U[dims].max(axis=1)
    affected = {r.unit: set().union(*[IMPACT[d] for d in DIMS if getattr(r, "d_" + d) > DRIFT_THR])
                for r in U.itertuples()}
    affected9 = dict(affected)
    p9 = os.path.join(OUT, "e2e_units_9d.csv")
    if os.path.exists(p9):
        U9 = pd.read_csv(p9, keep_default_na=False)
        affected9 = {r.unit: set().union(*[IMPACT[d] for d in DIMS9 if getattr(r, "d_" + d) > DRIFT_THR])
                     for r in U9.itertuples()}
    cons = {r.unit: set(filter(None, r.constructs.split(";"))) for r in U.itertuples()}
    pchg = {r.unit: (r.priv_ora == "definer" and r.priv_pg == "invoker") for r in U.itertuples()}
    pre, post = [], []          # слоти (об'єкт, властивість)
    obj_pre, obj_post = [], []
    for r in O.itertuples():
        if r.ora_kind in MONITORED:
            obj_pre.append(dict(unit=r.unit, kind=r.ora_kind, key=(r.ora_pkg + "." if r.ora_pkg else "") + r.ora_name,
                                match=r.match, pg_kind=r.pg_kind, pg_name=r.pg_name))
        if r.pg_kind in MONITORED:
            obj_post.append(dict(unit=r.unit, kind=r.pg_kind, key=r.pg_name, match=r.match,
                                 ora_key=(r.ora_pkg + "." if r.ora_pkg else "") + r.ora_name, ora_kind=r.ora_kind))
    for i, o in enumerate(obj_pre):
        for p in sorted(derive(o["kind"], cons[o["unit"]], False, False, "method", "pre")):
            pre.append((i, p))
    slots = {}
    for ont in ("gt", "method", "lexical"):
        s = []
        for i, o in enumerate(obj_post):
            for p in sorted(derive(o["kind"], cons[o["unit"]], pchg[o["unit"]], quoted[o["unit"]], ont, "post")):
                s.append((i, p))
        slots[ont] = s
    return dict(O=O, U=U, cons=cons, obj_pre=obj_pre, obj_post=obj_post, pre=pre, slots=slots,
                drift=U.set_index("unit")["drift"].to_dict(), dims=dims, affected=affected, affected9=affected9)


# ---------------------------------------------------------------- тензорний ГА
def candidates(slots, objs, platform, check_compat):
    """Для кожного слота — допустимі джерела (з онтологією) або всі об'єктні джерела платформи (без неї)."""
    C = []
    for i, p in slots:
        k = objs[i]["kind"]
        if check_compat:
            c = [SIDX[s] for s in SNAMES if compatible(p, s, k, platform)]
        else:                          # без онтології: ключові слова, без обмежень на тип об'єкта
            c = [SIDX[s] for s in sorted(LEXICAL.get(p, ()))]
        C.append(c)
    return C


def ga_synthesize(slots, objs, usage, platform, budget, rng, check_compat=True, pop=48, gens=120, fixed_cost=0.0):
    """Тензорна хромосома: для кожного слота (об'єкт × властивість) — джерело сигналу і рівень вибірки.
    Схрещування блоками за одиницями міграції зберігає змістовні підтензори."""
    n = len(slots)
    if n == 0:
        return np.zeros(0, int), np.zeros(0, int), 0
    C = candidates(slots, objs, platform, check_compat)
    maxc = max(len(c) for c in C) or 1
    cand = np.full((n, maxc), -1)
    ncand = np.array([len(c) for c in C])
    for j, c in enumerate(C):
        cand[j, :len(c)] = c
    w = np.array([PROPS[p][0] for _, p in slots]) * np.array([usage[objs[i]["unit"]] for i, _ in slots])
    base = np.array([[SIG[SNAMES[s]][3] if s >= 0 else 0 for s in row] for row in cand])
    powr = np.array([[SIG[SNAMES[s]][4] if s >= 0 else 0 for s in row] for row in cand])
    trac = np.array([[1.0 if s >= 0 and SIG[SNAMES[s]][1] else 0.0 for s in row] for row in cand])
    unit = np.array([objs[i]["unit"] for i, _ in slots])
    _, blk = np.unique(unit, return_inverse=True)
    nb = blk.max() + 1
    has = ncand > 0
    W = w.sum()

    def fitness(S, L):
        rows = np.arange(n)
        on = (L > 0) & has
        b = base[rows, S] * LEVEL_COST[L] * on
        cost = fixed_cost + b.sum(axis=-1)
        cov = (w * on).sum(-1) / W
        tr = (w * on * trac[rows, S]).sum(-1) / W
        tim = (w * on * powr[rows, S] * LEVEL_SPEED[L]).sum(-1) / W
        over = np.maximum(0, cost - budget) / budget
        return 0.45 * cov + 0.30 * tr + 0.25 * tim - 2.0 * over

    S = (rng.random((pop, n)) * np.maximum(ncand, 1)).astype(int)
    L = rng.integers(0, 4, (pop, n))
    # евристична особина: найдешевше джерело, рівень 2, у порядку спадання ваги до вичерпання бюджету
    h_s = np.argmin(np.where(cand >= 0, base, 1e9), axis=1)
    h_l = np.zeros(n, int)
    order = np.argsort(-w / (base[np.arange(n), h_s] + 1e-9))
    spent = fixed_cost
    for j in order:
        c = base[j, h_s[j]] * LEVEL_COST[2]
        if has[j] and spent + c <= budget:
            h_l[j] = 2
            spent += c
    S[0], L[0] = h_s, h_l
    evals = 0
    F = np.array([fitness(S[k], L[k]) for k in range(pop)])
    evals += pop
    pm = 2.0 / n
    for g in range(gens):
        idx = rng.integers(0, pop, (pop, 2))
        par = np.where(F[idx[:, 0]] > F[idx[:, 1]], idx[:, 0], idx[:, 1])
        mates = par[rng.permutation(pop)]
        mask_b = rng.random((pop, nb)) < 0.5
        mask = mask_b[:, blk]
        S2 = np.where(mask, S[par], S[mates])
        L2 = np.where(mask, L[par], L[mates])
        mut = rng.random((pop, n)) < pm
        S2 = np.where(mut, (rng.random((pop, n)) * np.maximum(ncand, 1)).astype(int), S2)
        mut = rng.random((pop, n)) < pm * 2
        L2 = np.where(mut, np.clip(L2 + rng.choice([-1, 1], (pop, n)), 0, 3), L2)
        F2 = np.array([fitness(S2[k], L2[k]) for k in range(pop)])
        evals += pop
        allS, allL, allF = np.vstack([S, S2]), np.vstack([L, L2]), np.concatenate([F, F2])
        keep = np.argsort(-allF)[:pop]
        S, L, F = allS[keep], allL[keep], allF[keep]
    best = 0
    sig = np.where(has, cand[np.arange(n), S[best]], -1)
    lev = np.where(has, L[best], 0)
    return sig, lev, evals


# ---------------------------------------------------------------- конфігурації
def probe_table(slots, objs, sig, lev, platform_objs="post"):
    rows = []
    for (i, p), s, l in zip(slots, sig, lev):
        if s >= 0 and l > 0:
            rows.append((i, p, SNAMES[s], int(l)))
    return rows


def evaluate_config(probes, M, ont_slots, usage):
    """Покриття і трасованість за еталонним набором слотів (онтологія 'gt')."""
    objs = M["obj_post"]
    valid = {}
    for (i, p, s, l, how) in probes:
        if i is None:
            continue
        ok = compatible(p, s, objs[i]["kind"], "pg")
        if ok:
            key = (i, p)
            tr = SIG[s][1]
            if key not in valid or (tr and not valid[key][0]) or l > valid[key][1]:
                valid[key] = (tr, l, s, how)
    # агреговані зонди рівня екземпляра (без прив'язки до об'єкта) дають покриття класу властивості без трасованості
    agg = {p for (i, p, s, l, how) in probes if i is None}
    gt = ont_slots["gt"]
    J = len(gt)
    w = np.array([PROPS[p][0] for _, p in gt])
    cov = np.array([(1.0 if (i, p) in valid or p in agg else 0.0) for i, p in gt])
    tr = np.array([(1.0 if (i, p) in valid and valid[(i, p)][0] else 0.0) for i, p in gt])
    return dict(PCR=cov.mean(), PCRw=(w * cov).sum() / w.sum(), TPP=tr.mean()), valid, agg


def config_cost(probes):
    return sum(SIG[s][3] * LEVEL_COST[l] for (_, _, s, l, _) in probes)


# ---------------------------------------------------------------- експлуатація з дефектами
def inject_defects(M, rng, era):
    """Дефекти міграції: імовірність одиниці залежить від класів складності конструкцій."""
    U = M["U"]
    risk = 1 + 0.4 * U.n_direct + 1.0 * U.n_rewrite + 2.0 * U.n_noeq
    if era == "pre":                       # експлуатаційні збої до міграції (рівномірніші)
        risk = 1 + 0.2 * U.n_rewrite + 0.3 * U.n_noeq
    pu = np.clip(DEFECT_RATE * risk / risk.mean(), 0, 0.95).to_numpy()
    hit = rng.random(len(U)) < pu
    objs = M["obj_post"] if era == "post" else M["obj_pre"]
    slots = M["slots"]["gt"] if era == "post" else M["pre"]
    by_unit = {}
    for (i, p) in slots:
        by_unit.setdefault(objs[i]["unit"], []).append((i, p))
    defects = []
    for u in np.where(hit)[0]:
        cand = by_unit.get(u)
        if not cand:
            continue
        # властивості, пов'язані з ризиковими конструкціями, мають більшу ймовірність
        wts = np.array([3.0 if PROPS[p][1] in ("silent", "policy", "security") else 1.0 for _, p in cand])
        i, p = cand[rng.choice(len(cand), p=wts / wts.sum())]
        defects.append((i, p, u))
    return defects


def simulate(defects, valid, agg, probes, usage, rng):
    """Подієве оцінювання: P, R, F1, MTTD, LA, FAR."""
    tp = loc = 0
    delays = []
    events = 0
    for (i, p, u) in defects:
        lam = min(0.5, 0.02 * usage[u])
        ta = t_act = int(rng.geometric(lam))
        if ta >= T - 1:
            continue                       # дефект не проявився за горизонт спостереження
        events += 1
        key = (i, p)
        q, local = 0.0, False
        if key in valid:
            tr, l, s, st = valid[key]
            q, local = SIG[s][4] * LEVEL_SPEED[l], tr
            if st == "fresh":
                ta = max(ta, WARMUP)           # новий зонд ще калібрує базову лінію
        elif p in agg:
            q = 0.06
        if q <= 0:
            continue
        dt = int(rng.geometric(q)) - 1
        if ta + dt < T:
            tp += 1
            delays.append(ta + dt - t_act)
            loc += int(local)
    # хибні тривоги: епізоди з вікном пригнічення 10 кроків
    fa_rate = 0.0
    for (i, p, s, l, how) in probes:
        fa_rate += SIG[s][5] * LEVEL_FA[l] * (FA_AGG if i is None else FA_OBJ) * (STALE_FA if how == "stale" else 1.0)
    fp = rng.poisson(fa_rate * T / 10.0)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / events if events else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0
    return dict(P=P, R=R, F1=F1, MTTD=np.mean(delays) if delays else np.nan, LA=loc / events if events else 0.0,
                FAR=fp / (tp + fp) if tp + fp else 0.0, events=events, TP=tp, FP=fp)


# ---------------------------------------------------------------- варіанти
def run_seed(seed, M):
    rng = np.random.default_rng(seed)
    U = M["U"]
    usage = rng.zipf(1.6, len(U)).astype(float)
    usage = np.minimum(usage, 50)
    usage = dict(enumerate(usage / usage.mean()))
    objs_pre, objs_post = M["obj_pre"], M["obj_post"]
    # --- M0: зріла конфігурація Oracle-версії
    full_cost_pre = sum(min(SIG[s][3] for s in SNAMES if compatible(p, s, objs_pre[i]["kind"], "ora")) * LEVEL_COST[2]
                        for i, p in M["pre"] if any(compatible(p, s, objs_pre[i]["kind"], "ora") for s in SNAMES))
    sig0, lev0, _ = ga_synthesize(M["pre"], objs_pre, usage, "ora", BUDGET_FRAC * full_cost_pre, rng)
    M0 = [(i, p, SNAMES[s], int(l)) for (i, p), s, l in zip(M["pre"], sig0, lev0) if s >= 0 and l > 0]
    # якість M0 до події (для ACS)
    v0 = {}
    for (i, p, s, l) in M0:
        v0[(i, p)] = (SIG[s][1], l, s, "transferred")
    d_pre = inject_defects(M, np.random.default_rng(seed + 1000), "pre")
    q_pre = simulate(d_pre, v0, set(), [(i, p, s, l, "transferred") for (i, p, s, l) in M0], usage, np.random.default_rng(seed + 2000))
    # --- відповідність об'єктів G0 -> G1
    post_by = {}
    for j, o in enumerate(objs_post):
        post_by.setdefault((o["unit"], o["key"], o["kind"]), j)
    name_by = {}
    for j, o in enumerate(objs_post):
        name_by.setdefault((o["unit"], o["key"]), j)
    struct_map = {}                           # структурне зіставлення (етап 2 методу)
    for j, o in enumerate(objs_post):
        if o["ora_key"]:
            struct_map[(o["unit"], o["ora_key"])] = j
    full_cost_post = sum(min(SIG[s][3] for s in SNAMES if compatible(p, s, objs_post[i]["kind"], "pg")) * LEVEL_COST[2]
                         for i, p in M["slots"]["gt"] if any(compatible(p, s, objs_post[i]["kind"], "pg") for s in SNAMES))
    budget = BUDGET_FRAC * full_cost_post
    # обов'язкові для відновлення шляхи: слоти еталона, що були покриті до події, + нові слоти
    pre_cov = {(objs_pre[i]["unit"], objs_pre[i]["key"], p) for (i, p, s, l) in M0}
    required = set()
    for (j, p) in M["slots"]["gt"]:
        o = objs_post[j]
        if (o["unit"], o["ora_key"], p) in pre_cov or p not in derive(o.get("ora_kind") or "", M["cons"][o["unit"]], False, False, "method", "pre"):
            required.add((j, p))
    out = []
    template = [(None, "exec_errors", "pg_log_errors", 1, "tmpl"), (None, "txn_semantics", "pg_stat_database_xact", 1, "tmpl"),
                (None, "availability", "pg_catalog_objects", 1, "tmpl"), (None, "remote_dependency", "pg_stat_activity_fdw", 1, "tmpl")]

    def remap(m0, rebinding):
        """Перенесення зондів M0 на G1: заміна джерела і перепризначення об'єкта."""
        res, attempts = [], 0
        for (i, p, s, l) in m0:
            o = objs_pre[i]
            s2 = REMAP.get(s, None) if s != "data_assertion" else "data_assertion"
            attempts += 1
            if s2 is None:
                continue
            if rebinding == "identifier":
                j = post_by.get((o["unit"], o["key"], o["kind"]))
                if j is None and s2 not in FINGERPRINT:
                    j = name_by.get((o["unit"], o["key"]))
            else:
                j = struct_map.get((o["unit"], o["key"]))
            if j is None:
                continue
            if s2 == "data_assertion" and M["cons"][o["unit"]] & ORA_SPECIFIC_SQL and rebinding == "identifier":
                continue                      # твердження з Oracle-специфічним SQL не виконується в PostgreSQL
            res.append((j, p, s2, l, "remap"))
        return res, attempts

    gt_slots = M["slots"]
    def greedy_fill(base_probes, extra, budget_left):
        """Додавання зондів у порядку спадання ваги використання до вичерпання бюджету."""
        extra = sorted(extra, key=lambda k: -usage[objs_post[k[0]]["unit"]] * PROPS[k[1]][0])
        res, spent = list(base_probes), config_cost(base_probes)
        for k in extra:
            c = SIG[k[2]][3] * LEVEL_COST[k[3]]
            if spent + c <= budget_left:
                res.append(k)
                spent += c
        return res

    for variant in VARIANTS:
        t0 = time.perf_counter()
        evals = 0
        if variant == "S0":
            probes = []
            for (i, p, s, l) in M0:
                if s == "data_assertion" and not (M["cons"][objs_pre[i]["unit"]] & ORA_SPECIFIC_SQL):
                    j = post_by.get((objs_pre[i]["unit"], objs_pre[i]["key"], objs_pre[i]["kind"]))
                    if j is not None:
                        probes.append((j, p, s, l, "kept"))
            probes += template
        elif variant == "S1":
            probes, attempts = remap(M0, "identifier")
            probes += template
        elif variant == "S2":
            slots = gt_slots["method"]
            sig, lev, evals = ga_synthesize(slots, objs_post, usage, "pg", budget, np.random.default_rng(seed + 3000))
            probes = [(i, p, SNAMES[s], int(l), "new") for (i, p), s, l in zip(slots, sig, lev) if s >= 0 and l > 0]

        elif variant == "A-RB":
            probes, attempts = remap(M0, "identifier")
            seen = {k[0] for k in probes}
            extra = [(j, p, s_, 2, "new") for j, o in enumerate(objs_post) if j not in seen
                     for p, s_ in TACTICS.get(o["kind"], [])]
            probes = greedy_fill(probes, extra, budget) + template
        elif variant == "A-RX":
            kept, attempts = remap(M0, "structural")
            probes = [k for k in kept if not (k[2] == "data_assertion" and M["cons"][objs_post[k[0]]["unit"]] & ORA_SPECIFIC_SQL)] + template
        elif variant == "A-AM":
            probes, attempts = remap(M0, "identifier")
            aff = M["affected"]
            up = [k for k in probes if aff[objs_post[k[0]]["unit"]] and k[3] < 3]
            rest = [k for k in probes if not (aff[objs_post[k[0]]["unit"]] and k[3] < 3)]
            # підвищення деталізації до рівня 3 у порядку спадання ваги до вичерпання бюджету
            up = sorted(up, key=lambda k: -usage[objs_post[k[0]]["unit"]] * PROPS[k[1]][0])
            spent = config_cost(rest + up)
            res = []
            for k in up:
                extra_c = SIG[k[2]][3] * (LEVEL_COST[3] - LEVEL_COST[k[3]])
                if spent + extra_c <= budget:
                    res.append((k[0], k[1], k[2], 3, k[4]))
                    spent += extra_c
                else:
                    res.append(k)
            probes = rest + res + template
        elif variant == "A-RV":
            # властивості вихідної специфікації (до міграції) для відображених об'єктів G1
            spec = []
            for j, o in enumerate(objs_post):
                if o["ora_key"] and o.get("ora_kind"):
                    for p in sorted(derive(o["ora_kind"], M["cons"][o["unit"]], False, False, "method", "pre")):
                        spec.append((j, p))
            slots = spec
            sig, lev, evals = ga_synthesize(slots, objs_post, usage, "pg", budget, np.random.default_rng(seed + 3000))
            probes = [(i, p, SNAMES[s], int(l), "new") for (i, p), s, l in zip(slots, sig, lev) if s >= 0 and l > 0] + template
        else:
            ont = "method" if variant in ("S3", "S3-9D") else "lexical"
            kept, attempts = remap(M0, "structural")
            # локалізація: зберігаються зонди властивостей, на які не впливають значущі виміри дрейфу одиниці
            aff = M["affected9"] if variant == "S3-9D" else M["affected"]
            keep = [k for k in kept if k[1] not in aff[objs_post[k[0]]["unit"]]]
            if variant in ("S3", "S3-9D"):
                keep = [k for k in keep if compatible(k[1], k[2], objs_post[k[0]]["kind"], "pg")]
            kept_keys = {(k[0], k[1]) for k in keep}
            slots = [(i, p) for (i, p) in gt_slots[ont] if (i, p) not in kept_keys]
            fixed = config_cost(keep)
            sig, lev, evals = ga_synthesize(slots, objs_post, usage, "pg", budget, np.random.default_rng(seed + 3000),
                                            check_compat=(variant != "S3-O"), fixed_cost=fixed)
            new = [(i, p, SNAMES[s], int(l), "new") for (i, p), s, l in zip(slots, sig, lev) if s >= 0 and l > 0]
            probes = keep + new
        t_adapt = time.perf_counter() - t0
        aff = M["affected9"] if variant == "S3-9D" else M["affected"]
        probes = [(i, p, s_, l, "fresh" if how in ("new", "tmpl") else
                   ("stale" if p in aff[objs_post[i]["unit"]] else "transferred")) for (i, p, s_, l, how) in probes]
        if PROBE_SINK is not None:
            PROBE_SINK[(seed, variant)] = list(probes)
        q, valid, agg = evaluate_config(probes, M, gt_slots, usage)
        # успішність переконфігурування: відновлені обов'язкові шляхи / обов'язкові
        restored = sum(1 for key in required if key in valid)
        mrsr = restored / len(required) if required else np.nan
        produced = [(i, p, s_) for (i, p, s_, l, how) in probes if i is not None]
        vr = (sum(compatible(p, s_, objs_post[i]["kind"], "pg") for i, p, s_ in produced) / len(produced)
              if produced else np.nan)
        defects = inject_defects(M, np.random.default_rng(seed + 4000), "post")
        det = simulate(defects, valid, agg, probes, usage, np.random.default_rng(seed + 5000))
        cost = config_cost(probes)
        acs = (q_pre["F1"] - det["F1"]) / q_pre["F1"] if q_pre["F1"] else np.nan
        n_stale = sum(how == "stale" for *_, how in probes)
        n_fresh = sum(how == "fresh" for *_, how in probes)
        out.append(dict(seed=seed, variant=variant, stale=n_stale, fresh=n_fresh, **q, MRSR=mrsr, VR=vr, **det, ACS=acs, F1_pre=q_pre["F1"],
                        OH=cost / budget, probes=len(probes),
                        slots_optimized=len(slots) if variant in ("S2", "S3", "S3-O", "A-RV", "S3-9D") else 0,
                        evals=evals, t_adapt=t_adapt, required=len(required)))
    return out


def a12(x, y):
    u = mannwhitneyu(x, y, alternative="two-sided").statistic
    return u / (len(x) * len(y))


def main():
    t = time.perf_counter()
    M = build_model()
    info = dict(obj_pre=len(M["obj_pre"]), obj_post=len(M["obj_post"]), slots_pre=len(M["pre"]),
                slots_gt=len(M["slots"]["gt"]), slots_method=len(M["slots"]["method"]),
                slots_lexical=len(M["slots"]["lexical"]),
                localized_units=int(sum(bool(v) for v in M["affected"].values())))
    print(info)
    rows = []
    for s in SEEDS:
        rows += run_seed(s, M)
        print("seed", s, "done", round(time.perf_counter() - t, 1), "s", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, f"e2e_runs{RUN_TAG}.csv"), index=False)
    if RUN_TAG:
        return
    metrics = ["PCR", "PCRw", "TPP", "MRSR", "VR", "P", "R", "F1", "MTTD", "LA", "FAR", "ACS", "OH", "probes",
               "slots_optimized", "evals", "t_adapt"]
    S = R.groupby("variant")[metrics].agg(["mean", "std"])
    S.columns = [f"{a}_{b}" for a, b in S.columns]
    S = S.reindex(["S0", "S1", "S2", "S3", "S3-O"])
    S.to_csv(os.path.join(OUT, "e2e_summary.csv"))
    tests = []
    for m in ["F1", "PCR", "TPP", "MRSR", "MTTD", "LA"]:
        piv = R.pivot(index="seed", columns="variant", values=m).dropna()
        fr = friedmanchisquare(*[piv[v] for v in piv.columns])
        for v in ["S0", "S1", "S2", "S3-O"]:
            x, y = piv["S3"], piv[v]
            try:
                w = wilcoxon(x, y).pvalue
            except ValueError:
                w = np.nan
            tests.append(dict(metric=m, comparison=f"S3 vs {v}", friedman_chi2=fr.statistic, friedman_p=fr.pvalue,
                              wilcoxon_p=w, A12=a12(x, y), mean_S3=x.mean(), mean_other=y.mean()))
    pd.DataFrame(tests).to_csv(os.path.join(OUT, "e2e_tests.csv"), index=False)
    json.dump(info, open(os.path.join(OUT, "e2e_model_info.json"), "w"), indent=1)
    pd.set_option("display.width", 250)
    print(S[[c for c in S.columns if c.endswith("mean")]].round(3).T.to_string())


if __name__ == "__main__":
    main()
