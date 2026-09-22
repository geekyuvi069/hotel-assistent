import json
from pathlib import Path

KB = json.loads((Path(__file__).parent / "hotel.json").read_text())
ROOMS = {r["id"]: r for r in KB["rooms"]}
VALID_IDS = {f["id"] for f in KB["facts"]} | set(ROOMS)


def system_prompt() -> str:
    facts = "\n".join(f"[{f['id']}] {f['text']}" for f in KB["facts"])
    rooms = "\n".join(
        f"[{r['id']}] {r['name']}: sleeps {r['capacity']}, {r['price']} USD/night. {r['description']}"
        for r in KB["rooms"]
    )
    return (
        f"You are the guest assistant for {KB['name']}. Answer ONLY from the facts below.\n"
        "Rules:\n"
        "- If the answer is not in the facts, say you don't know and point to the front desk. Never guess.\n"
        "- Never state availability or prices for dates yourself; call check_availability.\n"
        "- For ANY availability or booking request you MUST call check_availability, never ask for the details "
        "in text. Pass whatever the guest has given and leave out the rest; the app collects missing fields.\n"
        "- You cannot make bookings. If asked to book, say so and refer to the front desk; never promise "
        "speed, confirmation or anything not in the facts.\n"
        "- Be brief and friendly.\n"
        "- End with a final line 'SOURCES: id1,id2' listing the fact/room ids you used, "
        "or 'SOURCES: none'.\n\n"
        f"FACTS:\n{facts}\n\nROOMS:\n{rooms}"
    )


def split_sources(text: str) -> tuple[str, list[str]]:
    """Strip the trailing SOURCES line; return (reply, cited ids)."""
    body, sep, tail = text.rpartition("SOURCES:")
    if not sep:
        return text.strip(), []
    ids = [i.strip() for i in tail.split(",") if i.strip() and i.strip() != "none"]
    return body.strip(), ids
