# -*- coding: utf-8 -*-
"""SSH-хелпер деплоя: удалённые команды и передача файлов.

Использование:
  python deploy/ssh_exec.py cmd "<удалённая команда>"
  python deploy/ssh_exec.py put <локальный> <удалённый>
  python deploy/ssh_exec.py get <удалённый> <локальный>

Учётные данные читаются из deploy/credentials.json (не коммитится).
"""
import json
import sys
from pathlib import Path

import paramiko

CREDS = Path(__file__).with_name("credentials.json")


def connect() -> paramiko.SSHClient:
    data = json.loads(CREDS.read_text(encoding="utf-8"))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(data["host"], username=data["user"],
                    password=data["password"], timeout=30, allow_agent=False,
                    look_for_keys=False)
    return client


def run(cmd: str) -> int:
    client = connect()
    try:
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err:
            print(err, file=sys.stderr, end="" if err.endswith("\n") else "\n")
        return code
    finally:
        client.close()


def put(local: str, remote: str) -> None:
    client = connect()
    try:
        sftp = client.open_sftp()
        # создаём родительские каталоги
        parent = str(Path(remote).parent).replace("\\", "/")
        if parent and parent != "/":
            _mkdir_p(sftp, parent)
        sftp.put(local, remote)
        sftp.close()
        print(f"uploaded {local} -> {remote}")
    finally:
        client.close()


def get(remote: str, local: str) -> None:
    client = connect()
    try:
        sftp = client.open_sftp()
        sftp.get(remote, local)
        sftp.close()
        print(f"downloaded {remote} -> {local}")
    finally:
        client.close()


def _mkdir_p(sftp, path):
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    action = sys.argv[1]
    if action == "cmd":
        return run(" ".join(sys.argv[2:]) or "true")
    if action == "put" and len(sys.argv) == 4:
        put(sys.argv[2], sys.argv[3])
        return 0
    if action == "get" and len(sys.argv) == 4:
        get(sys.argv[2], sys.argv[3])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
