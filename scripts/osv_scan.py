import json, re, sys, urllib.request

lock_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/yyc3-req.lock'
locks = [l.strip() for l in open(lock_path) if l.strip() and not l.startswith('#')]
pkgs = []
for l in locks:
    m = re.match(r'^([a-zA-Z0-9_.\-]+)==([0-9][0-9a-zA-Z.+\-]*)', l)
    if m:
        pkgs.append((m.group(1), m.group(2)))
print(f"resolved {len(pkgs)} packages")

seen = set()
unique = []
for n, v in pkgs:
    if (n, v) not in seen:
        seen.add((n, v))
        unique.append((n, v))

def osv_query(name, ver):
    body = json.dumps({"package": {"name": name, "ecosystem": "PyPI"}, "version": ver}).encode()
    req = urllib.request.Request("https://api.osv.dev/v1/query", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

vulns = []
for name, ver in unique:
    try:
        res = osv_query(name, ver)
        for v in res.get("vulns", []):
            sev = ""
            for d in v.get("severity", []):
                sev += f"{d.get('type')}={d.get('score')} "
            vulns.append((name, ver, v["id"], v.get("summary", "")[:120], sev.strip()))
    except Exception as e:
        print(f"  ! {name}=={ver} query failed: {e}")

print(f"\n=== 漏洞数: {len(vulns)} ===")
for name, ver, vid, summary, sev in sorted(vulns):
    print(f"- {name}=={ver} | {vid} | {sev} | {summary}")
