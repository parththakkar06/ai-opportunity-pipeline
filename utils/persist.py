"""Optional persistence of saved runs to a private Hugging Face Dataset repo.

A free Hugging Face Space has an ephemeral disk, so reports would vanish on every restart. When
REPORTS_DATASET (e.g. "my-org/ai-opportunity-reports") and HF_TOKEN are set, finished runs are uploaded
to that dataset and restored into OUTPUTS_DIR at startup. With either unset, everything here is a no-op,
so local use is unchanged. Failures never break a run: they're logged and the local copy is kept.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("persist")
IGNORE = ["cache/**", "cache", "*.tmp", "04_prototype.html"]   # the cache is rebuilt; prototypes can be large
_lock = threading.Lock()


def enabled() -> bool:
    return bool(os.getenv("REPORTS_DATASET") and os.getenv("HF_TOKEN"))


def _api():
    from huggingface_hub import HfApi   # imported lazily: only installed for the Space image

    return HfApi(token=os.getenv("HF_TOKEN"))


def restore(outputs: Path) -> int:
    """Download saved runs into `outputs` (never overwriting newer local files). Returns folders restored."""
    if not enabled():
        return 0
    try:
        from huggingface_hub import snapshot_download

        outputs.mkdir(parents=True, exist_ok=True)
        before = {p.name for p in outputs.iterdir() if p.is_dir()}
        snapshot_download(repo_id=os.environ["REPORTS_DATASET"], repo_type="dataset", token=os.getenv("HF_TOKEN"),
                          local_dir=str(outputs), ignore_patterns=[".gitattributes", "README.md"])
        return len({p.name for p in outputs.iterdir() if p.is_dir() and not p.name.startswith(".")} - before)
    except Exception as exc:  # noqa: BLE001 - a missing or empty dataset must not stop the app starting
        log.warning("Couldn't restore saved reports: %s", exc)
        return 0


def save_run(out_dir: Path) -> bool:
    """Upload one run folder to the dataset. Safe to call from any thread; returns True if uploaded."""
    if not enabled() or not out_dir.is_dir():
        return False
    with _lock:
        try:
            _api().upload_folder(folder_path=str(out_dir), path_in_repo=out_dir.name,
                                 repo_id=os.environ["REPORTS_DATASET"], repo_type="dataset",
                                 ignore_patterns=IGNORE, commit_message=f"Save run {out_dir.name}")
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Couldn't save %s to the dataset: %s", out_dir.name, exc)
            return False
