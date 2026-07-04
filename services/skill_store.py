"""
services/skill_store.py -- built-in skill packs users can install.

Each pack is a set of expert instructions saved into user_skills; the /stream
pipeline already injects relevant skills into the system prompt, so installed
packs immediately shape answers.
"""
import uuid

PACKS = {
    "excel_expert": {
        "name": "Excel Expert",
        "description": "Advanced Excel: formulas, pivot tables, Power Query, VBA",
        "skills": [
            ("Excel formulas", "When asked about Excel, give the exact formula with cell references, explain each argument briefly, and mention keyboard shortcuts. Prefer XLOOKUP/FILTER/LET over legacy functions; note version requirements."),
            ("Pivot tables", "For data summarization questions, walk through pivot table setup step by step: select data, Insert > PivotTable, drag fields to Rows/Values/Filters, then suggest slicers and conditional formatting."),
        ],
    },
    "electrical_is": {
        "name": "Electrical Standards (IS/IEC)",
        "description": "Indian & IEC electrical standards expertise",
        "skills": [
            ("IS standards", "Always answer electrical engineering questions using IS (Indian Standards) and IEC standards. Cite the specific standard number (e.g. IS 732 for wiring, IS 3043 for earthing, IEC 60909 for fault calculations) and clause where possible."),
            ("Cable sizing", "For cable sizing: state design current, apply derating factors (ambient, grouping, depth), check voltage drop limit (IS 1255: 3 percent lighting, 5 percent power), verify short-circuit withstand, and present the calculation table."),
        ],
    },
    "solar_design": {
        "name": "Solar & BESS Design",
        "description": "Solar PV plant and battery storage design",
        "skills": [
            ("Solar PV design", "For solar questions: size the array from kWh/day and peak sun hours, apply performance ratio 0.75-0.8, pick inverter DC/AC ratio 1.1-1.3, and check MNRE/CEA norms for India-specific queries."),
            ("BESS sizing", "For battery storage: compute usable energy from depth-of-discharge and round-trip efficiency, size for autonomy hours, compare LFP vs NMC, include degradation (2-3 percent/yr) and cite CEA grid connectivity regulations."),
        ],
    },
    "stock_market": {
        "name": "Stock Market Analyst",
        "description": "Fundamental + technical analysis frameworks",
        "skills": [
            ("Stock analysis", "For stock questions: cover fundamentals (P/E, ROE, debt/equity, growth), technicals (trend, support/resistance, volume), and always add that this is information, not financial advice."),
        ],
    },
    "robotics": {
        "name": "Robotics Engineer",
        "description": "Kinematics, control systems, ROS",
        "skills": [
            ("Robotics", "For robotics questions: be precise about kinematics (DH parameters, IK vs FK), control loops (PID tuning steps), and prefer ROS2 examples with actual node/topic code."),
        ],
    },
}


def list_packs(installed_names: set) -> list:
    return [{"id": pid, "name": p["name"], "description": p["description"],
             "skills": len(p["skills"]),
             "installed": p["name"] in installed_names}
            for pid, p in PACKS.items()]


def install(pack_id: str, username: str, db) -> dict:
    pack = PACKS.get(pack_id)
    if not pack:
        return {"error": "unknown pack"}
    n = 0
    for name, content in pack["skills"]:
        try:
            db.save_skill(username, uuid.uuid4().hex[:12],
                          "%s: %s" % (pack["name"], name),
                          pack["description"], content, [pack_id])
            n += 1
        except Exception:
            pass
    return {"ok": True, "installed": n, "pack": pack["name"]}
