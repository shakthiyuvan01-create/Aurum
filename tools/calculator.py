"""Calculator tool — safe expression evaluator with math functions."""
import math, re, ast as _ast

NAME        = "calculator"
DESCRIPTION = "Evaluate mathematical expressions, unit conversions, and scientific functions"
CATEGORY    = "builtin"
ICON        = "🧮"
INPUTS = [
    {"name": "expression", "label": "Expression", "type": "text",
     "placeholder": "e.g. sqrt(144) + 2^10  or  sin(pi/4)", "required": True},
]

# Safe math namespace
_NS = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
_NS.update({"abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "int": int, "float": float})

_WORD_OPS = [
    (r"\bsquare root of\b",    "sqrt"),
    (r"\bcube root of\b",      "cbrt"),
    (r"\bsquared\b",           "**2"),
    (r"\bcubed\b",             "**3"),
    (r"\bto the power of\b",   "**"),
    (r"\btimes\b",             "*"),
    (r"\bdivided by\b",        "/"),
    (r"\bplus\b",              "+"),
    (r"\bminus\b",             "-"),
    (r"\bpercent of\b",        "/100*"),
    (r"\bmodulo\b",            "%"),
    (r"\bmod\b",               "%"),
    (r"\bpi\b",                str(math.pi)),
    (r"\be\b",                 str(math.e)),
]

# Unit conversions: (from_pattern, to_unit, factor_or_fn)
_UNIT_CONV = {
    ("km",  "miles"):   lambda x: x * 0.621371,
    ("miles", "km"):    lambda x: x * 1.60934,
    ("kg",  "lbs"):     lambda x: x * 2.20462,
    ("lbs", "kg"):      lambda x: x / 2.20462,
    ("c",   "f"):       lambda x: x * 9/5 + 32,
    ("f",   "c"):       lambda x: (x - 32) * 5/9,
    ("m",   "feet"):    lambda x: x * 3.28084,
    ("feet","m"):       lambda x: x / 3.28084,
    ("l",   "gallons"): lambda x: x * 0.264172,
    ("gallons","l"):    lambda x: x / 0.264172,
}

def _try_unit_conversion(expr: str):
    m = re.match(
        r"([\d.]+)\s*(km|miles|kg|lbs|c|f|m|feet|l|gallons)\s+(?:in|to|as)\s+(km|miles|kg|lbs|c|f|m|feet|l|gallons)",
        expr.lower().strip()
    )
    if not m:
        return None
    val, frm, to = float(m.group(1)), m.group(2), m.group(3)
    fn = _UNIT_CONV.get((frm, to))
    if fn:
        result = fn(val)
        return {"result": round(result, 6), "expression": expr,
                "formatted": f"{val} {frm} = {round(result,4)} {to}"}
    return None

def _safe_eval(expr: str):
    tree = _ast.parse(expr, mode="eval")
    # Whitelist node types
    allowed = (
        _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Call, _ast.Constant,
        _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow, _ast.Mod,
        _ast.FloorDiv, _ast.USub, _ast.UAdd, _ast.Name, _ast.Load,
        _ast.Compare, _ast.Eq, _ast.NotEq, _ast.Lt, _ast.LtE, _ast.Gt, _ast.GtE,
    )
    for node in _ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError(f"Disallowed expression: {type(node).__name__}")
    return eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, _NS)

def run(expression: str) -> dict:
    expr = expression.strip()

    # Try unit conversion first
    conv = _try_unit_conversion(expr)
    if conv:
        return conv

    # Normalise word operators
    low = expr.lower()
    for pattern, repl in _WORD_OPS:
        low = re.sub(pattern, repl, low)

    # ^ → **
    low = low.replace("^", "**")
    # Remove trailing punctuation
    low = low.rstrip(".,;")

    try:
        result = _safe_eval(low)
        if isinstance(result, float):
            result = round(result, 10)
            if result == int(result) and abs(result) < 1e15:
                result = int(result)
        return {"result": result, "expression": expression,
                "formatted": f"{expression} = {result}"}
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except Exception as e:
        return {"error": f"Cannot evaluate: {e}"}
