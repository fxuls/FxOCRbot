"""Per-user engine preference, persisted as a small JSON file (atomic writes).

Only validated engine ids are ever stored. If the data dir isn't writable the store keeps working
in memory and logs once.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from fxocr.core.engines import ENGINES

log = logging.getLogger(__name__)
MAX_USERS = 100_000


class Prefs:
    def __init__(self, path: Path | None):
        self.path = path
        self._engine: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text("utf-8"))
            eng = raw.get("engine", {}) if isinstance(raw, dict) else {}
            self._engine = {str(k): v for k, v in eng.items() if isinstance(v, str) and v in ENGINES}
        except (OSError, ValueError) as exc:
            log.warning("prefs unreadable, starting empty: %s", type(exc).__name__)

    def engine_for(self, user_id: int, default: str) -> str:
        return self._engine.get(str(user_id), default)

    def set_engine(self, user_id: int, engine: str) -> None:
        if engine not in ENGINES:
            raise ValueError("unknown engine")
        if len(self._engine) >= MAX_USERS and str(user_id) not in self._engine:
            return  # don't let the file grow without bound
        self._engine[str(user_id)] = engine
        self._save()

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".prefs-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"engine": self._engine}, f)
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("prefs not saved (%s); keeping in memory", type(exc).__name__)
            self.path = None
