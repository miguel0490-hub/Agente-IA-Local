"""Elige el primer puerto TCP libre en un rango (para evitar conflicto con Streamlit)."""
from __future__ import annotations

import subprocess
import sys

BASE = 8501
MAX_PORT = 8519


def _listening_tcp_ports() -> set[int]:
    proc = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout or ""
    in_use: set[int] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0].upper() != "TCP":
            continue
        state = parts[3].upper()
        if state not in ("LISTENING", "ESCUCHANDO"):
            continue
        local = parts[1]
        if "]:" in local:
            _, _, tail = local.partition("]:")
            addr = tail
        elif ":" in local:
            addr = local.rsplit(":", 1)[-1]
        else:
            continue
        if addr.isdigit():
            in_use.add(int(addr))
    return in_use


def main() -> None:
    busy = _listening_tcp_ports()
    for port in range(BASE, MAX_PORT + 1):
        if port not in busy:
            print(port)
            return
    print(BASE, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
