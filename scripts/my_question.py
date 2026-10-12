#!/usr/bin/env python3
"""Create my own Metabase question: frame drop rate by trip (top 10)."""
import json
import urllib.request
import urllib.error

MB = "http://localhost:3000"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(MB + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"X-Metabase-Session": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        print("ERROR", e.code, e.read().decode()[:300])
        raise


token = call("POST", "/api/session", {"username": "lab@example.com", "password": "Day9-lab-pass!"})["id"]
dbs = call("GET", "/api/database", token=token)["data"]
wh = next(d for d in dbs if d["engine"] == "postgres")

try:
    call("DELETE", "/api/card/46", token=token)
except Exception:
    pass

sql = ("select t.trip_id, t.drive_id, t.frames, t.frames_kept, t.lighting, t.conditions, "
       "round(100.0 * (t.frames - t.frames_kept) / t.frames, 1) as drop_pct "
       "from marts.mart_trip_summary t order by drop_pct desc limit 10")
card = call("POST", "/api/card", {
    "name": "My question: frame drop rate by trip (top 10)",
    "display": "bar",
    "visualization_settings": {},
    "dataset_query": {"type": "native", "database": wh["id"], "native": {"query": sql}},
}, token=token)
print("created card id:", card["id"])

res = call("POST", "/api/card/%d/query" % card["id"], {}, token=token)
rows = res["data"]["rows"]
cols = [c["name"] for c in res["data"]["cols"]]
print("|".join(cols))
for r in rows:
    print("|".join(str(x) for x in r))
