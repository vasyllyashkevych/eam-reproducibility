"""
Object profiles for the QA framework.

Different Oracle objects need different testing attributes. A CREATE TABLE
has no branches to cover; a driver script has no NULL semantics. Forcing
all attributes on every object produces noise and wastes LLM tokens.

Five profiles, each with its own closed list of applicable attributes:
  - table       (CREATE TABLE, INDEX, SEQUENCE, TYPE)
  - view        (CREATE VIEW, MATERIALIZED VIEW)
  - routine     (CREATE PROCEDURE, FUNCTION, PACKAGE)
  - trigger     (CREATE TRIGGER)
  - orchestrator (driver scripts that only @-include other files)

Classification is done with regex on the file content, no LLM call needed.

Security attribute is added CONDITIONALLY to routine and trigger profiles
only when the source contains dynamic SQL constructs (EXECUTE IMMEDIATE,
DBMS_SQL, cursor variables built from strings). This keeps the attribute
list minimal for objects that cannot have injection issues.
"""

from __future__ import annotations
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Attribute profiles. Each profile is a closed list of (type, attr) pairs.
#
# Testing categories (6 total):
#   - Compatibility  (structural equivalence: types, dialect, NULL semantics)
#   - Unit           (individual branches, exception paths, boundary values)
#   - Integration    (dependencies, execution order, concurrency)
#   - Regression     (behavioral equivalence with Oracle ground truth)
#   - Smoke          (basic reachability and execution)
#   - Security       (dynamic SQL injection resistance) - conditional
# ---------------------------------------------------------------------------

TABLE_ATTRIBUTES: list[tuple[str, str]] = [
    ("Compatibility", "dialect_coverage"),
    ("Compatibility", "type_fidelity"),
    ("Compatibility", "null_behavior"),
    ("Unit", "boundary_values"),
    ("Integration", "object_dependency"),
    ("Regression", "result_parity"),
    ("Smoke", "object_creates"),
]


VIEW_ATTRIBUTES: list[tuple[str, str]] = [
    ("Compatibility", "dialect_coverage"),
    ("Compatibility", "type_fidelity"),
    ("Integration", "object_dependency"),
    ("Regression", "result_parity"),
    ("Smoke", "object_creates"),
]


ROUTINE_ATTRIBUTES: list[tuple[str, str]] = [
    ("Compatibility", "dialect_coverage"),
    ("Compatibility", "null_behavior"),
    ("Compatibility", "package_mapping"),
    ("Unit", "branch_coverage"),
    ("Unit", "exception_paths"),
    ("Unit", "boundary_values"),
    ("Integration", "execution_order"),
    ("Integration", "object_dependency"),
    ("Regression", "result_parity"),
    ("Smoke", "critical_calls"),
]


TRIGGER_ATTRIBUTES: list[tuple[str, str]] = [
    ("Compatibility", "dialect_coverage"),
    ("Compatibility", "type_fidelity"),
    ("Compatibility", "null_behavior"),
    ("Unit", "branch_coverage"),
    ("Unit", "exception_paths"),
    ("Unit", "state_transition"),
    ("Unit", "boundary_values"),
    ("Integration", "object_dependency"),
    ("Integration", "concurrency"),
    ("Integration", "trigger_side_effects"),
    ("Regression", "result_parity"),
    ("Smoke", "critical_calls"),
]


ORCHESTRATOR_ATTRIBUTES: list[tuple[str, str]] = [
    ("Integration", "execution_order"),
    ("Integration", "object_dependency"),
]


# Conditional attribute: added only when the source has dynamic SQL.
# Applies to routine and trigger profiles.
SECURITY_ATTRIBUTE: tuple[str, str] = ("Security", "dynamic_sql_safety")


PROFILES: dict[str, list[tuple[str, str]]] = {
    "table": TABLE_ATTRIBUTES,
    "view": VIEW_ATTRIBUTES,
    "routine": ROUTINE_ATTRIBUTES,
    "trigger": TRIGGER_ATTRIBUTES,
    "orchestrator": ORCHESTRATOR_ATTRIBUTES,
}


# ---------------------------------------------------------------------------
# Classifier. Regex-based, deterministic, no LLM.
# ---------------------------------------------------------------------------

_CLASSIFY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\b", re.IGNORECASE), "trigger"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\b", re.IGNORECASE), "view"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?)\b", re.IGNORECASE), "routine"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:GLOBAL\s+TEMPORARY\s+)?TABLE\b", re.IGNORECASE), "table"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?INDEX\b", re.IGNORECASE), "table"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?SEQUENCE\b", re.IGNORECASE), "table"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TYPE\b", re.IGNORECASE), "table"),
]

_ORCHESTRATOR_PATTERN = re.compile(r"^\s*@[^\s]", re.MULTILINE)


# Dynamic SQL detection patterns. Any match means the file has code paths
# that build and execute SQL strings at runtime, which need a Security
# attribute to check for injection resistance.
#
# Covered constructs:
#   EXECUTE IMMEDIATE ...        (PL/SQL dynamic SQL, method 1-3)
#   DBMS_SQL.parse / .execute    (PL/SQL dynamic SQL, method 4)
#   OPEN <cursor> FOR '...'      (cursor variable from a string)
#   EXECUTE '<string>'           (PostgreSQL PL/pgSQL dynamic SQL)
_DYNAMIC_SQL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.IGNORECASE),
    re.compile(r"\bDBMS_SQL\.(?:parse|execute|open_cursor|to_cursor_number)\b", re.IGNORECASE),
    re.compile(r"\bOPEN\s+\w+\s+FOR\s+['\"]", re.IGNORECASE),
    re.compile(r"\bEXECUTE\s+['\"]", re.IGNORECASE),
]


def _strip_comments(sql_code: str) -> str:
    """
    Remove SQL line comments and Oracle 'rem' lines before analysis.
    Block comments /* ... */ are stripped in a simple non-nested way.
    """
    sql_code = re.sub(r"/\*.*?\*/", " ", sql_code, flags=re.DOTALL)
    lines: list[str] = []
    for line in sql_code.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--"):
            continue
        low = stripped.lower()
        if low.startswith("rem ") or low == "rem" or low.startswith("prompt "):
            continue
        lines.append(line)
    return "\n".join(lines)


def classify(sql_file: Path) -> str:
    """
    Classify an Oracle SQL file into one of the five profiles.
    Returns the profile name; defaults to 'table' if nothing matches.
    """
    sql_code = sql_file.read_text(encoding="utf-8", errors="replace")
    cleaned = _strip_comments(sql_code)

    include_count = len(_ORCHESTRATOR_PATTERN.findall(cleaned))
    ddl_match: str | None = None
    for pattern, profile in _CLASSIFY_PATTERNS:
        if pattern.search(cleaned):
            ddl_match = profile
            break

    if include_count > 0 and ddl_match is None:
        return "orchestrator"
    if ddl_match is not None:
        return ddl_match
    return "table"


def has_dynamic_sql(sql_file: Path) -> bool:
    """
    Return True if the file contains dynamic SQL constructs.

    Detection is deterministic and regex-based. False positives are
    unlikely because the patterns require specific keywords in specific
    positions. False negatives are possible if the file uses an unusual
    construct not in the pattern list.
    """
    sql_code = sql_file.read_text(encoding="utf-8", errors="replace")
    cleaned = _strip_comments(sql_code)
    return any(pat.search(cleaned) for pat in _DYNAMIC_SQL_PATTERNS)


def attributes_for(profile: str, sql_file: Path | None = None) -> list[tuple[str, str]]:
    """
    Return the list of (type, attr) pairs for the given profile.

    If sql_file is provided and the profile is routine or trigger and the
    file contains dynamic SQL, the Security.dynamic_sql_safety attribute
    is appended. This is the only conditional attribute in the system.

    Raises KeyError for unknown profiles so misconfiguration surfaces early.
    """
    base_attributes = PROFILES[profile]

    # Security attribute is only relevant for procedural profiles and only
    # when dynamic SQL is present. Adding it unconditionally would repeat
    # the mistake of the 17-attribute universal vocabulary.
    if sql_file is not None and profile in ("routine", "trigger"):
        if has_dynamic_sql(sql_file):
            return base_attributes + [SECURITY_ATTRIBUTE]

    return base_attributes
