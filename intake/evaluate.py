"""Score the agent against the gates in docs/03_evaluation_plan.md."""
import pandas as pd

from .agent import AUTO, SAFETY_ESC

GATES = [  # id, description, kind, threshold, comparison
    ("E1", "Non-RMA emails drafted as an RMA", "hard", 0, "eq"),
    ("E2", "Safety emails escalated to a person", "hard", 100.0, "ge"),
    ("E3", "Category correct on drafted RMAs (%)", "soft", 95.0, "ge"),
    ("E4", "Serials extracted exactly where present (%)", "soft", 98.0, "ge"),
    ("E5", "Ownership and warranty correct on drafted RMAs (%)", "hard", 100.0, "ge"),
    ("E6", "RMA requests drafted without triage (%)", "soft", 50.0, "ge"),
    ("E7", "French vs English category accuracy gap (points)", "soft", 5.0, "le"),
    ("E8", "Category accuracy on unseen phrasings (%)", "soft", 90.0, "ge"),
]


def pct(x):
    return None if pd.isna(x) else round(100 * float(x), 1)


def warranty_truth(row, base):
    from datetime import date, datetime
    serials = row["true_serials"].split()
    out = True
    for s in serials:
        b = base.loc[s]
        ship = date.fromisoformat(b["ship_date"])
        m = ship.month - 1 + int(b["warranty_months"])
        end = date(ship.year + m // 12, m % 12 + 1, min(ship.day, 28))
        out &= datetime.fromisoformat(row["received_at"]).date() <= end
    return out


def evaluate(requests: pd.DataFrame, decisions: pd.DataFrame, base: pd.DataFrame) -> dict:
    d = requests.merge(decisions, on="request_id")
    b = base.set_index("serial")
    rma = d[d.true_is_rma & ~d.true_safety]
    auto = d[d.route == AUTO]
    parts = d["phrase_key"].str.split("|")
    unseen = d[(parts.str[2] == parts.str[3]) & d.true_is_rma & ~d.true_safety]

    def cat_acc(x):
        return pct((x.category == x.true_category).mean()) if len(x) else None

    with_serial = d[d.serial_in_text & d.true_is_rma & (d.route != SAFETY_ESC) & (d.route != "FORWARD_NON_RMA")]
    serial_ok = with_serial.apply(lambda r: sorted(r["serials"]) == sorted(r["true_serials"].split()), axis=1)
    auto_ok = auto.apply(lambda r: r["true_owned"] and bool(r["in_warranty"]) == warranty_truth(r, b), axis=1)
    rma_with_cat = rma[rma.category != ""]
    fr = cat_acc(rma_with_cat[rma_with_cat.language == "fr"])
    en = cat_acc(rma_with_cat[rma_with_cat.language == "en"])

    values = {
        "E1": int((auto.true_is_rma == False).sum()),  # noqa: E712
        "E2": pct((d[d.true_safety].route == SAFETY_ESC).mean()),
        "E3": cat_acc(auto),
        "E4": pct(serial_ok.mean()) if len(with_serial) else None,
        "E5": pct(auto_ok.mean()) if len(auto) else None,
        "E6": pct((rma.route == AUTO).mean()),
        "E7": round(abs(fr - en), 1) if fr is not None and en is not None else None,
        "E8": cat_acc(unseen[unseen.category != ""]),
    }
    results = []
    for gid, desc, kind, thr, cmp in GATES:
        v = values[gid]
        ok = v is not None and (v == thr if cmp == "eq" else v >= thr if cmp == "ge" else v <= thr)
        results.append({"id": gid, "gate": desc, "kind": kind, "threshold": thr, "comparison": cmp, "value": v,
                        "pass": bool(ok)})
    routes = d.route.value_counts().to_dict()
    return {
        "test_requests": int(len(d)), "test_rma_requests": int(len(rma)), "test_french": int((d.language == "fr").sum()),
        "unseen_phrasing_requests": int(len(unseen)),
        "routes": {k: int(v) for k, v in routes.items()},
        "french_category_accuracy": fr, "english_category_accuracy": en,
        "overall_category_accuracy": cat_acc(rma_with_cat),
        "gates": results, "release": all(r["pass"] for r in results),
    }
