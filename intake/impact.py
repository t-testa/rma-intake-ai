"""Before/after against the baseline log.

Error rates in the "after" column are measured on the test set. Cycle times are
projected, not measured: the agent has not run in production. The assumptions
are stated next to every projected number and in docs/04_results.md.
"""
import pandas as pd

ASSUME = {
    "agent_minutes": 2,            # agent runs as the email arrives
    "approval_hours": 1.0,         # desk approves a drafted RMA within an hour (one click)
    "hands_on_triage_min": 10, "hands_on_entry_min": 15, "hands_on_approve_min": 1,
}


def impact(test: pd.DataFrame, dec: pd.DataFrame, log: pd.DataFrame) -> dict:
    d = test.merge(dec, on="request_id").merge(log, on="request_id")
    rma = d[d.true_is_rma & ~d.true_safety].copy()
    for c in ("cycle_hours", "info_wait_hours", "triage_hours", "erp_entry_hours"):
        rma[c] = pd.to_numeric(rma[c], errors="coerce").fillna(0)

    # Projected cycle time per route, built from the same requests' baseline components
    def after(r):
        if r.route == "DRAFT_RMA":
            return ASSUME["agent_minutes"] / 60 + ASSUME["approval_hours"]
        if r.route == "ASK_CUSTOMER":   # reply goes out at once; customer wait unchanged; then auto path
            return r.info_wait_hours + ASSUME["approval_hours"]
        return r.cycle_hours            # human review: same as today
    rma["after_hours"] = rma.apply(after, axis=1)

    safety = d[d.true_safety]
    hands_before = len(rma) * (ASSUME["hands_on_triage_min"] + ASSUME["hands_on_entry_min"])
    hands_after = sum(ASSUME["hands_on_approve_min"] if r == "DRAFT_RMA" else
                      ASSUME["hands_on_approve_min"] if r == "ASK_CUSTOMER" else
                      ASSUME["hands_on_triage_min"] + ASSUME["hands_on_entry_min"] for r in rma.route)
    drafted = d[d.route == "DRAFT_RMA"]
    return {
        "assumptions": ASSUME,
        "rma_requests_in_test": int(len(rma)),
        "median_cycle_hours_before": round(float(rma.cycle_hours.median()), 1),
        "median_cycle_hours_after_projected": round(float(rma.after_hours.median()), 1),
        "p90_cycle_hours_before": round(float(rma.cycle_hours.quantile(0.9)), 1),
        "p90_cycle_hours_after_projected": round(float(rma.after_hours.quantile(0.9)), 1),
        "safety_median_hours_before": round(float(pd.to_numeric(safety.safety_escalated_hours).median()), 1),
        "safety_worst_hours_before": round(float(pd.to_numeric(safety.safety_escalated_hours).max()), 1),
        "safety_minutes_after": ASSUME["agent_minutes"],
        "miscategorized_pct_before": round(100 * float(rma.miscategorized.astype(str).eq("True").mean()), 1),
        "miscategorized_pct_after_on_drafts": round(100 * float((drafted.category != drafted.true_category).mean()), 1)
        if len(drafted) else None,
        "warranty_error_pct_before": round(100 * float(rma.warranty_check_error.astype(str).eq("True").mean()), 1),
        "desk_hands_on_hours_before": round(hands_before / 60, 1),
        "desk_hands_on_hours_after_projected": round(hands_after / 60, 1),
    }
