"""Generate a teammate's private keys and shareable public-key bundle."""

import argparse
import base64
import json
import re
import shlex
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def prepare_registration(username, path):
    bundle = json.loads(path.read_text())
    name = username.lower()
    if bundle["snowflake_user"] != username or bundle["unix_user"] != name:
        raise ValueError("Bundle username mismatch")
    public = bundle["snowflake_public_key"]
    key = serialization.load_der_public_key(base64.b64decode(public, validate=True))
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
        raise ValueError("RSA key must have at least 2048 bits")
    ssh = bundle["ssh_public_key"]
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?", ssh):
        raise ValueError("Expected an Ed25519 SSH public key")
    folder = Path(".agent-work/runs")
    folder.mkdir(parents=True, exist_ok=True)
    sql = folder / f"{name}-register.sql"
    sql.write_text(
        f"USE ROLE ACCOUNTADMIN;\nCREATE USER {username} TYPE=PERSON DEFAULT_ROLE=GQH_PUBLISHER DEFAULT_WAREHOUSE=GQH_WH RSA_PUBLIC_KEY='{public}';\nGRANT ROLE GQH_PUBLISHER TO USER {username};\n"
    )
    script = folder / f"{name}-ssh-user.sh"
    script.write_text(
        "#!/bin/sh\nset -eu\n"
        + f"if id {name} >/dev/null 2>&1; then echo 'User already exists; inspect before changing keys'; exit 1; fi\nuseradd -m -s /bin/bash {name}\nchmod 700 /home/{name}\ninstall -d -m 700 -o {name} -g {name} /home/{name}/.ssh\nprintf '%s\\n' {shlex.quote(ssh)} > /home/{name}/.ssh/authorized_keys\nchown {name}:{name} /home/{name}/.ssh/authorized_keys\nchmod 600 /home/{name}/.ssh/authorized_keys\n"
    )
    print("Owner registration SQL:", sql)
    print("Owner SSH provisioning script:", script)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument(
        "--bundle", type=Path, help="Owner: prepare registration SQL from public keys"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,30}", args.username):
        parser.error("Use an uppercase Snowflake identifier with at most 31 characters")
    if args.bundle:
        prepare_registration(args.username, args.bundle)
        return
    name = args.username.lower()
    folder = Path(".agent-work/.secrets") / name
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    private = folder / "snowflake.p8"
    if not private.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        private.chmod(0o600)
    key = serialization.load_pem_private_key(private.read_bytes(), password=None)
    public = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    ssh = folder / "notebooks"
    if not ssh.exists():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(ssh)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    bundle = {
        "snowflake_user": args.username,
        "unix_user": name,
        "snowflake_public_key": public,
        "ssh_public_key": ssh.with_suffix(".pub").read_text().strip(),
    }
    output = Path(".agent-work/runs") / f"{name}-access.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2) + "\n")
    print("Share only:", output)
    print("Private keys retained in:", folder)


if __name__ == "__main__":
    main()
