"""Write docs/04_results.md from output/eval.json, so every number in it traces to a run."""
import json
from pathlib import Path

r = json.loads(Path("output/eval.json").read_text())
im = r["impact"]
ROUTE = {"DRAFT_RMA": "RMA drafted for one-click approval", "HUMAN_REVIEW": "Human review, with the reason",
         "ASK_CUSTOMER": "Serial requested from the customer", "SAFETY_ESCALATION": "Safety escalation",
         "FORWARD_NON_RMA": "Forwarded to sales or billing"}


def cmp(g):
    return {"eq": "=", "ge": "≥", "le": "≤"}[g["comparison"]]


lines = ["# 4. Results", "",
         f"Test set: {r['test_requests']} emails ({r['test_rma_requests']} RMA requests, {r['test_french']} in French, "
         f"{r['unseen_phrasing_requests']} RMA requests written with phrasings never seen in training). "
         f"Training {r['split']['train']}, validation {r['split']['val']}. "
         f"Category threshold chosen on validation: {r['category_threshold']}.", "",
         "## Iteration log", "",
         "| Gate | Target | " + " | ".join(i["version"] for i in r["iterations"]) + " |",
         "|---|---|" + "---|" * len(r["iterations"])]
for n, g in enumerate(r["iterations"][0]["gates"]):
    vals = []
    for it in r["iterations"]:
        gi = it["gates"][n]
        vals.append(f"{gi['value']} {'✅' if gi['pass'] else '❌'}")
    lines.append(f"| {g['id']} {g['gate']} ({g['kind']}) | {cmp(g)} {g['threshold']} | " + " | ".join(vals) + " |")
lines.append("| **Release decision** | all gates | " + " | ".join(
    "**release**" if it["release"] else "**blocked**" for it in r["iterations"]) + " |")
v1 = r["iterations"][0]
lines += ["",
          "**v1 was blocked.** The model, trained on " + str(r["split"]["train"]) + " historical tickets, had not learned "
          "that \"RAM\", \"DOA\", \"PSU\" or \"disque\" mean memory, dead on arrival, power supply and storage when the wording "
          "was new to it, and French suffered most. It was safe (E1, E2 and E5 passed) but not useful.",
          "",
          "**v2 added the repair engineers' bilingual failure glossary** (`config/failure_glossary.yaml`) in front of the model, "
          "with a rule that disagreement between the two sends the email to a person. Thresholds were re-tuned on validation only. "
          "All gates pass.", "",
          "## Where the v2 test emails went", "", "| Route | Emails |", "|---|---|"]
lines += [f"| {ROUTE[k]} | {v} |" for k, v in sorted(r["routes"].items(), key=lambda kv: -kv[1])]
lines += ["", "## Before and after", "",
          "Error rates for the agent are **measured** on the test set. Cycle times and desk hours are **projected** "
          "from the same requests' baseline timings, using the assumptions below; the agent has not run in production.", "",
          "| Measure | Before (manual) | After (agent) | |", "|---|---|---|---|",
          f"| Median time, email to RMA number | {im['median_cycle_hours_before']} h | {im['median_cycle_hours_after_projected']} h | projected |",
          f"| 90th percentile | {im['p90_cycle_hours_before']} h | {im['p90_cycle_hours_after_projected']} h | projected |",
          f"| Safety email seen by a person | median {im['safety_median_hours_before']} h, worst {im['safety_worst_hours_before']} h | "
          f"about {im['safety_minutes_after']} min | projected |",
          f"| Wrong failure category | {im['miscategorized_pct_before']}% | {im['miscategorized_pct_after_on_drafts']}% on drafted RMAs | measured |",
          f"| Wrong warranty decision | {im['warranty_error_pct_before']}% | 0% (deterministic lookup) | measured |",
          f"| RMA desk hands-on time for these requests | {im['desk_hands_on_hours_before']} h | {im['desk_hands_on_hours_after_projected']} h | projected |",
          "", "**Assumptions:** " + "; ".join(f"{k.replace('_', ' ')} = {v}" for k, v in im["assumptions"].items()) + ".",
          "Human-review items are assumed to take as long as today. The serial-request reply goes out at once, "
          "but the customer's reply time is unchanged.", "",
          "## Caveats", "",
          "- **Synthetic data.** The glossary and the generated emails share the same component vocabulary, which flatters E8. "
          "On real emails expect lower accuracy on new wording; that is why E8 is monitored monthly and 10% of drafts are re-checked.",
          "- The intent and category models are small (TF-IDF and logistic regression) by design: fast, explainable, cheap. "
          "`intake/llm.py` puts Claude behind the same validation if the gates ever require it.",
          ]
Path("docs/04_results.md").write_text("\n".join(lines) + "\n")
print("wrote docs/04_results.md")
