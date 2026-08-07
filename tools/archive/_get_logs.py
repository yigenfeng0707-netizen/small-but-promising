"""查询创空间完整构建日志。"""
import json, urllib.request

API_KEY = "ms-d6326ed9-f8b1-438c-ab98-4e029a5e2f70"
OWNER = "gsym236998"
REPO = "home-chem-safety-agent"

url = f"https://modelscope.cn/openapi/v1/studios/{OWNER}/{REPO}/logs/build?page_size=100"
req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    },
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode())

logs = data.get("data", {}).get("logs", [])
print(f"总日志行数: {len(logs)}")
print(f"状态: {data.get('data', {}).get('status', 'N/A')}")
print()
# 打印最后 50 行
print("=== 最后 50 行构建日志 ===")
for line in logs[-50:]:
    print(line.rstrip())
