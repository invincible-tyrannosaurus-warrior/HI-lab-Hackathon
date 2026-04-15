import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


class ResultBundler:
    def __init__(self, repo_root: Path, results_root: Path, mode: str = "link", keep_log: bool = True):
        self.repo_root = Path(repo_root)
        self.results_root = Path(results_root)
        self.mode = (mode or "link").lower()
        self.keep_log = bool(keep_log)

    def _warn(self, msg: str):
        print(f"[results] warning: {msg}")

    def _ensure_dir(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self._warn(f"failed to create dir {path}: {e}")
            return False

    def _rel(self, path: Path):
        try:
            return str(path.relative_to(self.repo_root))
        except Exception:
            return str(path)

    def _try_symlink(self, src: Path, dst: Path) -> bool:
        try:
            if dst.exists() or dst.is_symlink():
                if dst.is_dir() and not dst.is_symlink():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            os.symlink(str(src), str(dst), target_is_directory=src.is_dir())
            return True
        except Exception as e:
            self._warn(f"symlink failed ({src} -> {dst}): {e}")
            return False

    def _copy_path(self, src: Path, dst: Path) -> bool:
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return True
        except Exception as e:
            self._warn(f"copy failed ({src} -> {dst}): {e}")
            return False

    def _link_or_copy(self, src: Path, dst: Path) -> bool:
        if self.mode == "link":
            if self._try_symlink(src, dst):
                return True
            return self._copy_path(src, dst)
        return self._copy_path(src, dst)

    def _get_git_commit(self):
        try:
            head = self.repo_root / ".git" / "HEAD"
            if not head.exists():
                return None
            content = head.read_text(encoding="utf-8").strip()
            if content.startswith("ref:"):
                ref = content.split(" ", 1)[1].strip()
                ref_path = self.repo_root / ".git" / ref
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
                return None
            return content
        except Exception:
            return None

    def bundle(
        self,
        run_id: str,
        user_idea: str,
        success: bool,
        output_dir: Path,
        run_log_dir: Path | None,
        extra: dict | None = None,
    ) -> dict:
        status = {
            "ok": True,
            "partial": False,
            "errors": [],
            "results_dir": None,
        }
        try:
            run_dir = self.results_root / run_id
            if not self._ensure_dir(run_dir):
                status["ok"] = False
                status["errors"].append("results_dir_create_failed")
                return status

            status["results_dir"] = str(run_dir)

            files = {
                "final_story": Path(output_dir) / "final_story.json",
                "pipeline_result": Path(output_dir) / "pipeline_result.json",
            }
            placed = {}
            for key, src in files.items():
                dst = run_dir / src.name
                if src.exists():
                    ok = self._link_or_copy(src, dst)
                    placed[key] = self._rel(dst)
                    if not ok:
                        status["ok"] = False
                        status["partial"] = True
                        status["errors"].append(f"copy_failed:{src}")
                else:
                    status["ok"] = False
                    status["partial"] = True
                    status["errors"].append(f"missing:{src}")

            if self.keep_log and run_log_dir and Path(run_log_dir).exists():
                log_dst = run_dir / "run_log"
                ok = self._link_or_copy(Path(run_log_dir), log_dst)
                placed["run_log"] = self._rel(log_dst)
                if not ok:
                    status["ok"] = False
                    status["partial"] = True
                    status["errors"].append("log_copy_failed")

            manifest = {
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_idea": user_idea,
                "success": success,
                "paths": placed,
                "git_commit": self._get_git_commit(),
            }
            if extra:
                manifest.update(extra)

            try:
                with (run_dir / "manifest.json").open("w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
            except Exception as e:
                status["ok"] = False
                status["partial"] = True
                status["errors"].append(f"manifest_write_failed:{e}")

            return status
        except Exception as e:
            self._warn(f"bundle failed: {e}")
            status["ok"] = False
            status["errors"].append(f"bundle_failed:{e}")
            return status
