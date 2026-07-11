"""Hosts-file based website blocking."""

import threading
import time
from pathlib import Path

HOSTS = Path(r"C:\Windows\System32\drivers\etc\hosts")
FL_START = "# FocusLock-START"
FL_END = "# FocusLock-END"


def _strip(content):
    """Remove everything between FocusLock markers."""
    out, inside = [], False
    for line in content.splitlines():
        if FL_START in line:
            inside = True
            continue
        if FL_END in line:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def normalize_domain(value):
    value = (value or "").strip().lower()
    for prefix in ("https://", "http://", "www."):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.split("/")[0].split("?")[0].split("#")[0]
    return value.strip(".")


def is_valid_domain(domain):
    if not domain or " " in domain or len(domain) > 253:
        return False
    parts = domain.split(".")
    if len(parts) < 2:
        return False
    for part in parts:
        if not part or len(part) > 63:
            return False
        if not all(c.isalnum() or c == "-" for c in part):
            return False
        if part.startswith("-") or part.endswith("-"):
            return False
    return True


def block_sites(domains):
    """Inject hosts-file entries for *domains* between FocusLock markers."""
    clean = []
    for domain in domains:
        d = normalize_domain(domain)
        if d and d not in clean:
            clean.append(d)
    if not clean:
        unblock_sites()
        return True
    try:
        content = _strip(HOSTS.read_text(encoding="utf-8"))
        entries = []
        for domain in clean:
            entries.append(f"127.0.0.1 {domain}")
            if not domain.startswith("www."):
                entries.append(f"127.0.0.1 www.{domain}")
        block = (
            f"\n{FL_START}\n"
            + "\n".join(entries)
            + f"\n{FL_END}\n"
        )
        HOSTS.write_text(content + block, encoding="utf-8")
        return True
    except PermissionError:
        return False


def unblock_sites(_domains=None):
    """Remove all FocusLock entries from the hosts file."""
    try:
        HOSTS.write_text(
            _strip(HOSTS.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
    except Exception:
        pass
