# -*- coding: utf-8 -*-
"""Independent evaluation of controlled-property inference against an execution-based reference.

The reference does not use the ontology rules of the method. It consists of the actual execution errors of the migrated
code on PostgreSQL 17 in the baseline state with no injected defects, including errors swallowed by WHEN OTHERS
handlers (ops/src/exec_gold.py -> ops/out/ops_exec_errors.csv). The mapping "SQLSTATE + message pattern ->
property" is fixed a priori by PostgreSQL error class (table RULES); errors caused by the incompleteness of the corpus
(missing tables, columns, schemas and routines of other systems) and by the test workload (generated arguments
and data, direct calls of trigger functions) are not part of the reference. Properties that no inference
method has in its vocabulary (implicit type conversion, package state) stay in the reference as a vocabulary gap.

Compared are the E3 inference methods (method = ontology, lexical, exhaustive), the specification of the source
version (source_spec, as in A-RV) and the evaluation reference (gt). Generic properties that all methods assign
to every routine (exec_errors, latency, call_volume, availability) are excluded from the evaluation.
Metrics: recall over (object, property) pairs of the reference; mean number of specific properties per object;
confirmed share - the share of assigned specific properties of objects whose errors actually occurred (a lower
bound on precision); recall gain over a random choice of the same size; 95% bootstrap intervals (10,000 object
samples) for paired recall differences.
Output: out/ont_indep_gold.csv, out/ont_indep_results.csv, out/ont_indep_rules.csv."""
import os, re
import numpy as np, pandas as pd
import e2e_adaptation as EA

OUT = EA.OUT
OPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ops", "out")
GENERIC = {"exec_errors", "latency", "call_volume", "availability"}
EXCL = "excluded"
# (SQLSTATE, message pattern or None, property | excluded, rationale)
RULES = [
    ("2D000", None, "txn_semantics", "ending a transaction is not allowed in this context"),
    ("22004", r"query string argument of EXECUTE is null", "null_semantics",
     "dynamic SQL text became NULL: concatenation with NULL does not give an empty string"),
    ("22004", r"cursor variable .* is null", "refcursor_lifecycle", "cursor variable is not open"),
    ("34000", None, "refcursor_lifecycle", "no open cursor with this name"),
    ("55000", r"is not assigned yet", "error_handling", "SELECT INTO without rows raised no exception"),
    ("P0001", r"does not exist|value too long", EXCL, "re-raised error caused by an incomplete corpus or data"),
    ("P0001", None, "error_handling", "application exception (RAISE_APPLICATION_ERROR)"),
    ("42501", None, "privilege_context", "insufficient privileges"),
    ("42601", None, "dynamic_sql_safety", "syntax error at run time - only in dynamic SQL"),
    ("22007", None, "temporal_semantics", "date/time format"),
    ("22008", None, "temporal_semantics", "date/time field overflow"),
    ("22012", None, "numeric_precision", "division by zero"),
    ("58P01", None, "remote_dependency", "file exchange (UTL_FILE)"),
    ("42883", r"operator does not exist", "type_coercion", "no implicit type conversion of the kind Oracle performs"),
    ("42883", r"function (\w+\.)?(sqlerrm|sqlerrcode|pg_exception_context|pg_backtrace)\(", "error_handling",
     "Oracle error-diagnostics functions"),
    ("42883", r"function (\w+\.)?(dblink|http_request|write_file|read_file)\w*\(", "remote_dependency",
     "external calls (DB link, UTL_HTTP, UTL_FILE)"),
    ("42883", r"function (\w+\.)?(round|trunc|to_char|to_date|to_number|nvl|decode|instr|substr|add_months|months_between)\(",
     "type_coercion", "built-in function with a different type signature"),
    ("42883", None, EXCL, "routine of another system, absent from the corpus"),
    ("42804", None, "type_coercion", "type mismatch without implicit conversion"),
    ("42846", None, "type_coercion", "impossible type conversion"),
    ("42704", r"configuration parameter", "package_state", "package state emulated with session parameters"),
    ("57014", None, "latency", "execution time exceeded"),
    ("42809", None, "exec_errors", "wrong object type"),
    ("0A000", r"trigger functions can only be called as triggers", EXCL, "direct call of a trigger function by the workload"),
    ("0A000", r"cross-database", "remote_dependency", "reference to another database"),
    ("0A000", None, "exec_errors", "unsupported feature"),
    ("42P01", None, EXCL, "table of another system, absent from the corpus"),
    ("42703", None, EXCL, "column of a table absent from the corpus"),
    ("3F000", None, EXCL, "schema of another system"),
    ("22P02", None, EXCL, "generated arguments or data"),
    ("22001", None, EXCL, "generated data"),
    ("22003", None, EXCL, "generated data"),
    ("23505", None, EXCL, "generated data"),
    ("23514", None, EXCL, "generated data"),
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
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "study_b", "ds", "O2P_GOLDEN_TESTSET_v03_full.csv"))
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
        # random choice of the same size among the compatible properties of the object (analytical expectation)
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
