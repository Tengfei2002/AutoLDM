from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

page = Path(__file__).resolve().parents[1] / "Hspice" / "va" / "parameter_network.html"
text = page.read_text(encoding="utf-8")

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts = []; self._script = False; self._buf = []
    def handle_starttag(self, tag, attrs):
        if tag == "script": self._script = True; self._buf = []
    def handle_data(self, data):
        if self._script: self._buf.append(data)
    def handle_endtag(self, tag):
        if tag == "script": self.scripts.append("".join(self._buf)); self._script = False

p = Parser(); p.feed(text)
assert "NMOS 参数关系网" in text
assert len(p.scripts) >= 2
m = re.search(r"const DATA=(\{.*?\});\s*\nconst canvas", p.scripts[0], re.S)
assert m, "embedded graph data is missing"
data = json.loads(m.group(1))
ids = {n["id"] for n in data["nodes"]}
assert len(ids) == len(data["nodes"]) == 13
assert all(a in ids and b in ids for a, b, *_ in data["edges"])
assert len(data["edges"]) == 21
assert data["stats"]["weights"] > 0 and data["stats"]["outputs"] > 0
assert len(data["allParams"]) == data["stats"]["physicalParameters"] > 300
full_ids = {p["id"] for p in data["allParams"]}
assert all(a in full_ids and b in full_ids for a, b in data["fullEdges"])
assert all(n["detail"]["parameters"] for n in data["nodes"]), "each graph node needs a visible detail label"
print(f"PASS: {len(data['nodes'])} nodes, {len(data['edges'])} edges, {data['stats']['weights']} NN weights, {data['stats']['outputs']} NN outputs")
