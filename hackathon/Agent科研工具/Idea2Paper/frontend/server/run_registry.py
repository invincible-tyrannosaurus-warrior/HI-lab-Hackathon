from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class RunInfo:
    ui_run_id: str
    pid: int
    popen: object
    started_at: float
    updated_at: float
    run_id: Optional[str] = None
    exit_code: Optional[int] = None
    status: str = "starting"
    env_meta: Dict = field(default_factory=dict)


class RunRegistry:
    def __init__(self, repo_root: Path):
        self._repo_root = repo_root
        self._runs: Dict[str, RunInfo] = {}
        self._lock = threading.Lock()

    def create(self, ui_run_id: str, popen, env_meta: Dict) -> RunInfo:
        now = time.time()
        info = RunInfo(
            ui_run_id=ui_run_id,
            pid=popen.pid,
            popen=popen,
            started_at=now,
            updated_at=now,
            env_meta=env_meta,
        )
        with self._lock:
            self._runs[ui_run_id] = info
        return info

    def get(self, ui_run_id: str) -> Optional[RunInfo]:
        with self._lock:
            return self._runs.get(ui_run_id)

    def list_runs(self):
        with self._lock:
            return list(self._runs.values())

    def update_run_id(self, info: RunInfo, run_id: str):
        with self._lock:
            info.run_id = run_id
            info.updated_at = time.time()

    def refresh_status(self, info: RunInfo):
        exit_code = info.popen.poll()
        info.exit_code = exit_code
        if exit_code is None:
            info.status = "running" if info.run_id else "starting"
        else:
            info.status = "done" if exit_code == 0 else "failed"
        info.updated_at = time.time()

    def resolve_run_id(self, pid: int) -> Optional[str]:
        log_root = self._repo_root / "log"
        if not log_root.exists():
            return None
        # find folder containing _{pid}_
        for p in log_root.iterdir():
            if not p.is_dir():
                continue
            name = p.name
            if f"_{pid}_" in name and name.startswith("run_"):
                return name
        return None
