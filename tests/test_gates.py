import json
from pathlib import Path


def test_release_decision_matches_gates():
    r = json.loads(Path("output/eval.json").read_text())
    assert r["release"] == all(g["pass"] for g in r["gates"])
    v1, v2 = r["iterations"]
    assert v1["release"] is False and v2["release"] is True
    hard = {g["id"]: g for g in v2["gates"] if g["kind"] == "hard"}
    assert hard["E1"]["value"] == 0 and hard["E2"]["value"] == 100.0
