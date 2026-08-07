"""查询创空间当前状态。"""
import json, urllib.request, urllib.error

API_KEY = "ms-d6326ed9-f8b1-438c-ab98-4e029a5e2f70"
OWNER = "gsym236998"
REPO = "home-chem-safety-agent"

req = urllib.request.Request(
    f"https://modelscope.cn/openapi/v1/studios/{OWNER}/{REPO}",
    headers={"Authorization": f"Bearer {API_KEY}", "User-Agent": "Mozilla/5.0"},
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
        print(json.dumps(data, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:500]}")
