"""Ecnalanif — writes the Bridge (Bridge.html): one self-contained page, no server, no internet."""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "bridge_template.html")
OUT = os.path.join(HERE, "Bridge.html")


def write(state: dict) -> str:
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    data = json.dumps(state, separators=(",", ":")).replace("</", "<\\/")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html.replace("/*__STATE__*/null", data))
    os.replace(tmp, OUT)
    return OUT
