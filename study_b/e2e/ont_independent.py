# -*- coding: utf-8 -*-
"""Незалежне оцінювання виведення контрольованих властивостей за виконавчим еталоном (підрозділ 7.7.8).

Еталон не використовує правил онтології методу. Він утворений фактичними помилками виконання мігрованого коду
на PostgreSQL 17 у базовому стані без внесених дефектів, включно з помилками, перехопленими обробниками
WHEN OTHERS (ops/src/exec_gold.py → ops/out/ops_exec_errors.csv). Відповідність «SQLSTATE + шаблон повідомлення →
властивість» задано апріорно за класами помилок PostgreSQL (табл. RULES); помилки, спричинені неповнотою набору
(відсутні таблиці, стовпці, схеми й підпрограми інших систем) та тестовим навантаженням (згенеровані аргументи
й дані, прямий виклик тригерної функції), до еталона не входять. Властивості, яких немає у словнику жодного
способу виведення (неявне перетворення типів, стан пакета), залишено в еталоні як прогалину словника.

Порівнюються способи виведення етапу E3 (method — онтологія, lexical, exhaustive), специфікація вихідної
версії (source_spec, як в A-RV) і еталон оцінювання 7.7.6–7.7.8 (gt). Загальні властивості, які всі способи
призначають кожній підпрограмі (exec_errors, latency, call_volume, availability), з оцінювання вилучено.
Метрики: повнота за парами (об'єкт, властивість) еталона; середня кількість специфічних властивостей
на об'єкт; частка підтверджених — частка призначених специфічних властивостей об'єктів з помилками, які
фактично проявилися (нижня межа точності); приріст повноти над випадковим вибором того самого розміру;
95 % бутстреп-інтервали (10 000 вибірок об'єктів) для парних різниць повноти.
Вихід: out/ont_indep_gold.csv, out/ont_indep_results.csv, out/ont_indep_rules.csv.
"""
import os, re
import numpy as np, pandas as pd
import e2e_adaptation as EA

OUT = EA.OUT
OPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ops", "out")
GENERIC = {"exec_errors", "latency", "call_volume", "availability"}
EXCL = "excluded"
# (SQLSTATE, шаблон повідомлення або None, властивість | excluded, обґрунтування)
RULES = [
    ("2D000", None, "txn_semantics", "завершення транзакції недопустиме в цьому контексті"),
    ("22004", r"query string argument of EXECUTE is null", "null_semantics",
     "текст динамічного SQL став NULL: конкатенація з NULL не дає порожнього рядка"),
    ("22004", r"cursor variable .* is null", "refcursor_lifecycle", "курсорна змінна не відкрита"),
    ("34000", None, "refcursor_lifecycle", "курсор із таким іменем не відкрито"),
    ("55000", r"is not assigned yet", "error_handling", "SELECT INTO без рядків не породив виключення"),
    ("P0001", r"does not exist|value too long", EXCL, "повторно піднята помилка неповноти набору чи даних"),
    ("P0001", None, "error_handling", "прикладне виключення (RAISE_APPLICATION_ERROR)"),
    ("42501", None, "privilege_context", "недостатньо прав"),
    ("42601", None, "dynamic_sql_safety", "синтаксична помилка під час виконання — лише в динамічному SQL"),
    ("22007", None, "temporal_semantics", "формат дати й часу"),
    ("22008", None, "temporal_semantics", "переповнення поля дати й часу"),
    ("22012", None, "numeric_precision", "ділення на нуль"),
    ("58P01", None, "remote_dependency", "файловий обмін (UTL_FILE)"),
    ("42883", r"operator does not exist", "type_coercion", "немає неявного перетворення типів, яке виконує Oracle"),
    ("42883", r"function (\w+\.)?(sqlerrm|sqlerrcode|pg_exception_context|pg_backtrace)\(", "error_handling",
     "функції діагностики помилок Oracle"),
    ("42883", r"function (\w+\.)?(dblink|http_request|write_file|read_file)\w*\(", "remote_dependency",
     "зовнішні виклики (DB link, UTL_HTTP, UTL_FILE)"),
    ("42883", r"function (\w+\.)?(round|trunc|to_char|to_date|to_number|nvl|decode|instr|substr|add_months|months_between)\(",
     "type_coercion", "вбудована функція з іншою сигнатурою типів"),
    ("42883", None, EXCL, "підпрограма іншої системи, відсутня в наборі"),
    ("42804", None, "type_coercion", "невідповідність типів без неявного перетворення"),
    ("42846", None, "type_coercion", "неможливе перетворення типів"),
    ("42704", r"configuration parameter", "package_state", "емуляція стану пакета параметрами сеансу"),
    ("57014", None, "latency", "перевищено час виконання"),
    ("42809", None, "exec_errors", "невідповідний тип об'єкта"),
    ("0A000", r"trigger functions can only be called as triggers", EXCL, "прямий виклик тригерної функції навантаженням"),
    ("0A000", r"cross-database", "remote_dependency", "звернення до іншої бази"),
    ("0A000", None, "exec_errors", "непідтримувана можливість"),
    ("42P01", None, EXCL, "таблиця іншої системи, відсутня в наборі"),
    ("42703", None, EXCL, "стовпець таблиці, відсутньої в наборі"),
    ("3F000", None, EXCL, "схема іншої системи"),
    ("22P02", None, EXCL, "згенеровані аргументи або дані"),
    ("22001", None, EXCL, "згенеровані дані"),
    ("22003", None, EXCL, "згенеровані дані"),
    ("23505", None, EXCL, "згенеровані дані"),
    ("23514", None, EXCL, "згенеровані дані"),
]


def map_error(state, msg):
    for st, rx, prop, _ in RULES:
        if st == state and (rx is None or re.search(rx, msg or "", re.I)):
            return prop
    return EXCL


def main():
    M = EA.build_model()
    post = M["obj_post"]
    E = pd.read_csv(os.path.join(OPS, "ops_exec_errors.csv"), keep_default_na=False)
    executed = sorted(E.j.unique())
    E = E[E.sqlstate != ""].copy()
    E["prop"] = [map_error(s, m) for s, m in zip(E.sqlstate, E.message)]
    E.to_csv(os.path.join(OUT, "ont_indep_gold.csv"), index=False)
    pd.DataFrame(RULES, columns=["sqlstate", "pattern", "property", "rationale"]) \
        .assign(errors=lambda d: [int(((E.sqlstate == s) & (E.prop == p)).sum()) for s, p in zip(d.sqlstate, d.property)]) \
        .to_csv(os.path.join(OUT, "ont_indep_rules.csv"), index=False)
    G = E[(E.prop != EXCL) & ~E.prop.isin(GENERIC)].groupby("j").prop.agg(lambda s: set(s)).to_dict()
    pchg = {r.unit: (r.priv_ora == "definer" and r.priv_pg == "invoker") for r in M["U"].itertuples()}
    raw_q = pd.read_csv(EA.DATA if hasattr(EA, "DATA") else
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv"))
    quoted = raw_q.input_db_query.fillna("").str.contains(r'"[A-Za-z_]\w*"', regex=True).to_numpy()

    def spec(j, how):
        o = post[j]
        cons = M["cons"][o["unit"]]
        if how == "exhaustive":
            P = {p for p in EA.PNAMES if any(EA.compatible(p, s, o["kind"], "pg") for s in EA.SNAMES)}
        elif how == "source_spec":
            P = EA.derive(o.get("ora_kind") or "", cons, False, False, "method", "pre") if o["ora_key"] else set()
        else:
            P = EA.derive(o["kind"], cons, pchg[o["unit"]], quoted[o["unit"]], how, "post")
        return P - GENERIC

    methods = ["method", "lexical", "exhaustive", "source_spec", "gt"]
    comp = {j: {p for p in EA.PNAMES if any(EA.compatible(p, s, post[j]["kind"], "pg") for s in EA.SNAMES)} - GENERIC
            for j in executed}
    gold_j = [j for j in executed if j in G]
    vocab = set(EA.PNAMES)
    rng = np.random.default_rng(42)
    hits = {m: np.array([len(spec(j, m) & G[j]) for j in gold_j]) for m in methods}
    size_g = {m: np.array([len(spec(j, m)) for j in gold_j]) for m in methods}
    ng = np.array([len(G[j]) for j in gold_j])
    ng_vocab = np.array([len(G[j] & vocab) for j in gold_j])
    rows = []
    for m in methods:
        # випадковий вибір того самого розміру із сумісних властивостей об'єкта (аналітичне очікування)
        exp_rand = np.array([min(len(spec(j, m)), len(comp[j])) / len(comp[j]) * len(G[j] & comp[j]) if comp[j] else 0.0
                             for j in gold_j])
        idx = rng.integers(0, len(gold_j), (10000, len(gold_j)))
        rb = hits[m][idx].sum(1) / ng[idx].sum(1)
        rows.append(dict(method=m, objects_executed=len(executed), objects_gold=len(gold_j), gold_pairs=int(ng.sum()),
                         gold_pairs_in_vocab=int(ng_vocab.sum()), hits=int(hits[m].sum()),
                         recall=hits[m].sum() / ng.sum(), recall_lo=np.quantile(rb, .025), recall_hi=np.quantile(rb, .975),
                         recall_in_vocab=hits[m].sum() / ng_vocab.sum(),
                         size_all=np.mean([len(spec(j, m)) for j in executed]), size_gold=size_g[m].mean(),
                         confirmed_share=hits[m].sum() / size_g[m].sum() if size_g[m].sum() else np.nan,
                         recall_random=exp_rand.sum() / ng.sum()))
    R = pd.DataFrame(rows)
    idx = rng.integers(0, len(gold_j), (10000, len(gold_j)))
    for m in methods[1:]:
        d = (hits["method"][idx].sum(1) - hits[m][idx].sum(1)) / ng[idx].sum(1)
        R.loc[R.method == m, ["d_recall_vs_method", "d_lo", "d_hi"]] = \
            [-(hits["method"].sum() - hits[m].sum()) / ng.sum(), -np.quantile(d, .975), -np.quantile(d, .025)]
    R.to_csv(os.path.join(OUT, "ont_indep_results.csv"), index=False)
    pd.set_option("display.width", 250)
    print(E.groupby("prop").agg(errors=("j", "size"), objects=("j", "nunique")).sort_values("objects", ascending=False))
    print(R.round(3).to_string())
    by = pd.Series([p for j in gold_j for p in G[j]]).value_counts()
    cov = {m: pd.Series([p for j in gold_j for p in G[j] & spec(j, m)]).value_counts() for m in methods}
    print(pd.concat([by.rename("gold")] + [cov[m].rename(m) for m in methods], axis=1).fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
