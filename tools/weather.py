"""Weather tool — current conditions via wttr.in (no API key required)."""
import urllib.parse, urllib.request, json

NAME        = "weather"
DESCRIPTION = "Get current weather and 3-day forecast for any city"
CATEGORY    = "builtin"
ICON        = "🌤️"
INPUTS = [
    {"name": "location", "label": "City / Location", "type": "text",
     "placeholder": "e.g. London, New York, Chennai", "required": True},
    {"name": "units", "label": "Units", "type": "select",
     "options": [{"value": "metric", "label": "°C (metric)"},
                 {"value": "imperial", "label": "°F (imperial)"}],
     "required": False, "default": "metric"},
]

_CONDITIONS = {
    "113": "Sunny", "116": "Partly cloudy", "119": "Cloudy",
    "122": "Overcast", "143": "Mist", "176": "Patchy rain",
    "179": "Patchy snow", "182": "Sleet", "185": "Freezing drizzle",
    "200": "Thundery outbreaks", "227": "Blowing snow", "230": "Blizzard",
    "248": "Fog", "260": "Freezing fog", "263": "Light drizzle",
    "266": "Light rain", "281": "Freezing drizzle", "284": "Heavy freezing drizzle",
    "293": "Light rain", "296": "Light rain", "299": "Moderate rain",
    "302": "Moderate rain", "305": "Heavy rain", "308": "Very heavy rain",
    "311": "Light freezing rain", "314": "Moderate freezing rain",
    "317": "Light sleet", "320": "Moderate sleet", "323": "Light snow",
    "326": "Light snow", "329": "Moderate snow", "332": "Moderate snow",
    "335": "Heavy snow", "338": "Heavy snow", "350": "Blizzard",
    "353": "Light rain", "356": "Moderate rain", "359": "Heavy rain",
    "362": "Light sleet", "365": "Moderate sleet", "368": "Light snow showers",
    "371": "Heavy snow showers", "374": "Light sleet", "377": "Moderate sleet",
    "386": "Thundery rain", "389": "Heavy thundery rain",
    "392": "Thundery snow", "395": "Heavy thundery snow",
}

_WIND_DIR = {
    "N":"↑","NNE":"↗","NE":"↗","ENE":"↗","E":"→","ESE":"↘","SE":"↘",
    "SSE":"↘","S":"↓","SSW":"↙","SW":"↙","WSW":"↙","W":"←","WNW":"↖",
    "NW":"↖","NNW":"↖",
}

def run(location: str, units: str = "metric") -> dict:
    loc_enc = urllib.parse.quote(location)
    url = f"https://wttr.in/{loc_enc}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "AssistNeo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return {"error": f"Could not fetch weather: {e}"}

    cur = data["current_condition"][0]
    temp = cur["temp_C"] if units == "metric" else cur["temp_F"]
    feels = cur["FeelsLikeC"] if units == "metric" else cur["FeelsLikeF"]
    unit_sym = "°C" if units == "metric" else "°F"
    wind_spd = cur["windspeedKmph"] if units == "metric" else cur["windspeedMiles"]
    wind_unit = "km/h" if units == "metric" else "mph"
    wind_arrow = _WIND_DIR.get(cur.get("winddir16Point", ""), "")
    cond_code = cur["weatherCode"]
    condition = _CONDITIONS.get(cond_code, cur["weatherDesc"][0]["value"])

    # 3-day forecast
    forecast = []
    for day in data.get("weather", [])[:3]:
        max_t = day["maxtempC"] if units == "metric" else day["maxtempF"]
        min_t = day["mintempC"] if units == "metric" else day["mintempF"]
        desc  = day["hourly"][4]["weatherDesc"][0]["value"] if day.get("hourly") else ""
        forecast.append({
            "date": day["date"],
            "max": f"{max_t}{unit_sym}",
            "min": f"{min_t}{unit_sym}",
            "description": desc,
            "sunrise": day.get("astronomy", [{}])[0].get("sunrise", ""),
            "sunset":  day.get("astronomy", [{}])[0].get("sunset", ""),
        })

    area = data.get("nearest_area", [{}])[0]
    city = area.get("areaName", [{}])[0].get("value", location)
    country = area.get("country", [{}])[0].get("value", "")

    return {
        "location": f"{city}, {country}".strip(", "),
        "temperature": f"{temp}{unit_sym}",
        "feels_like": f"{feels}{unit_sym}",
        "condition": condition,
        "humidity": f"{cur['humidity']}%",
        "wind": f"{wind_arrow} {wind_spd} {wind_unit} {cur.get('winddir16Point','')}",
        "visibility": f"{cur['visibility']} km",
        "uv_index": cur.get("uvIndex", "N/A"),
        "forecast": forecast,
    }
