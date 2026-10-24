"""Optional: Claude as the intent and category classifier, behind the same gates.

The model returns JSON. The answer is validated before use: the category must be
one of the allowed values and the confidence a number between 0 and 1, otherwise
the email goes to human review. Safety detection, serial extraction, ownership
and warranty stay deterministic whichever classifier is used.

    agent = IntakeAgent(base, glossary=glossary)
    agent.classifier = ClaudeClassifier()      # needs ANTHROPIC_API_KEY
"""
import json
import os

CATEGORIES = ["PSU", "MEMORY", "STORAGE", "MOTHERBOARD", "COOLING", "NETWORK", "DOA"]

PROMPT = """You triage support emails for a server manufacturer's RMA desk. Emails may be in English or French.
Decide whether the email asks for a warranty return (RMA), and if so which failure category fits best.
Allowed categories: {cats}. If you cannot tell, use "UNKNOWN" and a low confidence.
Return only JSON: {{"is_rma": true or false, "category": "...", "confidence": 0.0 to 1.0}}

Email subject: {subject}
Email body: {body}"""


def validate(raw: str):
    """Return (is_rma, category, confidence) or None if the answer can't be trusted."""
    try:
        d = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
        conf = float(d["confidence"])
        if not isinstance(d["is_rma"], bool) or not 0 <= conf <= 1:
            return None
        if d["is_rma"] and d["category"] not in CATEGORIES:
            return None
        return d["is_rma"], d.get("category", ""), conf
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


class ClaudeClassifier:
    def __init__(self, call=None, model="claude-sonnet-4-5"):
        if call is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("set ANTHROPIC_API_KEY or pass call=")
            import anthropic
            client = anthropic.Anthropic()
            call = lambda p: client.messages.create(model=model, max_tokens=120, temperature=0,  # noqa: E731
                                                    messages=[{"role": "user", "content": p}]).content[0].text
        self.call = call

    def classify(self, subject: str, body: str):
        return validate(self.call(PROMPT.format(cats=", ".join(CATEGORIES), subject=subject, body=body)))
