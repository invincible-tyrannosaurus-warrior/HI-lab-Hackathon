"""
Knowledge Graph Build Manager

Manages the 4-step KG construction pipeline:
  1. extract_patterns_ICLR_en_local.py
  2. generate_clusters.py
  3. build_entity_v3.py
  4. build_edges.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


# ── step / build status ──────────────────────────────────────────

class StepStatus:
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class BuildStatus:
    STARTING  = "starting"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


# ── data classes ──────────────────────────────────────────────────

@dataclass
class BuildStep:
    name: str
    script_name: str
    status: str = StepStatus.PENDING
    progress: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LogEntry:
    timestamp: str
    level: str
    step: str
    message: str


# ── manager ───────────────────────────────────────────────────────

SCRIPT_STEPS = [
    ("extract_patterns", "extract_patterns_ICLR_en_local.py"),
    ("generate_clusters", "generate_clusters.py"),
    ("build_entities",    "build_entity_v3.py"),
    ("build_edges",       "build_edges.py"),
]


class KGBuildManager:
    """Run 4 scripts in sequence in a background thread."""

    def __init__(
        self,
        build_id: str,
        dataset_name: str,
        dataset_path: str,
        output_dir: str,
        repo_root: Path,
        *,
        llm_api_key: str = "",
        llm_model: str = "gpt-4o",
        llm_api_url: str = "",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.build_id = build_id
        self.dataset_name = dataset_name
        # Ensure absolute path (frontend may send relative path)
        self.dataset_path = str((repo_root / dataset_path).resolve())
        self.output_dir = str((Path(output_dir)).resolve())
        self.repo_root = repo_root
        self.scripts_dir = repo_root / "Paper-KG-Pipeline" / "scripts"

        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_api_url = llm_api_url
        self.embedding_model = embedding_model

        # state
        self.status: str = BuildStatus.STARTING
        self.steps: List[BuildStep] = [
            BuildStep(name=name, script_name=script)
            for name, script in SCRIPT_STEPS
        ]
        self.current_step_index: Optional[int] = None
        self.error: Optional[str] = None

        # subprocess handle
        self._process: Optional[subprocess.Popen] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # logs
        self._lock = threading.Lock()
        self._logs: List[LogEntry] = []

    # ── public API ────────────────────────────────────────────────

    def start(self):
        self.status = BuildStatus.RUNNING
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._log("warning", "all", "Build cancelled by user.")
        self._stop.set()
        if self._process and self._process.poll() is None:
            self._process.kill()
        self.status = BuildStatus.CANCELLED
        if self.current_step_index is not None:
            self.steps[self.current_step_index].status = StepStatus.CANCELLED

    def get_status(self) -> dict:
        current_step_name = None
        overall = 0.0
        if self.current_step_index is not None:
            current_step_name = self.steps[self.current_step_index].name
            done = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
            cur_step = self.steps[self.current_step_index]
            cur = 0.0 if cur_step.status == StepStatus.COMPLETED else cur_step.progress
            overall = min((done + cur) / len(self.steps), 1.0)
        return {
            "ok": True,
            "build_id": self.build_id,
            "dataset_name": self.dataset_name,
            "status": self.status,
            "current_step": current_step_name,
            "progress": round(overall, 3),
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
        }

    def get_logs(self, since: int = 0) -> dict:
        with self._lock:
            entries = self._logs[since:]
        return {
            "ok": True,
            "logs": [asdict(e) for e in entries],
            "total": len(self._logs),
        }

    def is_running(self) -> bool:
        return self.status in (BuildStatus.STARTING, BuildStatus.RUNNING)

    # ── internals ─────────────────────────────────────────────────

    def _run(self):
        try:
            for idx, step in enumerate(self.steps):
                if self._stop.is_set():
                    self.status = BuildStatus.CANCELLED
                    return
                self.current_step_index = idx
                self._exec_step(step)
                if step.status == StepStatus.FAILED:
                    self.status = BuildStatus.FAILED
                    self.error = step.error
                    return
            self.status = BuildStatus.COMPLETED
            self._log("info", "all", "Knowledge graph build completed successfully!")
        except Exception as exc:
            self.status = BuildStatus.FAILED
            self.error = str(exc)
            self._log("error", "all", f"Build failed: {exc}")

    def _exec_step(self, step: BuildStep):
        step.status = StepStatus.RUNNING
        step.started_at = _now_iso()
        self._log("info", step.name, f"Starting step: {step.name}")

        env = os.environ.copy()
        env["KG_OUTPUT_DIR"]   = self.output_dir
        env["INPUT_JSONL_PATH"] = self.dataset_path
        if self.llm_api_key:
            env["SILICONFLOW_API_KEY"] = self.llm_api_key
            env["OPENAI_API_KEY"]      = self.llm_api_key
            env["LLM_API_KEY"]         = self.llm_api_key
        env["OPENAI_MODEL"] = self.llm_model
        env["LLM_MODEL"]    = self.llm_model
        if self.llm_api_url:
            env["OPENAI_BASE_URL"] = self.llm_api_url
            env["LLM_BASE_URL"]    = self.llm_api_url
            # Clear LLM_API_URL so the .env default (siliconflow) doesn't
            # override the user-configured base URL.  openai_compatible.py
            # uses: endpoint = api_url or join_url(base_url, "/chat/completions")
            # An empty api_url lets base_url take effect.
            env["LLM_API_URL"]     = ""

        script_path = self.scripts_dir / step.script_name
        cmd = ["python", str(script_path)]

        # step-specific CLI args
        if step.name == "generate_clusters":
            patterns_file = Path(self.output_dir) / "iclr_patterns_full.jsonl"
            # count patterns to set HDBSCAN params for small datasets
            n_patterns = _count_lines(patterns_file)
            min_cluster = max(3, n_patterns // 10)
            min_samples = max(2, n_patterns // 20)
            cmd += [
                "--input", str(patterns_file),
                "--outdir", self.output_dir,
                "--sbert_model", self.embedding_model,
                "--hdb_min_cluster_size", str(min_cluster),
                "--hdb_min_samples", str(min_samples),
                "--llm_name",
                "--llm_model", self.llm_model,
            ]
            if self.llm_api_url:
                cmd += ["--llm_api_base", self.llm_api_url]

        try:
            self._process = subprocess.Popen(
                cmd,
                env=env,
                cwd=str(self.scripts_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in self._process.stdout:
                if self._stop.is_set():
                    self._process.kill()
                    step.status = StepStatus.CANCELLED
                    return
                line = line.rstrip()
                if line:
                    self._log("info", step.name, line)
                    p = _parse_progress(line)
                    if p is not None:
                        step.progress = p

            rc = self._process.wait()
            if rc == 0:
                step.status = StepStatus.COMPLETED
                step.progress = 1.0
                step.completed_at = _now_iso()
                self._log("info", step.name, f"Step completed: {step.name}")
            else:
                step.status = StepStatus.FAILED
                step.error = f"Script exited with code {rc}"
                self._log("error", step.name, step.error)
        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error = str(exc)
            self._log("error", step.name, str(exc))

    def _log(self, level: str, step: str, message: str):
        entry = LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            step=step,
            message=message,
        )
        with self._lock:
            self._logs.append(entry)


# ── helpers ───────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().isoformat()


def _count_lines(filepath: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 100  # safe default


def _parse_progress(line: str) -> Optional[float]:
    """Extract progress from log lines like '300/1000' or '45%'."""
    m = re.search(r'(\d+)/(\d+)', line)
    if m:
        cur, tot = int(m.group(1)), int(m.group(2))
        if tot > 0:
            return min(cur / tot, 1.0)
    m = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
    if m:
        return min(float(m.group(1)) / 100.0, 1.0)
    if any(k in line for k in ("✓", "✅", "completed", "Completed")):
        return 1.0
    return None


# ── registry (singleton-ish, one active build) ────────────────────

_current_build: Optional[KGBuildManager] = None
_build_lock = threading.Lock()


def start_build(
    dataset_name: str,
    dataset_path: str,
    repo_root: Path,
    *,
    llm_api_key: str = "",
    llm_model: str = "gpt-4o",
    llm_api_url: str = "",
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> tuple[bool, str, Optional[KGBuildManager]]:
    """Start a new KG build.  Returns (ok, message, manager)."""
    global _current_build
    with _build_lock:
        if _current_build and _current_build.is_running():
            return False, "A build is already running.", None

        output_dir = str(repo_root / "Paper-KG-Pipeline" / "output")
        build_id = f"kg_{int(time.time())}_{os.urandom(3).hex()}"

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        mgr = KGBuildManager(
            build_id=build_id,
            dataset_name=dataset_name,
            dataset_path=dataset_path,
            output_dir=output_dir,
            repo_root=repo_root,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            llm_api_url=llm_api_url,
            embedding_model=embedding_model,
        )
        _current_build = mgr
        mgr.start()
        return True, build_id, mgr


def get_current_build() -> Optional[KGBuildManager]:
    return _current_build


def cancel_current_build() -> tuple[bool, str]:
    global _current_build
    with _build_lock:
        if not _current_build:
            return False, "No build running."
        if not _current_build.is_running():
            return False, "Build already finished."
        _current_build.cancel()
        return True, "Build cancelled."


# ── dataset validation ────────────────────────────────────────────

def validate_dataset(path_str: str) -> tuple[bool, Optional[str], Optional[dict]]:
    """Return (valid, error_msg, estimate_dict)."""
    p = Path(path_str)
    if not p.exists():
        return False, f"File not found: {path_str}", None
    if p.suffix != ".jsonl":
        return False, "File must be .jsonl", None

    required = {"title", "abstract"}
    id_fields = {"paper_id", "id"}       # accept either
    try:
        count = 0
        with open(p, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                count += 1
                if i < 10:          # validate first 10 lines
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError as e:
                        return False, f"Invalid JSON at line {i+1}: {e}", None
                    keys = set(rec.keys())
                    missing = required - keys
                    if missing:
                        return False, f"Missing fields at line {i+1}: {missing}", None
                    if not (keys & id_fields):
                        return False, f"Missing id field at line {i+1}: need 'id' or 'paper_id'", None

        mins = int(count * 3 / 60) + 10   # rough estimate
        display = f"{mins} min" if mins < 60 else f"{mins//60}h {mins%60}m"
        est = {"paper_count": count, "estimated_minutes": mins, "estimated_display": display}
        return True, None, est
    except Exception as e:
        return False, str(e), None
