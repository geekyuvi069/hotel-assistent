from .kb import KB

# Used when the LLM is unavailable. ponytail: substring match; upgrade to embeddings if the KB grows.
KEYWORDS = {
    "checkin": ["check-in", "check in", "checkin", "check-out", "check out", "checkout"],
    "pool": ["pool", "swim"],
    "breakfast": ["breakfast"],
    "cancellation": ["cancel", "refund"],
    "wifi": ["wifi", "wi-fi", "internet"],
    "parking": ["parking"],
    "pets": ["pet", "dog"],
    "gym": ["gym", "fitness"],
    "airport": ["airport", "shuttle"],
    "contact": ["contact", "phone", "email"],
}
AVAILABILITY = ["available", "availability", "vacan", "book", "rooms free"]
FACTS = {f["id"]: f["text"] for f in KB["facts"]}


def answer(text: str) -> dict:
    t = text.lower()
    if any(k in t for k in AVAILABILITY):
        return {"type": "needs_availability_input", "sources": [],
                "reply": "Happy to check. Please tell me your check-in date, check-out date and number of guests."}
    hits = [i for i, words in KEYWORDS.items() if any(w in t for w in words)]
    if hits:
        return {"type": "answer", "sources": hits, "reply": " ".join(FACTS[i] for i in hits)}
    return {"type": "fallback", "sources": [],
            "reply": f"I'm not able to answer that reliably. Please contact our front desk: {FACTS['contact']}"}
