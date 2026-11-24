"""Atomic records, product identities and exclusive per-operation mutation."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".record-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, default=str)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


@contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"operation is already active: {path}") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def records(paths):
    result = []
    for path in sorted(set(map(Path, paths))):
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"required nonempty product missing: {path}")
        h = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        result.append({"path": str(path.resolve()), "sha256": h.hexdigest()})
    return result


@contextmanager
def ownership(runtime, owner, *, claim=False):
    """Lock the actual shared runtime, and refuse another operation's files."""
    runtime = Path(runtime).resolve()
    marker = runtime / ".platform/owner.json"
    if not claim and not marker.is_file():
        raise RuntimeError(f"runtime has no platform ownership record: {runtime}")
    with lock(runtime / ".platform/runtime.lock"):
        expected = str(Path(owner).resolve())
        if marker.is_file():
            if json.loads(marker.read_text())["owner"] != expected:
                raise RuntimeError(
                    f"runtime already belongs to another operation: {runtime}"
                )
        else:
            if any(path.name != ".platform" for path in runtime.iterdir()):
                raise RuntimeError(f"refusing existing unowned runtime: {runtime}")
            atomic_json(marker, {"owner": expected})
        yield
