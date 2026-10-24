# RMA Intake: from process discovery to a gated AI agent

**A business-systems-analysis case study, end to end: map the current process, find where AI and automation help, design the future state with people in the loop, write the requirements, agree on evaluation thresholds *before* building, build the agent, and let the gates decide whether it ships.**

The process: a server manufacturer's RMA (warranty return) desk, where customers email in English and French when a server fails. Today an analyst reads every email, chases missing serial numbers, checks warranty in a spreadsheet, re-keys the RMA into the ERP, and sometimes misses a "we smelled burning" email for hours.

*Fictional company, synthetic data: 480 support emails, 356 servers in the installed base, and a baseline log of how the manual desk handled each request.*

## The deliverables, in the order a BSA produces them

| | Document | What's in it |
|---|---|---|
| 1 | [Process discovery](docs/01_discovery.md) | current-state BPMN, steps and hands-on time, baseline metrics, pain points, data sources, opportunities scored by effort, benefit and data sensitivity |
| 2 | [Future state and requirements](docs/02_requirements.md) | future-state BPMN showing where people review, approve or handle exceptions; user stories with Gherkin acceptance criteria; business rules; integrations, access and data sensitivity |
| 3 | [Evaluation plan](docs/03_evaluation_plan.md) | eight release gates with thresholds and the reason for each, **committed before the agent was built** (see the first commit) |
| 4 | [Results](docs/04_results.md) | the iteration log against the gates, where requests went, before and after against the baseline |

BPMN 2.0 sources for both processes are in [`bpmn/`](bpmn/). They open in Camunda Modeler or bpmn.io, and the diagrams below are generated from the same model.

![Current state](docs/current_state.svg)
![Future state](docs/future_state.svg)

## What happened

**v1 was blocked by its own gates.** A classifier trained on 214 historical tickets was safe (no false RMAs, every safety email escalated, every warranty decision right) but only 58% accurate on wording it hadn't seen. It drafted just 29% of requests and was 11 points worse in French. Under the plan, that doesn't ship.

**v2 added what the repair engineers already know:** a bilingual failure glossary in front of the model, plus a rule that disagreement between the two goes to a person. It passes all eight gates on the held-out test set:

| Gate | Target | v2 |
|---|---|---|
| Non-RMA emails drafted as an RMA | 0 | **0** |
| Safety emails escalated to a person | 100% | **100%** |
| Category correct on drafted RMAs | ≥ 95% | 100% |
| Serials extracted exactly | ≥ 98% | 100% |
| Ownership and warranty correct | 100% | 100% |
| RMA requests drafted without triage | ≥ 50% | **74.5%** |
| French vs English accuracy gap | ≤ 5 pts | 0 pts |
| Accuracy on unseen phrasings | ≥ 90% | 100% (flattered by synthetic data, see caveats) |

**Before and after** on the same 157 test RMA requests: median time to an RMA number goes from **10.2 h to about 1 h** (projected), safety emails reach a person in **minutes instead of up to 17 h**, wrong warranty decisions go from **3.8% to 0**, and desk hands-on time drops from **65 h to about 11 h**. Every RMA is still approved by a person. Error rates are measured; times are projections with the assumptions written out in [the results](docs/04_results.md).

## Design decisions a reviewer should push on

- **Safety is a rule, not a model.** An explicit English and French term list runs before anything else. A probability is the wrong tool when the cost of a miss is a fire.
- **Warranty and ownership are lookups, not predictions.** That is what removes today's 4.7% warranty errors. AI only does what needs judgment: reading free text.
- **Every exception names its reason.** "Serial registered to another customer" or "out of warranty: prepare a repair quote" tells the analyst what to do next.
- **Thresholds are tuned on validation, scored on test.** The test set includes whole phrasings held out of training, so it measures new wording, not memory.
- **The missing-serial reply goes out in the customer's language** the moment the email arrives, instead of after triage.
- **The classifier is swappable.** `intake/llm.py` puts Claude behind the same JSON validation and the same gates. The small TF-IDF model is the default because it is fast, cheap and explainable, and it passes.

## Run it

```bash
pip install -r requirements.txt
python generate_data.py        # installed base, 480 emails, baseline log
python run.py                  # trains, tunes on validation, scores v1 and v2 against the gates
python report.py               # docs/04_results.md
python bpmn/build_bpmn.py      # BPMN 2.0 files and diagrams
pytest -q                      # 10 tests
```

## Layout

| Path | What it is |
|---|---|
| `docs/` | the four deliverables and the BPMN diagrams |
| `bpmn/` | BPMN 2.0 XML for current and future state, and the script that draws them |
| `config/failure_glossary.yaml` | repair engineering's bilingual failure vocabulary |
| `intake/agent.py` | the agent: safety rule, intent and category, serial extraction, ERP checks, routing |
| `intake/evaluate.py` | the eight gates from the evaluation plan |
| `intake/impact.py` | before and after against the baseline log |
| `intake/llm.py` | optional Claude classifier with strict output validation |

## Caveats

- **Synthetic data, synthetic company.** The emails are generated from templates; real ones are messier. The glossary and the templates share vocabulary, so 100% on unseen phrasings is optimistic. The plan answers this with monthly monitoring of the same gates and a 10% re-check of drafted RMAs.
- **Cycle times and desk hours are projections**, not measurements; the agent has not run against a live inbox or ERP.
- **The Claude path is implemented and its validation tested with stubbed answers,** but it has not been scored against the gates in this repo.

All data is synthetic. The company, customers, serial numbers and emails are fictional.
