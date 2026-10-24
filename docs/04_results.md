# 4. Results

Test set: 212 emails (157 RMA requests, 72 in French, 108 RMA requests written with phrasings never seen in training). Training 214, validation 54. Category threshold chosen on validation: 0.4.

## Iteration log

| Gate | Target | v1: model only | v2: glossary + model |
|---|---|---|---|
| E1 Non-RMA emails drafted as an RMA (hard) | = 0 | 0 ✅ | 0 ✅ |
| E2 Safety emails escalated to a person (hard) | ≥ 100.0 | 100.0 ✅ | 100.0 ✅ |
| E3 Category correct on drafted RMAs (%) (soft) | ≥ 95.0 | 100.0 ✅ | 100.0 ✅ |
| E4 Serials extracted exactly where present (%) (soft) | ≥ 98.0 | 100.0 ✅ | 100.0 ✅ |
| E5 Ownership and warranty correct on drafted RMAs (%) (hard) | ≥ 100.0 | 100.0 ✅ | 100.0 ✅ |
| E6 RMA requests drafted without triage (%) (soft) | ≥ 50.0 | 29.3 ❌ | 74.5 ✅ |
| E7 French vs English category accuracy gap (points) (soft) | ≤ 5.0 | 10.8 ❌ | 0.0 ✅ |
| E8 Category accuracy on unseen phrasings (%) (soft) | ≥ 90.0 | 58.3 ❌ | 100.0 ✅ |
| **Release decision** | all gates | **blocked** | **release** |

**v1 was blocked.** The model, trained on 214 historical tickets, had not learned that "RAM", "DOA", "PSU" or "disque" mean memory, dead on arrival, power supply and storage when the wording was new to it, and French suffered most. It was safe (E1, E2 and E5 passed) but not useful.

**v2 added the repair engineers' bilingual failure glossary** (`config/failure_glossary.yaml`) in front of the model, with a rule that disagreement between the two sends the email to a person. Thresholds were re-tuned on validation only. All gates pass.

## Where the v2 test emails went

| Route | Emails |
|---|---|
| RMA drafted for one-click approval | 117 |
| Human review, with the reason | 43 |
| Serial requested from the customer | 20 |
| Safety escalation | 18 |
| Forwarded to sales or billing | 14 |

## Before and after

Error rates for the agent are **measured** on the test set. Cycle times and desk hours are **projected** from the same requests' baseline timings, using the assumptions below; the agent has not run in production.

| Measure | Before (manual) | After (agent) | |
|---|---|---|---|
| Median time, email to RMA number | 10.2 h | 1.0 h | projected |
| 90th percentile | 31.8 h | 19.9 h | projected |
| Safety email seen by a person | median 3.6 h, worst 17.1 h | about 2 min | projected |
| Wrong failure category | 7.6% | 0.0% on drafted RMAs | measured |
| Wrong warranty decision | 3.8% | 0% (deterministic lookup) | measured |
| RMA desk hands-on time for these requests | 65.4 h | 10.6 h | projected |

**Assumptions:** agent minutes = 2; approval hours = 1.0; hands on triage min = 10; hands on entry min = 15; hands on approve min = 1.
Human-review items are assumed to take as long as today. The serial-request reply goes out at once, but the customer's reply time is unchanged.

## Caveats

- **Synthetic data.** The glossary and the generated emails share the same component vocabulary, which flatters E8. On real emails expect lower accuracy on new wording; that is why E8 is monitored monthly and 10% of drafts are re-checked.
- The intent and category models are small (TF-IDF and logistic regression) by design: fast, explainable, cheap. `intake/llm.py` puts Claude behind the same validation if the gates ever require it.
