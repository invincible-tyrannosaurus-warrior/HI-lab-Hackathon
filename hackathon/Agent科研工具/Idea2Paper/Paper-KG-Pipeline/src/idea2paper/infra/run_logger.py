import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class RunLogger:
    """Structured run logger that writes meta.json and JSONL event/call logs."""

    def __init__(self, base_dir: Path, run_id: str, meta: Optional[Dict[str, Any]] = None,
                 max_text_chars: int = 20000):
        self.base_dir = Path(base_dir)
        self.run_id = run_id
        self.max_text_chars = max_text_chars
        self.run_dir = self.base_dir / run_id
        self.meta_path = self.run_dir / "meta.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.llm_path = self.run_dir / "llm_calls.jsonl"
        self.embedding_path = self.run_dir / "embedding_calls.jsonl"
        self._init_files(meta or {})

    def _init_files(self, meta: Dict[str, Any]):
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            meta_payload = {
                "run_id": self.run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta": meta
            }
            self.meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            # touch jsonl files
            for p in [self.events_path, self.llm_path, self.embedding_path]:
                if not p.exists():
                    p.write_text("", encoding="utf-8")
        except Exception as e:
            print(f"⚠️  [RunLogger] Failed to initialize log files: {e}")

    def _truncate(self, text: str) -> Dict[str, Any]:
        if text is None:
            return {"text": "", "truncated": False, "orig_len": 0}
        orig_len = len(text)
        if orig_len <= self.max_text_chars:
            return {"text": text, "truncated": False, "orig_len": orig_len}
        return {
            "text": text[: self.max_text_chars],
            "truncated": True,
            "orig_len": orig_len
        }

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]):
        try:
            line = json.dumps(payload, ensure_ascii=False)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + os.linesep)
        except Exception as e:
            print(f"⚠️  [RunLogger] Failed to write log: {e}")

    def _make_record(self, record_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "type": record_type,
            "data": data
        }

    def log_event(self, event_type: str, payload: Dict[str, Any]):
        self._append_jsonl(self.events_path, self._make_record("event", {
            "event_type": event_type,
            "payload": payload
        }))

    def log_llm_call(self, request: Dict[str, Any], response: Dict[str, Any]):
        if "prompt" in request:
            trunc = self._truncate(request.get("prompt", ""))
            request = dict(request)
            request["prompt"] = trunc["text"]
            request["prompt_truncated"] = trunc["truncated"]
            request["prompt_len"] = trunc["orig_len"]
        if "text" in response:
            trunc = self._truncate(response.get("text", ""))
            response = dict(response)
            response["text"] = trunc["text"]
            response["text_truncated"] = trunc["truncated"]
            response["text_len"] = trunc["orig_len"]
        self._append_jsonl(self.llm_path, self._make_record("llm", {
            "request": request,
            "response": response
        }))

    def log_embedding_call(self, request: Dict[str, Any], response: Dict[str, Any]):
        if "input_preview" in request:
            trunc = self._truncate(request.get("input_preview", ""))
            request = dict(request)
            request["input_preview"] = trunc["text"]
            request["input_truncated"] = trunc["truncated"]
            request["input_len"] = trunc["orig_len"]
        self._append_jsonl(self.embedding_path, self._make_record("embedding", {
            "request": request,
            "response": response
        }))

    def flush(self):
        # No-op for file-based logging; placeholder for future buffered logging.
        return
