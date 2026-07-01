"""
tools/flight_finder.py — Flight search: natural-language date parsing + Gemini JSON extraction.
Ported from Mark-XLVII flight_finder.py. Uses requests (no browser automation).
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

NAME        = "flight_finder"
DESCRIPTION = (
    "Search for flights between two cities. Parses natural-language dates "
    "(tomorrow, next Friday, 15 July). Returns top 5 options with price, airline, times."
)
CATEGORY = "internet"
ICON     = "✈️"
INPUTS = [
    {"name": "origin",      "label": "Origin city / airport",      "type": "text", "placeholder": "London, LHR", "required": True},
    {"name": "destination", "label": "Destination city / airport", "type": "text", "placeholder": "Dubai, DXB",  "required": True},
    {"name": "date",        "label": "Departure date",             "type": "text", "placeholder": "tomorrow / 15 July / 2025-07-15", "required": True},
    {"name": "return_date", "label": "Return date (optional)",     "type": "text", "placeholder": "leave blank for one-way"},
    {"name": "passengers",  "label": "Passengers",                 "type": "number", "placeholder": "1"},
    {"name": "cabin",       "label": "Cabin class", "type": "select",
     "options": [
         {"value": "economy",  "label": "Economy"},
         {"value": "premium",  "label": "Premium Economy"},
         {"value": "business", "label": "Business"},
         {"value": "first",    "label": "First Class"},
     ], "required": False, "default": "economy"},
]

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3,    "april": 4,
    "may": 5,     "june": 6,     "july": 7,      "august": 8,
    "september": 9,"october": 10,"november": 11, "december": 12,
}
_CABIN_CODE = {"economy": "1", "premium": "2", "business": "3", "first": "4"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _gemini_key() -> str:
    k = os.getenv("GEMINI_API_KEY", "")
    if not k:
        raise EnvironmentError("GEMINI_API_KEY not set")
    return k


def _parse_date(raw: str) -> str:
    raw   = raw.strip()
    lower = raw.lower()
    today = datetime.now()

    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    relative = {
        "today":    today,
        "tomorrow": today + timedelta(days=1),
    }
    for key, val in relative.items():
        if key in lower:
            return val.strftime("%Y-%m-%d")

    # Try Gemini for complex expressions
    try:
        from google import genai
        client   = genai.Client(api_key=_gemini_key())
        response = client.models.generate_content(
            model   = "gemini-2.5-flash-lite",
            contents= (
                f"Today is {today.strftime('%Y-%m-%d')}. "
                f"Convert this date to YYYY-MM-DD: '{raw}'. "
                "Return ONLY the date string, nothing else."
            ),
        )
        result = response.text.strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", result):
            return result
    except Exception as e:
        log.debug("Gemini date parse failed: %s", e)

    # Manual month-name parsing
    for month_name, month_num in _MONTH_MAP.items():
        if month_name in lower:
            dm = re.search(r"\d{1,2}", raw)
            if dm:
                day  = int(dm.group())
                year = today.year if month_num >= today.month else today.year + 1
                return f"{year}-{month_num:02d}-{day:02d}"

    return today.strftime("%Y-%m-%d")


def _build_google_flights_url(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str  = None,
    passengers:  int  = 1,
    cabin:       str  = "economy",
) -> str:
    cabin_code = _CABIN_CODE.get(cabin.lower(), "1")
    base       = "https://www.google.com/travel/flights"
    if return_date:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}+returning+{return_date}"
    else:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}"
    return (
        f"{base}?q={trip}"
        f"&curr=USD&cabin={cabin_code}&adults={passengers}"
    )


def _scrape_flights_page(url: str) -> str:
    """Fetch Google Flights page HTML as text."""
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.text
    except ImportError:
        return ""
    except Exception as e:
        log.warning("Flights page fetch failed: %s", e)
        return ""


def _parse_with_gemini(raw_text: str, origin: str, destination: str, date: str) -> list:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_gemini_key())
        prompt = (
            f"Extract flight options from {origin} to {destination} on {date} "
            f"from this Google Flights page text:\n\n{raw_text[:12000]}\n\n"
            "Return a JSON array of up to 5 flights:\n"
            '[{"airline":"...","departure":"HH:MM","arrival":"HH:MM",'
            '"duration":"Xh Ym","stops":0,"price":"...","currency":"USD"}]\n'
            "If no flights found return: []"
        )
        response = client.models.generate_content(
            model   = "gemini-2.5-flash",
            contents= prompt,
            config  = types.GenerateContentConfig(
                system_instruction=(
                    "You are a flight data extraction expert. "
                    "Extract from raw HTML/text. Return ONLY valid JSON — no markdown."
                )
            ),
        )
        text    = re.sub(r"```(?:json)?", "", response.text).strip().rstrip("`").strip()
        flights = json.loads(text)
        return flights if isinstance(flights, list) else []
    except Exception as e:
        log.warning("Gemini flights parse failed: %s", e)
        return []


def _format_results(flights: list, origin: str, destination: str, date: str, flights_url: str) -> str:
    if not flights:
        return (
            f"No flights found for {origin} → {destination} on {date}.\n"
            f"Try searching directly: {flights_url}"
        )
    lines = [f"✈️ Flights from **{origin}** to **{destination}** on {date}:\n"]
    for i, f in enumerate(flights[:5], 1):
        stops    = f.get("stops", 0)
        stop_str = "non-stop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
        price    = f"{f.get('price', 'N/A')} {f.get('currency', '')}".strip()
        dur      = f", {f['duration']}" if f.get("duration") else ""
        lines.append(
            f"{i}. **{f.get('airline','?')}** — "
            f"{f.get('departure','?')} → {f.get('arrival','?')}{dur} "
            f"({stop_str}) — {price}"
        )
    priced = [f for f in flights if f.get("price")]
    if priced:
        cheapest = min(priced, key=lambda x: int(re.sub(r"[^\d]", "", str(x.get("price",0))) or "999999"))
        lines.append(f"\n💰 Cheapest: **{cheapest.get('airline')}** at {cheapest.get('price')} {cheapest.get('currency','')}")
    lines.append(f"\n🔗 Book: {flights_url}")
    return "\n".join(lines)


def run(
    origin:      str = "",
    destination: str = "",
    date:        str = "",
    return_date: str = "",
    passengers:  int = 1,
    cabin:       str = "economy",
    username:    str = "",
) -> dict:
    origin      = (origin      or "").strip()
    destination = (destination or "").strip()
    date        = (date        or "").strip()

    if not origin or not destination:
        return {"error": "Please provide both origin and destination."}
    if not date:
        return {"error": "Please provide a departure date."}

    cabin = (cabin or "economy").lower()
    if cabin not in _CABIN_CODE:
        cabin = "economy"
    try:
        passengers = max(1, int(str(passengers).strip() or 1))
    except (ValueError, TypeError):
        passengers = 1

    departure_date = _parse_date(date)
    return_parsed  = _parse_date(return_date) if return_date.strip() else None

    log.info("flight_finder: %s → %s on %s", origin, destination, departure_date)

    flights_url = _build_google_flights_url(
        origin, destination, departure_date, return_parsed, passengers, cabin
    )

    raw_html = _scrape_flights_page(flights_url)
    flights  = _parse_with_gemini(raw_html, origin, destination, departure_date) if raw_html else []

    result = _format_results(flights, origin, destination, departure_date, flights_url)
    return {
        "result":       result,
        "flights":      flights,
        "flights_url":  flights_url,
        "date_parsed":  departure_date,
    }
