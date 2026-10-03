"""Build content-addressed inventories of private research assets."""

import hashlib

COLLECTIONS = {
    "market": [
        "data/dax-cross-contract-flow",
        "data/futures-daily-development",
        "data/sr3-macro-revisions",
    ],
    "context": ["INDEX.md", "notes", "library", "sources"],
    "results": ["data/experiment-results"],
}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(source, collection):
    rows = []
    for name in COLLECTIONS[collection]:
        folder = source / name
        if not folder.exists():
            raise ValueError(f"Missing canonical source: {folder}")
        for p in [folder] if folder.is_file() else sorted(folder.rglob("*")):
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
    return {
        "collection": collection,
        "files": rows,
        "bytes": sum(r["bytes"] for r in rows),
    }
