"""Test configuration: force offline, deterministic, network-free runs.

Environment variables are set before any project module imports
``config.settings`` so the singleton picks them up.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="sih26091-tests-"))

os.environ["DATA_MODE"] = "offline"
os.environ["LLM_PROVIDER"] = "none"
os.environ["CHECKPOINT_BACKEND"] = "memory"
os.environ["SQLITE_DB_PATH"] = str(_TMP / "platform.db")
os.environ["VECTOR_STORE_PATH"] = str(_TMP / "vector_store")
os.environ["INDIC_TRANSLATION_ENABLED"] = "false"
