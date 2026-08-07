"""尝试 restart API 触发部署（状态已是 Initialized）。"""
import json, os, pickle, urllib.request, urllib.error

OWNER = "gsym236998"
NAME = "home-chem-safety-agent"

cookie_path = os.path.expanduser("~/.modelscope/credentials/cookies")
with open(cookie_path, "rb") as f:
    cookies = pickle.loads(f.read())
cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

# 尝试 restart API
print("🔄 调用 restart API...")
req = urllib.request.Request(
    f"https://www.modelscope.cn/api/v1/studio/{OWNER}/{NAME}/restart",
    data=json.dumps({}).encode(),
    headers={
        "Cookie": cookie_str,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary",
    },
    method="PUT",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read().decode())
        print(f"restart 结果: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
except urllib.error.HTTPError as e:
    print(f"❌ restart 失败: HTTP {e.code}")
    print(e.read().decode("utf-8", errors="ignore")[:500])
