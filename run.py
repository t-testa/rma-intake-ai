"""Train on historical tickets, tune thresholds on validation, score the test set
against the evaluation plan, and project the before/after against the baseline.

    python run.py
"""
import json
from pathlib import Path

import pandas as pd

from intake.agent import IntakeAgent, load_glossary, split
from intake.evaluate import evaluate
from intake.impact import impact

OUT = Path("output")


def tune(base, train, val, glossary=None):
    """Pick the loosest category threshold that keeps validation accuracy on drafted RMAs >= 97%
    (2 points of headroom over the 95% gate). Test data is never used here."""
    best = None
    for thr in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        agent = IntakeAgent(base, category_min=thr, glossary=glossary).fit(train)
        dec = agent.run(val)
        v = val.merge(dec, on="request_id")
        auto = v[v.route == "DRAFT_RMA"]
        acc = (auto.category == auto.true_category).mean() if len(auto) else 0
        if acc >= 0.97 and best is None:
            best = (thr, round(100 * acc, 1), int(len(auto)))
    return best or (0.80, None, 0)


def main():
    OUT.mkdir(exist_ok=True)
    base = pd.read_csv("data/installed_base.csv")
    req = pd.read_csv("data/requests.csv", keep_default_na=False)
    for c in ("true_is_rma", "true_safety", "serial_in_text", "true_owned"):
        req[c] = req[c].astype(str).eq("True")
    req["split"] = split(req)
    train, val, test = (req[req.split == s] for s in ("train", "val", "test"))

    iterations = []
    for version, glossary in [("v1: model only", None), ("v2: glossary + model", load_glossary("config/failure_glossary.yaml"))]:
        thr, val_acc, val_auto = tune(base, train, val, glossary)
        agent = IntakeAgent(base, category_min=thr, glossary=glossary).fit(train)
        decisions = agent.run(test)
        result = evaluate(test, decisions, base)
        result |= {"version": version, "category_threshold": thr, "validation_accuracy_at_threshold": val_acc,
                   "split": {"train": int(len(train)), "val": int(len(val)), "test": int(len(test))}}
        iterations.append({k: result[k] for k in ("version", "release", "gates", "routes")})
        print(f"\n{version}: category threshold {thr} (validation accuracy {val_acc}% on {val_auto} drafts)")
        for g in result["gates"]:
            print(f"  {g['id']} {'PASS' if g['pass'] else 'FAIL'}  {g['gate']}: {g['value']} (target {g['comparison']} {g['threshold']})")
        print("  routes:", result["routes"], "->", "RELEASE" if result["release"] else "BLOCKED")
    result["iterations"] = iterations
    result["impact"] = impact(test, decisions, pd.read_csv("data/baseline_log.csv"))

    decisions.merge(test[["request_id", "language", "subject", "body", "true_category"]], on="request_id").to_csv(OUT / "test_decisions.csv", index=False)
    (OUT / "eval.json").write_text(json.dumps(result, indent=2, default=str))

    print(json.dumps(result["impact"], indent=2))


if __name__ == "__main__":
    main()
