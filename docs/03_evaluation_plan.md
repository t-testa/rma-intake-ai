# 3. Evaluation plan: agreed before the agent was built

These thresholds were set with the RMA desk lead and the product owner **before any model was trained**. The agent ships only if every gate passes on the held-out test set. Confidence thresholds may be tuned on the validation set, never on the test set.

## Data split

- **Test set:** every email written with a phrasing held out of training (the last phrasing of each failure category, in each language), plus 20% of the rest, sampled at random. This measures how the agent handles wording it has never seen, not only wording it memorized.
- **Validation set:** 20% of the remainder, used only to choose confidence thresholds.
- **Training set:** everything else.

## Gates

| ID | What we measure | Threshold | Why this number |
|---|---|---|---|
| E1 | Non-RMA emails drafted as an RMA | **0** | A false RMA ships a replacement server for nothing. No tolerance. |
| E2 | Safety emails (smoke, burning, sparks) escalated to a person | **100%** | Safety cannot depend on a probability. |
| E3 | Failure category correct, on RMAs the agent drafts | **≥ 95%** | Better than today's 91.0% (9.0% miscategorized). |
| E4 | Serials extracted exactly, where the email contains one | **≥ 98%** | A wrong serial means the wrong unit and the wrong warranty. |
| E5 | Ownership and warranty decision correct, on drafted RMAs | **100%** | Deterministic lookup; replaces today's 4.7% error rate. |
| E6 | RMA requests drafted without human triage | **≥ 50%** | Below this, the change is not worth the operational cost. |
| E7 | French vs English category accuracy | **≤ 5 points apart** | French customers must not get a worse service. |
| E8 | Category accuracy on phrasings never seen in training | **≥ 90%** | Real customers will not write like the training data. |

## What happens on a miss

- A **hard gate** (E1, E2, E5) failing blocks release, whatever the other numbers say.
- A **soft gate** (E3, E4, E6, E7, E8) failing goes back to the product owner with the error analysis and a recommendation: more training data, a stricter review threshold, or a narrower scope.

## After release

Measure monthly against the baseline in [01_discovery.md](01_discovery.md): time from email to RMA number, follow-up rate, miscategorization rate, warranty errors, safety escalation time. Sample 10% of auto-drafted RMAs for human review to catch drift.
