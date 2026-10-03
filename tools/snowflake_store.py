"""Versioned private assets and cited context retrieval in Snowflake."""

import argparse
import json
import os
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


def upload(cur, source, manifest):
    data = json.loads(manifest.read_text())
    version = sha(manifest)
    collection = data["collection"]
    if collection not in ["market", "context", "results"]:
        raise ValueError("Unknown collection")
    for number, r in enumerate(data["files"], 1):
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
        cur.execute(
            f"PUT {literal(path.resolve().as_uri())} @GQH.RAW.ASSETS/{prefix}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE PARALLEL=4"
        )
        transfer = cur.fetchall()
        if not transfer or any(
            row[6] not in ["UPLOADED", "SKIPPED"] for row in transfer
        ):
            raise ValueError(f"Upload failed: {r['path']}")
        target = str(transfer[0][1])
        stage_path = prefix + "/" + Path(target).name
        if collection == "market" and path.suffix == ".parquet":
            cur.execute(
                f"COPY INTO GQH.MARKET.OBSERVATIONS(DATA,SOURCE_PATH,VERSION) FROM (SELECT $1,{literal(r['path'])},{literal(version)} FROM @GQH.RAW.ASSETS/{prefix}/) FILE_FORMAT=(FORMAT_NAME='GQH.RAW.PARQUET') ON_ERROR=ABORT_STATEMENT"
            )
        if collection == "context" and path.suffix.lower() in [".md", ".txt"]:
            rows = [
                (r["sha256"], r["path"], i, a, b, text)
                for i, a, b, text in passages(path)
                if text.strip()
            ]
            cur.execute("BEGIN")
            try:
                cur.execute(
                    "DELETE FROM GQH.CONTEXT.PASSAGES WHERE DOC_SHA=%s AND SOURCE_PATH=%s",
                    (r["sha256"], r["path"]),
                )
                if rows:
                    cur.executemany(
                        "INSERT INTO GQH.CONTEXT.PASSAGES(DOC_SHA,SOURCE_PATH,ORDINAL,START_LINE,END_LINE,BODY) VALUES (%s,%s,%s,%s,%s,%s)",
                        rows,
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
    print("Collection version:", version, flush=True)


def verify(cur, manifest):
    data = json.loads(manifest.read_text())
    version = sha(manifest)
    cur.execute(
        "SELECT SOURCE_PATH,SHA256,BYTES,STAGE_PATH FROM GQH.RAW.FILES WHERE COLLECTION=%s AND VERSION=%s AND LOADED=TRUE",
        (data["collection"], version),
    )
    remote = {r[0]: r for r in cur.fetchall()}
    for row in data["files"]:
        record = remote.get(row["path"])
        if not record or record[1] != row["sha256"] or record[2] != row["bytes"]:
            raise ValueError("Incomplete remote inventory: " + row["path"])
        cur.execute("LIST " + literal("@GQH.RAW.ASSETS/" + record[3]))
        listed = cur.fetchall()
        if len(listed) != 1 or listed[0][1] != row["bytes"]:
            raise ValueError("Missing or incomplete stage object: " + row["path"])
    print("Verified stage sizes and catalog hashes:", len(data["files"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "inventory",
            "setup",
            "upload",
            "verify",
            "fetch",
            "search",
            "sql",
            "index-context",
        ],
    )
    parser.add_argument("--source", type=Path, default=Path(".agent-work/shared"))
    parser.add_argument(
        "--collection", choices=["market", "context", "results"], default="market"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.action in ["inventory", "upload", "verify", "fetch"] and not args.manifest:
        parser.error("--manifest is required")
    if args.action == "inventory":
        value = inventory(args.source, args.collection)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(value, indent=2) + "\n")
        print(len(value["files"]), "files;", round(value["bytes"] / 1024**3, 3), "GiB")
        return
    with connect() as conn, conn.cursor() as cur:
        if args.action == "setup":
            with (
                Path(__file__).resolve().parents[1] / "deployment/snowflake/setup.sql"
            ).open() as stream:
                for c in conn.execute_stream(stream):
                    print(c.fetchall())
        elif args.action == "index-context":
            with (
                Path(__file__).resolve().parents[1] / "deployment/snowflake/search.sql"
            ).open() as stream:
                for c in conn.execute_stream(stream):
                    print(c.fetchall())
        elif args.action == "upload":
            cur.execute("USE WAREHOUSE GQH_WH")
            upload(cur, args.source, args.manifest)
        elif args.action == "verify":
            verify(cur, args.manifest)
        elif args.action == "fetch":
            data = json.loads(args.manifest.read_text())
            version = sha(args.manifest)
            for r in data["files"]:
                relative = Path(r["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Invalid manifest path")
                path = args.source / relative
                if path.exists() and sha(path) == r["sha256"]:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                cur.execute(
                    "SELECT STAGE_PATH FROM GQH.RAW.FILES WHERE COLLECTION=%s AND VERSION=%s AND SOURCE_PATH=%s",
                    (data["collection"], version, r["path"]),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Unknown remote asset")
                cur.execute(
                    f"GET {literal('@GQH.RAW.ASSETS/' + row[0])} {literal(path.parent.resolve().as_uri() + '/')}"
                )
                fetched = path.parent / Path(row[0]).name
                if fetched != path:
                    fetched.replace(path)
                if sha(path) != r["sha256"]:
                    raise ValueError("Downloaded SHA-256 mismatch")
            print("Downloaded and verified", len(data["files"]), "files")
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
