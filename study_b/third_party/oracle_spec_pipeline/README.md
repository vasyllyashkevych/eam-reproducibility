# Third-party code: object-profile classifier

`pipeline/profiles.py` is taken unchanged from the laboratory project *oracle-spec-project*
(original author). It classifies Oracle and PostgreSQL code units into profiles (table, view, routine,
trigger, orchestrator) with regular expressions and is used by `study_b/e2e/o2p_ctx_goal.py` for the goal-drift
dimension. It is redistributed here with the author's permission. `pipeline/__init__.py` is a minimal stub so that
only this module is imported; no other part of the original project is included.
