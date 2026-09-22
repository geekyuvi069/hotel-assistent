from datetime import date

from .kb import KB

# Mock inventory: rooms sold out for these [start, end) ranges.
# ponytail: hard-coded; swap for a real PMS call with the same signature.
SOLD_OUT = {
    "deluxe": [(date(2026, 12, 24), date(2026, 12, 28))],
    "family": [(date(2026, 12, 20), date(2027, 1, 3))],
}


def check_availability(check_in: date, check_out: date, adults: int) -> dict:
    if check_out <= check_in:
        raise ValueError("check_out must be after check_in")
    if adults < 1:
        raise ValueError("adults must be at least 1")
    nights = (check_out - check_in).days
    rooms = []
    for r in KB["rooms"]:
        blocked = any(check_in < end and check_out > start for start, end in SOLD_OUT.get(r["id"], []))
        if r["capacity"] >= adults and not blocked:
            rooms.append({"id": r["id"], "name": r["name"], "capacity": r["capacity"],
                          "price_per_night": r["price"], "total": r["price"] * nights})
    return {"check_in": check_in, "check_out": check_out, "adults": adults,
            "nights": nights, "rooms": rooms}
