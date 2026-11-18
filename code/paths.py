"""Package-relative paths. No absolute paths to the author's machine are used anywhere."""
import os
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / "data"
RESULTS = Path(os.environ.get("EAM_RESULTS_DIR", PKG / "results"))
FIGURES = Path(os.environ.get("EAM_FIGURES_DIR", PKG / "figures"))
# Study B unit-level data are restricted; point this variable to an authorised local copy if you have one.
STUDY_B_RESTRICTED = Path(os.environ.get("EAM_STUDY_B_DIR", DATA / "study_b_restricted"))
# Fixed evaluation instant for Study C (the OSV cache was captured on this date).
OSV_AS_OF = os.environ.get("EAM_OSV_AS_OF", "2026-11-05 23:40:00")
