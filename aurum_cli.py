#!/usr/bin/env python3
"""aurum CLI -- talk to your Aurum server from any terminal.

  python aurum_cli.py "explain IS 3043 earthing"
  python aurum_cli.py --team "research BESS prices and summarize"
  python aurum_cli.py --tool weather --args \'{"city": "Hyderabad"}\'

Env: AURUM_URL (default http://localhost:5000), AURUM_API_KEY (required).
"""
import json
import os
import sys
import requests

URL = os.getenv("AURUM_URL", "http://localhost:5000").rstrip("/")
KEY = os.getenv("AURUM_API_KEY", "")


def main():
    if not KEY:
        sys.exit("Set AURUM_API_KEY (same value as in the server .env)")
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    headers = {"X-API-Key": KEY}
    if args[0] == "--team":
        r = requests.post(URL + "/api/team", json={"goal": " ".join(args[1:])},
                          headers=headers, timeout=600)
        print(r.json().get("reply", r.text))
    elif args[0] == "--tool":
        tool = args[1]
        extra = json.loads(args[3]) if len(args) > 3 and args[2] == "--args" else {}
        r = requests.post(URL + "/api/tool", json={"tool": tool, "args": extra},
                          headers=headers, timeout=300)
        print(json.dumps(r.json(), indent=2)[:4000])
    else:
        r = requests.post(URL + "/api/ask", json={"message": " ".join(args)},
                          headers=headers, timeout=300)
        d = r.json()
        print(d.get("reply", d))


if __name__ == "__main__":
    main()
