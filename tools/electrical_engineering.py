"""
tools/electrical_engineering.py — Electrical Engineering Assistant.
Domain-specific calculations for the power industry.
Calculations: cable sizing, transformer, fault level, solar PV, BESS sizing,
tariff, standards lookup, report generation.
"""
import json, logging, math, os

log = logging.getLogger(__name__)

NAME        = "electrical_engineering"
DESCRIPTION = (
    "Electrical engineering calculations: cable_sizing, transformer, fault_level, "
    "solar_design, bess_sizing, tariff, standards, report. "
    "Designed for power systems / industrial electrical engineers."
)
CATEGORY = "engineering"
ICON     = "⚡"
INPUTS = [
    {"name": "action", "label": "Calculation", "type": "select", "required": True,
     "options": ["cable_sizing","transformer","fault_level","solar_design",
                 "bess_sizing","tariff","standards","report","power_factor"]},
    {"name": "load_kw",      "label": "Load (kW)",          "type": "number"},
    {"name": "voltage_v",    "label": "Voltage (V)",         "type": "number"},
    {"name": "power_factor", "label": "Power factor",        "type": "number", "default": "0.85"},
    {"name": "distance_m",   "label": "Cable run (m)",       "type": "number"},
    {"name": "install_method","label": "Install method",     "type": "select",
     "options": ["underground","trunking","conduit","open_air","direct_buried"], "default": "underground"},
    {"name": "phases",       "label": "Phases",              "type": "select",
     "options": ["3","1"], "default": "3"},
    {"name": "demand_kwh",   "label": "Daily demand (kWh)",  "type": "number"},
    {"name": "peak_power_kw","label": "Peak power (kW)",     "type": "number"},
    {"name": "solar_irr",    "label": "Irradiance (kWh/m²/day)", "type": "number", "default": "5.5"},
    {"name": "tariff_rate",  "label": "Tariff (₹/kWh or $/kWh)", "type": "number"},
    {"name": "query",        "label": "Standards query",     "type": "text"},
    {"name": "username",     "label": "Username",            "type": "text"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt(value, unit="", decimals=2) -> str:
    return f"{round(value, decimals)} {unit}".strip()


# ── Cable Sizing (IEC 60364 / IS 732 approach) ────────────────────────────────
_CABLE_TABLE = {
    # (cross_section_mm2): (current_A_air, current_A_ground)
    1.5:   (16,  13),
    2.5:   (21,  17),
    4:     (28,  23),
    6:     (36,  29),
    10:    (50,  40),
    16:    (66,  53),
    25:    (84,  68),
    35:    (103, 84),
    50:    (125, 101),
    70:    (160, 129),
    95:    (193, 156),
    120:   (224, 181),
    150:   (259, 209),
    185:   (295, 238),
    240:   (346, 279),
    300:   (394, 319),
    400:   (459, 372),
    500:   (531, 430),
    630:   (613, 497),
    800:   (702, 570),
    1000:  (802, 651),
}
RESISTIVITY_COPPER = 0.0172   # Ω·mm²/m at 20°C
RESISTIVITY_ALUM   = 0.0282   # Ω·mm²/m at 20°C

def cable_sizing(load_kw: float, voltage_v: float, power_factor: float,
                 distance_m: float, phases: int, install_method: str,
                 conductor: str = "copper") -> dict:
    if phases == 3:
        current_a = load_kw * 1000 / (math.sqrt(3) * voltage_v * power_factor)
    else:
        current_a = load_kw * 1000 / (voltage_v * power_factor)

    # Derate for underground
    derate = 0.8 if install_method in ("underground","direct_buried") else 1.0

    # Find minimum cable size
    selected_size = None
    for size, (cap_air, cap_gnd) in sorted(_CABLE_TABLE.items()):
        cap = (cap_gnd if install_method in ("underground","direct_buried") else cap_air) * derate
        if cap >= current_a:
            selected_size = size
            break

    if not selected_size:
        selected_size = 1000  # flag — oversized

    # Voltage drop check
    rho = RESISTIVITY_COPPER if conductor == "copper" else RESISTIVITY_ALUM
    r_per_m = rho / selected_size
    if phases == 3:
        vdrop_v  = math.sqrt(3) * current_a * r_per_m * distance_m
    else:
        vdrop_v  = 2 * current_a * r_per_m * distance_m
    vdrop_pct = vdrop_v / voltage_v * 100

    # If voltage drop > 5% (IS 732 limit), go up one size
    if vdrop_pct > 5:
        sizes = sorted(_CABLE_TABLE.keys())
        idx   = sizes.index(selected_size)
        if idx + 1 < len(sizes):
            selected_size = sizes[idx + 1]
            r_per_m  = rho / selected_size
            vdrop_v  = (math.sqrt(3) if phases == 3 else 2) * current_a * r_per_m * distance_m
            vdrop_pct = vdrop_v / voltage_v * 100

    result = (
        f"## Cable Sizing Result\n"
        f"- **Load**: {_fmt(load_kw,'kW')} at {_fmt(power_factor)} PF, {voltage_v}V {phases}ϕ\n"
        f"- **Design current**: {_fmt(current_a,'A')}\n"
        f"- **Selected cable**: {_fmt(selected_size,'mm²')} {conductor.title()}\n"
        f"- **Installation**: {install_method} (derate: {derate})\n"
        f"- **Voltage drop**: {_fmt(vdrop_v,'V')} ({_fmt(vdrop_pct,'%')} — "
        f"{'✅ OK (< 5%)' if vdrop_pct <= 5 else '⚠️ Exceeds 5% limit'})\n"
        f"- **Standard**: IEC 60364 / IS 732"
    )
    return {"result": result, "selected_mm2": selected_size, "current_a": round(current_a,2),
            "vdrop_pct": round(vdrop_pct,2)}


# ── Transformer sizing ────────────────────────────────────────────────────────
def transformer_sizing(load_kw: float, power_factor: float) -> dict:
    kva_required = load_kw / power_factor
    # Standard IEC transformer ratings (kVA)
    std_ratings = [25,50,63,100,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000]
    selected    = next((r for r in std_ratings if r >= kva_required * 1.1), std_ratings[-1])  # 10% margin
    result = (
        f"## Transformer Sizing\n"
        f"- **Connected load**: {_fmt(load_kw,'kW')} at PF {power_factor}\n"
        f"- **Apparent power**: {_fmt(kva_required,'kVA')}\n"
        f"- **Selected transformer**: **{selected} kVA** (10% safety margin)\n"
        f"- **Loading**: {_fmt(kva_required/selected*100,'%')}\n"
        f"- **Standard**: IEC 60076 / IS 2026"
    )
    return {"result": result, "required_kva": round(kva_required,2), "selected_kva": selected}


# ── Fault level ───────────────────────────────────────────────────────────────
def fault_level(voltage_kv: float, source_mva: float, transformer_kva: float, impedance_pct: float) -> dict:
    z_source   = voltage_kv**2 / source_mva * 1000  # mΩ
    z_xfmr     = impedance_pct / 100 * voltage_kv**2 / (transformer_kva/1000) * 1000
    z_total    = z_source + z_xfmr
    fault_mva  = voltage_kv**2 / (z_total / 1000)
    fault_ka   = fault_mva / (math.sqrt(3) * voltage_kv)
    result = (
        f"## Fault Level Calculation\n"
        f"- **System voltage**: {voltage_kv} kV\n"
        f"- **Source fault MVA**: {source_mva} MVA\n"
        f"- **Transformer**: {transformer_kva} kVA, {impedance_pct}% impedance\n"
        f"- **Total impedance**: {_fmt(z_total,'mΩ')}\n"
        f"- **Fault level**: **{_fmt(fault_mva,'MVA')}** ({_fmt(fault_ka,'kA')})\n"
        f"- **Standard**: IEC 60909"
    )
    return {"result": result, "fault_mva": round(fault_mva,2), "fault_ka": round(fault_ka,3)}


# ── Solar PV design ────────────────────────────────────────────────────────────
def solar_design(demand_kwh: float, peak_power_kw: float, solar_irr: float) -> dict:
    panel_watt    = 550  # standard panel size
    system_eff    = 0.80
    panels_needed = math.ceil(peak_power_kw * 1000 / panel_watt)
    dc_capacity   = panels_needed * panel_watt / 1000
    annual_kwh    = dc_capacity * solar_irr * 365 * system_eff
    coverage_pct  = annual_kwh / (demand_kwh * 365) * 100
    result = (
        f"## Solar PV Design\n"
        f"- **Daily demand**: {demand_kwh} kWh\n"
        f"- **Peak load**: {peak_power_kw} kW\n"
        f"- **Irradiance**: {solar_irr} kWh/m²/day\n"
        f"- **Panels (550Wp)**: {panels_needed} panels = **{_fmt(dc_capacity,'kWp DC')}**\n"
        f"- **Inverter**: {_fmt(peak_power_kw,'kW AC')} (minimum)\n"
        f"- **Annual generation**: {_fmt(annual_kwh,'kWh')}\n"
        f"- **Demand coverage**: {_fmt(coverage_pct,'%')}\n"
        f"- **Standard**: IEC 62446 / IS 16221"
    )
    return {"result": result, "panels": panels_needed, "dc_kw": round(dc_capacity,2),
            "annual_kwh": round(annual_kwh,2), "coverage_pct": round(coverage_pct,1)}


# ── BESS sizing ────────────────────────────────────────────────────────────────
def bess_sizing(peak_power_kw: float, demand_kwh: float, autonomy_hours: float = 2.0) -> dict:
    energy_kwh   = peak_power_kw * autonomy_hours
    usable_kwh   = demand_kwh * 0.30  # 30% peak-shaving
    bess_kwh     = max(energy_kwh, usable_kwh)
    dod          = 0.90  # depth of discharge 90% for LFP
    nominal_kwh  = bess_kwh / dod
    c_rate       = peak_power_kw / bess_kwh
    result = (
        f"## BESS Sizing\n"
        f"- **Peak power**: {peak_power_kw} kW\n"
        f"- **Autonomy**: {autonomy_hours} hours\n"
        f"- **Usable energy**: **{_fmt(bess_kwh,'kWh')}**\n"
        f"- **Nominal capacity**: {_fmt(nominal_kwh,'kWh')} (at 90% DoD)\n"
        f"- **C-rate**: {_fmt(c_rate,'C')}\n"
        f"- **Chemistry recommendation**: {'LFP (safe, long cycle)' if c_rate <= 1 else 'NMC (high power)'}\n"
        f"- **Standard**: IEC 62619 / MNRE guidelines"
    )
    return {"result": result, "usable_kwh": round(bess_kwh,2), "nominal_kwh": round(nominal_kwh,2)}


# ── Tariff calculation ────────────────────────────────────────────────────────
def tariff_calc(load_kw: float, demand_kwh: float, tariff_rate: float) -> dict:
    monthly_kwh  = demand_kwh * 30
    energy_cost  = monthly_kwh * tariff_rate
    demand_charge = load_kw * tariff_rate * 0.5  # typical demand charge
    total_monthly = energy_cost + demand_charge
    result = (
        f"## Tariff Calculation\n"
        f"- **Connected load**: {load_kw} kW\n"
        f"- **Monthly consumption**: {_fmt(monthly_kwh,'kWh')}\n"
        f"- **Energy charge**: {_fmt(energy_cost)} @ ₹{tariff_rate}/kWh\n"
        f"- **Demand charge**: {_fmt(demand_charge)} (estimated)\n"
        f"- **Total monthly**: **{_fmt(total_monthly)}**\n"
        f"- **Annual estimate**: {_fmt(total_monthly*12)}"
    )
    return {"result": result, "monthly_cost": round(total_monthly,2), "monthly_kwh": round(monthly_kwh,2)}


# ── Standards lookup ──────────────────────────────────────────────────────────
_STANDARDS = {
    "cable": "IEC 60502, IEC 60227, IS 1554 — Cable specification; IS 732 — Wiring rules",
    "transformer": "IEC 60076 — Power transformers; IS 2026 — Indian standard",
    "earthing": "IEC 61936, IEC 60364-5-54, IS 3043 — Earthing systems",
    "protection": "IEC 60255 — Relays; IEC 60947 — LV switchgear",
    "solar": "IEC 62446, IEC 61730, IS 16221 — Solar PV systems",
    "bess": "IEC 62619, IEC 62133 — Battery safety",
    "hvac": "IEC 60060, IEC 62271 — HV switchgear and equipment",
    "motor": "IEC 60034 — Rotating machines; IS 325 — Indian standard",
    "fault": "IEC 60909 — Short-circuit calculations",
    "safety": "IEC 60479, IS 5216 — Electrical safety",
}

def standards_lookup(query: str) -> dict:
    q = query.lower()
    matches = {k: v for k, v in _STANDARDS.items() if k in q or any(w in q for w in k.split())}
    if not matches:
        return {"result": f"Standards for '{query}':\n" + "\n".join(f"- {k}: {v}" for k,v in _STANDARDS.items())}
    result = "\n".join(f"**{k.upper()}**: {v}" for k,v in matches.items())
    return {"result": result, "matches": matches}


# ── Main dispatcher ───────────────────────────────────────────────────────────
def run(
    action:        str   = "cable_sizing",
    load_kw:       float = 0,
    voltage_v:     float = 415,
    power_factor:  float = 0.85,
    distance_m:    float = 100,
    install_method:str   = "underground",
    phases:        str   = "3",
    demand_kwh:    float = 0,
    peak_power_kw: float = 0,
    solar_irr:     float = 5.5,
    tariff_rate:   float = 0,
    query:         str   = "",
    username:      str   = "",
) -> dict:
    action  = (action or "cable_sizing").lower().strip()
    phases_ = int(phases) if str(phases) in ("1","3") else 3

    if action == "cable_sizing":
        return cable_sizing(load_kw or 10, voltage_v, power_factor, distance_m, phases_, install_method)

    if action == "transformer":
        return transformer_sizing(load_kw or 100, power_factor)

    if action == "fault_level":
        kv = voltage_v / 1000
        return fault_level(kv or 11, load_kw or 500, demand_kwh or 1000, power_factor * 10 or 5.5)

    if action == "solar_design":
        return solar_design(demand_kwh or 500, peak_power_kw or 100, solar_irr)

    if action == "bess_sizing":
        return bess_sizing(peak_power_kw or 100, demand_kwh or 500, distance_m / 100 if distance_m else 2.0)

    if action == "tariff":
        return tariff_calc(load_kw or 100, demand_kwh or 500, tariff_rate or 6.5)

    if action == "standards":
        return standards_lookup(query or "cable")

    if action == "power_factor":
        if not load_kw or not voltage_v:
            return {"error": "load_kw and voltage_v required"}
        kw  = load_kw
        kva = kw / power_factor
        kvar= math.sqrt(kva**2 - kw**2)
        cap_kvar = kvar * (1 - power_factor / 0.95)  # correct to 0.95 PF
        result = (
            f"## Power Factor Correction\n"
            f"- Active power (P): {_fmt(kw,'kW')}\n"
            f"- Apparent power (S): {_fmt(kva,'kVA')} at PF {power_factor}\n"
            f"- Reactive power (Q): {_fmt(kvar,'kVAR')}\n"
            f"- Capacitor bank for PF 0.95: **{_fmt(max(cap_kvar,0),'kVAR')}**"
        )
        return {"result": result, "kvar_correction": round(max(cap_kvar,0),2)}

    if action == "report":
        parts = []
        if load_kw and voltage_v:
            parts.append(cable_sizing(load_kw, voltage_v, power_factor, distance_m or 100, phases_, install_method)["result"])
            parts.append(transformer_sizing(load_kw, power_factor)["result"])
        if demand_kwh and peak_power_kw:
            parts.append(solar_design(demand_kwh, peak_power_kw, solar_irr)["result"])
            parts.append(bess_sizing(peak_power_kw, demand_kwh)["result"])
        if not parts:
            return {"error": "Provide load_kw + voltage_v and/or demand_kwh + peak_power_kw for a full report"}
        return {"result": "\n\n".join(parts)}

    return {"error": f"Unknown action: {action}"}
