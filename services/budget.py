"""services/budget.py -- per-user daily token ceiling (reuses provider_usage)."""
import os, sqlite3, time, logging
log = logging.getLogger('services.budget')
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aiaurum.db')

def _budget():
    return int(os.getenv('DAILY_TOKEN_BUDGET', '4000000'))

def tokens_used_today():
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as con:
            row = con.execute('SELECT COALESCE(SUM(est_tokens),0) FROM provider_usage WHERE day=?', (time.strftime('%Y-%m-%d'),)).fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0

def check():
    budget = _budget()
    if budget <= 0:
        return {'ok': True, 'unlimited': True}
    used = tokens_used_today()
    return {'ok': used < budget, 'used': used, 'budget': budget, 'remaining': max(0, budget - used)}
