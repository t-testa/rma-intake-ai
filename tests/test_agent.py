import pandas as pd
import pytest

from intake.agent import ASK, AUTO, FORWARD, REVIEW, SAFETY_ESC, IntakeAgent, load_glossary, split
from intake.llm import validate

BASE = pd.read_csv("data/installed_base.csv")
REQ = pd.read_csv("data/requests.csv", keep_default_na=False)
for c in ("true_is_rma", "true_safety", "serial_in_text", "true_owned"):
    REQ[c] = REQ[c].astype(str).eq("True")
REQ["split"] = split(REQ)


@pytest.fixture(scope="module")
def agent():
    return IntakeAgent(BASE, category_min=0.4, glossary=load_glossary("config/failure_glossary.yaml")).fit(
        REQ[REQ.split == "train"])


def email(body, sender=None, subject="RMA request", received="2026-09-15T10:00"):
    own = BASE.iloc[0]
    return {"request_id": "T1", "subject": subject, "body": body, "received_at": received,
            "from": sender or f"ops@{own['customer_domain']}"}


def test_safety_beats_everything(agent):
    s = BASE.iloc[0]["serial"]
    for body in [f"Invoice question, also we saw smoke from {s}", f"Bonjour, odeur de brûlé, série {s}"]:
        assert agent.decide(email(body)).route == SAFETY_ESC


def test_clean_request_is_drafted(agent):
    row = BASE[pd.to_datetime(BASE.ship_date) > "2025-06-01"].iloc[0]
    d = agent.decide(email(f"Hi, NVMe drive in bay 2 is not detected. Serial: {row['serial']}.",
                           sender=f"it@{row['customer_domain']}"))
    assert d.route == AUTO and d.category == "STORAGE" and d.in_warranty


def test_missing_serial_gets_reply_in_french(agent):
    d = agent.decide(email("Bonjour, la carte mère échoue au POST. Pouvez-vous ouvrir un RMA? Merci, le serveur est en panne."))
    assert d.route == ASK and "numéro de série" in d.reply_draft


def test_someone_elses_serial_goes_to_review(agent):
    a, b = BASE.customer_domain.unique()[:2]
    s = BASE[BASE.customer_domain == a].iloc[0]["serial"]
    d = agent.decide(email(f"Hi, PSU failed. Serial: {s}.", sender=f"ops@{b}"))
    assert d.route == REVIEW and "another customer" in d.reason


def test_unknown_serial_goes_to_review(agent):
    d = agent.decide(email("Hi, the PSU failed. Serial: HT99-000000. Please open an RMA."))
    assert d.route == REVIEW and "not in the installed base" in d.reason


def test_quote_request_is_forwarded(agent):
    d = agent.decide(email("Can you send me an updated quote for 40 more Corvus R4 nodes?", subject="Quote"))
    assert d.route in (FORWARD, REVIEW) and d.route != AUTO


def test_llm_answers_are_validated():
    assert validate('{"is_rma": true, "category": "MEMORY", "confidence": 0.9}') == (True, "MEMORY", 0.9)
    assert validate('{"is_rma": true, "category": "GPU_MELTDOWN", "confidence": 0.9}') is None
    assert validate('{"is_rma": true, "category": "PSU", "confidence": 7}') is None
    assert validate("It's probably the power supply.") is None


def test_split_holds_out_phrasings():
    parts = REQ.phrase_key.str.split("|")
    held = REQ[parts.str[2] == parts.str[3]]
    assert (held.split == "test").all()
