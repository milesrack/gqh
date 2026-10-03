"""Build content-addressed inventories of private research assets."""

import fnmatch
import hashlib


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(source, collection, pattern=None):
    rows = []
    if not source.is_dir():
        raise ValueError(f"Source must be a directory: {source}")
    folder = source
    if folder.is_symlink():
        raise ValueError(f"Symlink excluded: {folder}")
    for p in sorted(folder.rglob("*")):
        if pattern and not fnmatch.fnmatch(str(p.relative_to(source)), pattern):
            continue
        if p.is_symlink():
            raise ValueError(f"Symlink excluded: {p}")
        if not p.is_file():
            continue
        if p.stat().st_size < 200 and p.read_bytes().startswith(
            b"version https://git-lfs.github.com/spec/v1"
        ):
            raise ValueError(f"Git LFS pointer: pull the real source first: {p}")
        rows.append(
            {
                "path": str(p.relative_to(source)),
                "bytes": p.stat().st_size,
                "sha256": sha(p),
            }
        )
    if not rows:
        raise ValueError("No source assets matched")
    return {
        "collection": collection,
        "files": rows,
        "bytes": sum(r["bytes"] for r in rows),
    }
