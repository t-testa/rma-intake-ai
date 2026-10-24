"""The RMA intake agent: read an email, decide what it is, and route it.

Each step is chosen for the job it does:
- Safety language        -> keyword rules in English and French. Never left to a model.
- Is this an RMA?        -> classifier, with a confidence threshold.
- Which failure?         -> classifier, with a confidence threshold.
- Serials                -> pattern extraction, then checked against the installed base.
- Owner and warranty     -> deterministic lookup in the installed base. Never a model.
- Route                  -> business rules from docs/02_requirements.md.

The classifiers are scikit-learn (TF-IDF + logistic regression) trained on
historical tickets. intake/llm.py offers Claude as a drop-in replacement for
the two classification steps; the same evaluation gates apply to either.
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

import unicodedata

import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, make_pipeline

SERIAL = re.compile(r"\bHT\d{2}-\d{6}\b", re.I)
SAFETY = re.compile(r"\b(smoke|smoking|burn\w*|spark\w*|fire|melt\w*|fumée|brûl\w*|étincelle\w*|feu|odeur de)\b", re.I)
FRENCH = re.compile(r"\b(bonjour|merci|le|la|les|une|est|pas|pouvez|svp|numéro|série|panne)\b", re.I)

AUTO, ASK, REVIEW, SAFETY_ESC, FORWARD = "DRAFT_RMA", "ASK_CUSTOMER", "HUMAN_REVIEW", "SAFETY_ESCALATION", "FORWARD_NON_RMA"

ASK_TEMPLATE = {
    "en": "Hello,\n\nThanks for contacting us. To open your RMA we need the serial number of the affected server "
          "(format HTxx-xxxxxx, on the label at the back of the chassis or in the BMC). Reply to this email with it and "
          "we will issue your RMA number right away.\n\nThe RMA team",
    "fr": "Bonjour,\n\nMerci de nous avoir écrit. Pour ouvrir votre RMA, il nous faut le numéro de série du serveur "
          "touché (format HTxx-xxxxxx, sur l'étiquette à l'arrière du châssis ou dans le BMC). Répondez à ce courriel "
          "avec ce numéro et nous émettrons votre numéro de RMA immédiatement.\n\nL'équipe RMA",
}


def text_model():
    features = FeatureUnion([("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
                             ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True))])
    return make_pipeline(features, LogisticRegression(max_iter=2000, C=4.0))


def text_of(r) -> str:
    return f"{r['subject']} . {SERIAL.sub(' ', r['body'])}"


@dataclass
class Decision:
    request_id: str
    detected_language: str
    route: str
    reason: str
    is_rma_prob: float
    category: str = ""
    category_prob: float = 0.0
    serials: list = field(default_factory=list)
    models: list = field(default_factory=list)
    in_warranty: bool | None = None
    reply_draft: str = ""


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def load_glossary(path) -> dict:
    g = yaml.safe_load(open(path))
    return {cat: [re.compile(rf"(?<![a-z0-9]){re.escape(fold(t))}(?![a-z0-9])") for t in terms] for cat, terms in g.items()}


class IntakeAgent:
    def __init__(self, installed_base: pd.DataFrame, intent_min=0.80, category_min=0.70, glossary=None):
        self.base = installed_base.set_index("serial")
        self.glossary = glossary
        self.intent_min, self.category_min = intent_min, category_min
        self.intent, self.category = text_model(), text_model()

    def fit(self, train: pd.DataFrame):
        texts = train.apply(text_of, axis=1)
        self.intent.fit(texts, train["true_is_rma"].astype(int))
        rma = train[train["true_is_rma"] & ~train["true_safety"]]
        self.category.fit(rma.apply(text_of, axis=1), rma["true_category"])
        return self

    def _warranty(self, serial: str, received: str) -> bool:
        row = self.base.loc[serial]
        ship = date.fromisoformat(row["ship_date"])
        end = date(ship.year + (ship.month - 1 + row["warranty_months"]) // 12,
                   (ship.month - 1 + row["warranty_months"]) % 12 + 1, min(ship.day, 28))
        return datetime.fromisoformat(received).date() <= end

    def decide(self, r) -> Decision:
        text = f"{r['subject']} {r['body']}"
        lang = "fr" if len(FRENCH.findall(text)) >= 3 else "en"
        p_rma = float(self.intent.predict_proba([text_of(r)])[0][1])
        d = Decision(r["request_id"], lang, "", "", round(p_rma, 3))

        if SAFETY.search(text):
            d.route, d.reason = SAFETY_ESC, "safety language detected: page engineering now"
            return d
        if p_rma < 1 - self.intent_min:
            d.route, d.reason = FORWARD, "not an RMA request: forward to sales or billing"
            return d
        if p_rma < self.intent_min:
            d.route, d.reason = REVIEW, "unsure whether this is an RMA request"
            return d

        d.category, d.category_prob = self._categorize(r)
        d.serials = sorted({s.upper() for s in SERIAL.findall(r["body"])})

        if not d.serials:
            d.route, d.reason, d.reply_draft = ASK, "no serial number in the email", ASK_TEMPLATE[lang]
            return d
        unknown = [s for s in d.serials if s not in self.base.index]
        if unknown:
            d.route, d.reason = REVIEW, f"serial not in the installed base: {', '.join(unknown)}"
            return d
        domain = r["from"].split("@")[-1]
        foreign = [s for s in d.serials if self.base.loc[s, "customer_domain"] != domain]
        if foreign:
            d.route, d.reason = REVIEW, f"serial registered to another customer: {', '.join(foreign)}"
            return d
        d.models = [self.base.loc[s, "model"] for s in d.serials]
        d.in_warranty = all(self._warranty(s, r["received_at"]) for s in d.serials)
        if not d.in_warranty:
            d.route, d.reason = REVIEW, "out of warranty: prepare a repair quote"
            return d
        if d.category_prob < self.category_min:
            d.route, d.reason = REVIEW, f"failure category uncertain ({d.category_prob:.2f})"
            return d
        d.route, d.reason = AUTO, "in warranty, owner verified, category confident: RMA drafted for one-click approval"
        return d

    def _categorize(self, r):
        probs = self.category.predict_proba([text_of(r)])[0]
        best = probs.argmax()
        ml = (str(self.category.classes_[best]), round(float(probs[best]), 3))
        if not self.glossary:
            return ml
        body = fold(SERIAL.sub(" ", r["body"]))
        hits = [c for c, pats in self.glossary.items() if any(p.search(body) for p in pats)]
        if len(hits) == 1:
            return hits[0], 0.95
        if len(hits) > 1 and ml[0] in hits:
            return ml
        if len(hits) > 1:
            return ml[0], min(ml[1], 0.5)       # glossary and model disagree: let a person decide
        return ml

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame([asdict(self.decide(r)) for r in df.to_dict("records")])


def split(requests: pd.DataFrame, seed: int = 7) -> pd.Series:
    """test = held-out phrasings + 20% of the rest; val = 20% of the remainder; train = the rest."""
    parts = requests["phrase_key"].str.split("|")
    held_out = parts.str[2] == parts.str[3]
    rest = requests[~held_out]
    test_extra = rest.sample(frac=0.20, random_state=seed).index
    remaining = rest.drop(test_extra)
    val = remaining.sample(frac=0.20, random_state=seed).index
    s = pd.Series("train", index=requests.index)
    s[held_out] = "test"
    s[test_extra] = "test"
    s[val] = "val"
    return s
