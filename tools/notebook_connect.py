"""Open the private notebook worker through an SSH tunnel."""

import argparse
import ast
import subprocess
import time
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="gqh")
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--remote-port", type=int, default=8888)
    args = parser.parse_args()
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "UserKnownHostsFile=" + str(args.known_hosts.expanduser()),
        "-i",
        str(args.key.expanduser()),
    ]
    target = args.user + "@" + args.host
    config = subprocess.check_output(
        ssh + [target, "cat ~/.jupyter/jupyter_server_config.py"], text=True
    )
    token = next(
        ast.literal_eval(line.split("=", 1)[1].strip())
        for line in config.splitlines()
        if line.startswith("c.IdentityProvider.token")
    )
    process = subprocess.Popen(
        ssh
        + ["-N", "-L", f"127.0.0.1:{args.port}:127.0.0.1:{args.remote_port}", target]
    )
    try:
        time.sleep(1)
        if process.poll() is not None:
            raise RuntimeError("SSH tunnel failed")
        webbrowser.open(f"http://127.0.0.1:{args.port}/lab?token={token}")
        print("Notebook tunnel running. Ctrl-C closes it.", flush=True)
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
