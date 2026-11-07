"""Ecnalanif — reading the Mission Charter. The fleet stays docked until it is signed."""
from __future__ import annotations

import hashlib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CHARTER = os.path.join(HERE, "THESIS_D.md")


def read() -> str:
    with open(CHARTER, encoding="utf-8") as f:
        return f.read()


def signed(text: str | None = None) -> tuple[bool, str]:
    text = read() if text is None else text
    m = re.search(r"\*\*Date signed:\*\*\s*([^|&\n]*)", text)
    val = (m.group(1) if m else "").strip().strip("_").strip()
    return (bool(re.search(r"\d", val)), val)


def amendment_initialed(n: int, text: str | None = None) -> bool:
    """True once Opie has initialed AMENDMENT n (a name or date on its **Initialed:** line)."""
    text = read() if text is None else text
    m = re.search(rf"\n## AMENDMENT {n}\b(.*?)(?=\n## |\Z)", text, re.S)
    if not m:
        return False
    i = re.search(r"\*\*Initialed:\*\*\s*([^|&\n]*)", m.group(1))
    val = (i.group(1) if i else "").replace("(Opie)", "").strip().strip("_").strip()
    return bool(re.search(r"[A-Za-z0-9]", val))


def body_hash(text: str | None = None) -> str:
    """Hash of everything before the first amendment, so dated amendments don't trip the lock."""
    text = read() if text is None else text
    body = re.split(r"\n## AMENDMENT", text, maxsplit=1)[0]
    body = re.sub(r"\*\*Date signed:\*\*[^\n]*", "", body)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
