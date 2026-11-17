"""Date-aware, login-side input acquisition with atomic publication.

The acquisition contract is generic: providers are configured explicitly by
the experiment. Historical availability is never assumed or fabricated.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import urllib.error
import urllib.request
import fcntl


class InputUnavailable(RuntimeError):
    """A required scientific input could not be obtained from its provider."""


def ensure_input(*, target: Path, url: str | None, label: str,
                 timeout: int = 300, magic: bytes | None = None,
                 min_bytes: int = 1, sha256: str | None = None) -> Path:
    """Return an existing valid file or download it exactly once on LOGIN.

    A locked, temporary download is checked before publication with a hard
    link, so no partial file ever appears at the scientific input path.
    Existing files are never overwritten.
    """
    target = Path(target).expanduser()
    if timeout <= 0 or min_bytes <= 0:
        raise ValueError("acquisition timeout and minimum size must be positive")
    if url and not url.startswith("https://"):
        raise ValueError("scientific input URL must use HTTPS")

    def validate(path: Path) -> None:
        if not path.is_file() or path.stat().st_size < min_bytes:
            raise InputUnavailable(f"{label}: absent, empty or truncated input: {path}")
        if magic:
            with path.open("rb") as stream:
                if stream.read(len(magic)) != magic:
                    raise InputUnavailable(f"{label}: invalid file signature: {path}")
        if sha256:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest().lower() != sha256.lower():
                raise InputUnavailable(f"{label}: SHA-256 mismatch: {path}")

    if target.is_file():
        validate(target)
        return target
    if target.exists():
        raise InputUnavailable(f"{label}: target exists but is not a regular file: {target}")
    if not url:
        raise InputUnavailable(
            f"{label}: required input not found: {target}. "
            "No downloadable provider is configured for this product/date."
        )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise InputUnavailable(
            f"{label}: cannot create input directory {target.parent}: {error}. "
            "Select a writable input cache."
        ) from error

    lock_path = target.with_name(target.name + ".acquisition.lock")
    try:
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if target.is_file():
                validate(target)
                return target
            fd, temporary = tempfile.mkstemp(prefix=".acquiring-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as dest:
                    with urllib.request.urlopen(url, timeout=timeout) as response:
                        if response.status != 200:
                            raise InputUnavailable(
                                f"{label}: provider returned HTTP {response.status} for {url}"
                            )
                        shutil.copyfileobj(response, dest)
                        declared_size = response.headers.get("Content-Length")
                part = Path(temporary)
                if declared_size and part.stat().st_size != int(declared_size):
                    raise InputUnavailable(f"{label}: incomplete download from {url}")
                validate(part)
                os.link(part, target)
                # Record the exact provider/time/content identity next to the
                # cached raw input for reproducibility and later audit.
                digest = hashlib.sha256()
                with part.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                provenance = {
                    "schema_version": 1,
                    "label": label,
                    "source_url": url,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "size_bytes": part.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
                sidecar = target.with_name(target.name + ".acquisition.json")
                if not sidecar.exists():
                    fd_meta, temp_meta = tempfile.mkstemp(
                        prefix=".acquisition-meta-", dir=target.parent
                    )
                    try:
                        with os.fdopen(fd_meta, "w", encoding="utf-8") as meta:
                            json.dump(provenance, meta, indent=2, sort_keys=True)
                            meta.write("\\n")
                        os.link(temp_meta, sidecar)
                    finally:
                        Path(temp_meta).unlink(missing_ok=True)
            except (urllib.error.URLError, OSError) as error:
                raise InputUnavailable(
                    f"{label}: acquisition failed from {url}: {error}"
                ) from error
            finally:
                Path(temporary).unlink(missing_ok=True)
            return target
    except OSError as error:
        raise InputUnavailable(
            f"{label}: acquisition cache is not writable: {lock_path}: {error}"
        ) from error
