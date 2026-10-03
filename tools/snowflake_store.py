"""Versioned private assets and cited context retrieval in Snowflake."""

import argparse
import fnmatch
import json
import lzma
import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import snowflake.connector
from datastore import inventory, sha


def connect():
    args = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ.get("SNOWFLAKE_ROLE", "GQH_RESEARCHER"),
        "login_timeout": 60,
    }
    key = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE")
    if not key:
        raise ValueError(
            "Register your public key; set SNOWFLAKE_PRIVATE_KEY_FILE in ignored .env"
        )
    args["private_key_file"] = str(Path(key).expanduser())
    return snowflake.connector.connect(**args)


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def passages(path, limit=5000):
    if path.suffixes[-2:] in [[".md", ".xz"], [".txt", ".xz"]]:
        with lzma.open(path, "rt", encoding="utf-8", errors="replace") as stream:
            lines = stream.read().splitlines()
    else:
        lines = path.read_text(errors="replace").splitlines()
    text = []
    start = 1
    size = 0
    ordinal = 0
    for number, line in enumerate(lines, 1):
        if size + len(line) > limit and text:
            yield ordinal, start, number - 1, "\n".join(text)
            ordinal += 1
            text = []
            start = number
            size = 0
        for at in range(0, max(len(line), 1), limit):
            piece = line[at : at + limit]
            if len(line) > limit:
                if text:
                    yield ordinal, start, number - 1, "\n".join(text)
                    ordinal += 1
                    text = []
                    size = 0
                yield ordinal, number, number, piece
                ordinal += 1
                start = number + 1
            else:
                text.append(piece)
                size += len(piece) + 1
    if text:
        yield ordinal, start, len(lines), "\n".join(text)


def put_asset(cur, path, prefix, filename):
    with tempfile.TemporaryDirectory(prefix="gqh-stage-") as folder:
        staged = Path(folder) / filename
        try:
            os.link(path.resolve(), staged)
        except OSError:
            shutil.copyfile(path, staged)
        cur.execute(
            f"PUT {literal('file://' + str(staged))} @GQH.RAW.ASSETS/{prefix}/ SOURCE_COMPRESSION=NONE AUTO_COMPRESS=FALSE OVERWRITE=FALSE PARALLEL=4"
        )
        rows = cur.fetchall()
        if not rows or any(r[6] not in ["UPLOADED", "SKIPPED"] for r in rows):
            raise ValueError("Asset upload failed")
        return prefix + "/" + Path(str(rows[0][1])).name


def upload(cur, source, manifest, selected=None, publish=True):
    data = json.loads(manifest.read_text())
    if "version" in data:
        raise ValueError("Use a newly inventoried manifest for uploads")
    version = sha(manifest)
    collection = data["collection"]
    if collection not in ["market", "context", "results"]:
        raise ValueError("Unknown collection")
    files = (
        data["files"]
        if selected is None
        else [r for r in data["files"] if r["path"] in selected]
    )
    for number, r in enumerate(files, 1):
        relative = Path(r["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid path")
        path = source / relative
        if sha(path) != r["sha256"]:
            raise ValueError(f"Source changed: {path}")
        prefix = f"{collection}/{version}/{r['sha256']}"
        cur.execute(
            "SELECT LOADED FROM GQH.RAW.FILES WHERE COLLECTION=%s AND VERSION=%s AND SOURCE_PATH=%s",
            (collection, version, r["path"]),
        )
        existing = cur.fetchone()
        if existing and existing[0]:
            print(f"[{number}/{len(data['files'])}] cached {r['path']}", flush=True)
            continue
        stage_path = put_asset(cur, path, prefix, r["sha256"] + ".asset")
        if collection == "market" and path.suffix == ".parquet":
            cur.execute(
                "SELECT COUNT(*) FROM GQH.MARKET.OBSERVATIONS WHERE SOURCE_PATH=%s AND VERSION=%s",
                (r["path"], version),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    f"COPY INTO GQH.MARKET.OBSERVATIONS(DATA,SOURCE_PATH,VERSION) FROM (SELECT $1,{literal(r['path'])},{literal(version)} FROM @GQH.RAW.ASSETS/{stage_path}) FILE_FORMAT=(FORMAT_NAME='GQH.RAW.PARQUET') ON_ERROR=ABORT_STATEMENT"
                )
        if (
            collection == "context"
            and "original" not in path.relative_to(source).parts
            and path.suffix.lower() in [".md", ".txt"]
        ):
            rows = [
                (r["sha256"], r["path"], i, a, b, text)
                for i, a, b, text in passages(path)
                if text.strip()
            ]
            cur.execute(
                "SELECT COUNT(*) FROM GQH.CONTEXT.PASSAGES WHERE DOC_SHA=%s AND SOURCE_PATH=%s",
                (r["sha256"], r["path"]),
            )
            count = cur.fetchone()[0]
            if count not in [0, len(rows)]:
                raise ValueError("Incomplete existing context chunks")
            if rows and count == 0:
                cur.execute("BEGIN")
                try:
                    for start in range(0, len(rows), 100):
                        cur.executemany(
                            "INSERT INTO GQH.CONTEXT.PASSAGES(DOC_SHA,SOURCE_PATH,ORDINAL,START_LINE,END_LINE,BODY) VALUES (%s,%s,%s,%s,%s,%s)",
                            rows[start : start + 100],
                        )
                    cur.execute("COMMIT")
                except Exception:
                    cur.execute("ROLLBACK")
                    raise
        cur.execute(
            "MERGE INTO GQH.RAW.FILES t USING (SELECT %s COLLECTION,%s VERSION,%s SOURCE_PATH,%s SHA256,%s BYTES,%s STAGE_PATH) s ON t.COLLECTION=s.COLLECTION AND t.VERSION=s.VERSION AND t.SOURCE_PATH=s.SOURCE_PATH WHEN MATCHED THEN UPDATE SET LOADED=TRUE WHEN NOT MATCHED THEN INSERT(COLLECTION,VERSION,SOURCE_PATH,SHA256,BYTES,STAGE_PATH,LOADED) VALUES(s.COLLECTION,s.VERSION,s.SOURCE_PATH,s.SHA256,s.BYTES,s.STAGE_PATH,TRUE)",
            (collection, version, r["path"], r["sha256"], r["bytes"], stage_path),
        )
        print(f"[{number}/{len(data['files'])}] uploaded {r['path']}", flush=True)
    if publish:
        publish_manifest(cur, manifest)
        print("Collection version:", version, flush=True)


def upload_parallel(source, manifest, workers=4):
    data = json.loads(manifest.read_text())
    version = sha(manifest)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("USE WAREHOUSE GQH_WH")
        cur.execute(
            "SELECT SOURCE_PATH,SHA256 FROM GQH.RAW.FILES WHERE COLLECTION=%s AND VERSION=%s AND LOADED=TRUE",
            (data["collection"], version),
        )
        cached = dict(cur.fetchall())
    pending = [r["path"] for r in data["files"] if cached.get(r["path"]) != r["sha256"]]
    print(
        f"{data['collection']}: {len(data['files']) - len(pending)} cached; {len(pending)} pending; {workers} workers",
        flush=True,
    )

    def run(paths):
        with connect() as conn, conn.cursor() as cur:
            cur.execute("USE WAREHOUSE GQH_WH")
            upload(cur, source, manifest, selected=set(paths), publish=False)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(
            pool.map(
                run,
                [pending[i::workers] for i in range(workers) if pending[i::workers]],
            )
        )
    with connect() as conn, conn.cursor() as cur:
        cur.execute("USE WAREHOUSE GQH_WH")
        publish_manifest(cur, manifest)
    print("Collection version:", version, flush=True)


def publish_manifest(cur, manifest):
    data = json.loads(manifest.read_text())
    version = sha(manifest)
    collection = data["collection"]
    prefix = f"{collection}/{version}"
    stage_path = put_asset(cur, manifest, prefix, "manifest.json")
    cur.execute(
        "MERGE INTO GQH.RAW.FILES t USING (SELECT %s COLLECTION,%s VERSION) s ON t.COLLECTION=s.COLLECTION AND t.VERSION=s.VERSION AND t.SOURCE_PATH='@manifest' WHEN NOT MATCHED THEN INSERT(COLLECTION,VERSION,SOURCE_PATH,SHA256,BYTES,STAGE_PATH,LOADED) VALUES(s.COLLECTION,s.VERSION,'@manifest',%s,%s,%s,TRUE)",
        (collection, version, version, manifest.stat().st_size, stage_path),
    )


def retrieve_manifest(cur, collection, output, version=None):
    sql = "SELECT f.SOURCE_PATH,f.SHA256,f.BYTES,f.VERSION FROM GQH.RAW.FILES f JOIN GQH.RAW.FILES m ON f.COLLECTION=m.COLLECTION AND f.VERSION=m.VERSION AND m.SOURCE_PATH='@manifest' AND m.LOADED=TRUE WHERE f.COLLECTION=%s AND f.LOADED=TRUE AND f.SOURCE_PATH<>'@manifest'"
    values = [collection]
    if version:
        sql += " AND f.VERSION=%s"
        values.append(version)
    sql += " QUALIFY ROW_NUMBER() OVER (PARTITION BY f.SOURCE_PATH ORDER BY f.IMPORTED_AT DESC)=1 ORDER BY f.SOURCE_PATH"
    cur.execute(sql, values)
    rows = cur.fetchall()
    if not rows:
        raise ValueError("No completed collection manifest is published")
    data = {
        "collection": collection,
        "files": [
            {"path": r[0], "sha256": r[1], "bytes": r[2], "version": r[3]} for r in rows
        ],
        "bytes": sum(r[2] for r in rows),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n")
    data["version"] = version or sha(output)
    output.write_text(json.dumps(data, indent=2) + "\n")
    print("Manifest:", collection, data["version"], len(rows), "files")


def verify(cur, manifest):
    data = json.loads(manifest.read_text())
    version = data.get("version") or sha(manifest)
    cur.execute(
        "SELECT SOURCE_PATH,SHA256,BYTES,STAGE_PATH,VERSION FROM GQH.RAW.FILES WHERE COLLECTION=%s AND LOADED=TRUE",
        (data["collection"],),
    )
    remote = {(r[0], r[4]): r for r in cur.fetchall()}
    staged = {}
    versions = {r.get("version", version) for r in data["files"]}
    for v in versions:
        cur.execute("LIST " + literal(f"@GQH.RAW.ASSETS/{data['collection']}/{v}/"))
        staged.update({str(r[0]): r[1] for r in cur.fetchall()})
    for row in data["files"]:
        record = remote.get((row["path"], row.get("version", version)))
        if not record or record[1] != row["sha256"] or record[2] != row["bytes"]:
            raise ValueError("Incomplete remote inventory: " + row["path"])
        sizes = [
            size
            for name, size in staged.items()
            if name.endswith("/" + record[3]) or name == record[3]
        ]
        if sizes != [row["bytes"]]:
            raise ValueError("Missing or incomplete stage object: " + row["path"])
    print("Verified stage sizes and catalog hashes:", len(data["files"]))


def fetch_assets(source, manifest, pattern=None, workers=4):
    data = json.loads(manifest.read_text())
    version = data.get("version") or sha(manifest)
    selected = [
        r for r in data["files"] if not pattern or fnmatch.fnmatch(r["path"], pattern)
    ]
    if not selected:
        raise ValueError("No assets match --path")
    with connect() as conn, conn.cursor() as cur:
        cur.execute("USE WAREHOUSE GQH_WH")
        cur.execute(
            "SELECT SOURCE_PATH,VERSION,STAGE_PATH,SHA256 FROM GQH.RAW.FILES WHERE COLLECTION=%s AND LOADED=TRUE",
            (data["collection"],),
        )
        remote = {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}
    pending = []
    for r in selected:
        relative = Path(r["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid manifest path")
        if data["collection"] == "market" and relative.parts[0] == "data":
            relative = Path(*relative.parts[1:])
        path = source / relative
        if path.exists() and sha(path) == r["sha256"]:
            continue
        record = remote.get((r["path"], r.get("version", version)))
        if not record or record[1] != r["sha256"]:
            raise ValueError("Unknown asset or catalog hash mismatch")
        pending.append((r, path, record[0]))
    lock = threading.Lock()
    done = len(selected) - len(pending)
    print(f"{done}/{len(selected)} cached; {workers} download workers", flush=True)

    def run(rows):
        nonlocal done
        with connect() as conn, conn.cursor() as cur:
            for r, path, stage in rows:
                path.parent.mkdir(parents=True, exist_ok=True)
                cur.execute(
                    f"GET {literal('@GQH.RAW.ASSETS/' + stage)} {literal('file://' + str(path.parent.resolve()) + '/')}"
                )
                fetched = path.parent / Path(stage).name
                if fetched != path:
                    fetched.replace(path)
                if sha(path) != r["sha256"]:
                    raise ValueError("Downloaded SHA-256 mismatch")
                with lock:
                    done += 1
                    print(f"[{done}/{len(selected)}] verified {r['path']}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(
            pool.map(
                run,
                [pending[i::workers] for i in range(workers) if pending[i::workers]],
            )
        )
    print("Downloaded and verified", len(selected), "files", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "inventory",
            "manifest",
            "setup",
            "upload",
            "verify",
            "fetch",
            "search",
            "sql",
            "index-context",
        ],
    )
    parser.add_argument("--source", type=Path, default=Path("data"))
    parser.add_argument(
        "--collection", choices=["market", "context", "results"], default="market"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--version")
    parser.add_argument("--path", help="Fetch only source paths matching this glob")
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if (
        args.action in ["inventory", "manifest", "upload", "verify", "fetch"]
        and not args.manifest
    ):
        parser.error("--manifest is required")
    if args.action == "inventory":
        value = inventory(args.source, args.collection, args.path)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(value, indent=2) + "\n")
        print(len(value["files"]), "files;", round(value["bytes"] / 1024**3, 3), "GiB")
        return
    with connect() as conn, conn.cursor() as cur:
        if args.action == "manifest":
            retrieve_manifest(cur, args.collection, args.manifest, args.version)
        elif args.action == "setup":
            with (
                Path(__file__).resolve().parents[1] / "tools/sql/setup.sql"
            ).open() as stream:
                for c in conn.execute_stream(stream):
                    print(c.fetchall())
        elif args.action == "index-context":
            with (
                Path(__file__).resolve().parents[1] / "tools/sql/search.sql"
            ).open() as stream:
                for c in conn.execute_stream(stream):
                    print(c.fetchall())
        elif args.action == "upload":
            cur.execute("USE WAREHOUSE GQH_WH")
            upload_parallel(args.source, args.manifest, args.workers)
        elif args.action == "verify":
            verify(cur, args.manifest)
        elif args.action == "fetch":
            fetch_assets(args.source, args.manifest, args.path, args.workers)
        elif args.action == "search":
            if not args.query:
                parser.error("--query is required")
            cur.execute("USE WAREHOUSE GQH_WH")
            request = json.dumps(
                {
                    "query": args.query,
                    "columns": [
                        "BODY",
                        "SOURCE_PATH",
                        "DOC_SHA",
                        "START_LINE",
                        "END_LINE",
                    ],
                    "limit": args.limit,
                }
            )
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s,%s)",
                ("GQH.CONTEXT.SEARCH", request),
            )
            print(cur.fetchone()[0])
        else:
            if not args.query or not args.query.lstrip().upper().startswith(
                ("SELECT", "WITH", "SHOW", "DESCRIBE", "LIST")
            ):
                parser.error("--query must be a read query")
            cur.execute("USE WAREHOUSE GQH_WH")
            cur.execute(args.query)
            print(json.dumps(cur.fetchall(), default=str, indent=2))


if __name__ == "__main__":
    main()
