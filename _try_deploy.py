"""尝试多种方式触发首次部署。

方案1: restart 带 force 参数
方案2: 重新 PUT 完整配置（force_rebuild 的变体）
方案3: 直接访问 /api/v1/studio/{owner}/{name}/startup
方案4: POST /api/v1/studio/{owner}/{name}/deploy
"""
import json, os, pickle, urllib.request, urllib.error

OWNER = "gsym236998"
NAME = "home-chem-safety-agent"

cookie_path = os.path.expanduser("~/.modelscope/credentials/cookies")
with open(cookie_path, "rb") as f:
    cookies = pickle.loads(f.read())
cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

api_key = "ms-d6326ed9-f8b1-438c-ab98-4e029a5e2f70"

# 方案1: restart 带 force=true 参数
print("=" * 60)
print("方案1: restart 带 force=true")
print("=" * 60)
for path in [
    f"/api/v1/studio/{OWNER}/{NAME}/restart?force=true",
    f"/api/v1/studio/{OWNER}/{NAME}/restart?deep=true",
]:
    url = f"https://www.modelscope.cn{path}"
    req = urllib.request.Request(
        url, data=json.dumps({"force": True, "deep": True}).encode(),
        headers={
            "Cookie": cookie_str, "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0", "Accept": "application/json",
            "Referer": f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary",
        }, method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"✅ {path}")
            print(json.dumps(json.loads(r.read().decode()), ensure_ascii=False)[:300])
            break
    except urllib.error.HTTPError as e:
        print(f"❌ {path}: HTTP {e.code} - {e.read().decode('utf-8', errors='ignore')[:200]}")

# 方案2: POST /startup
print("\n" + "=" * 60)
print("方案2: /startup 和 /deploy 端点")
print("=" * 60)
for method, path in [
    ("POST", f"/api/v1/studio/{OWNER}/{NAME}/startup"),
    ("POST", f"/api/v1/studio/{OWNER}/{NAME}/deploy"),
    ("PUT", f"/api/v1/studio/{OWNER}/{NAME}/startup"),
    ("PUT", f"/api/v1/studio/{OWNER}/{NAME}/deploy"),
]:
    url = f"https://www.modelscope.cn{path}"
    req = urllib.request.Request(
        url, data=json.dumps({}).encode(),
        headers={
            "Cookie": cookie_str, "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0", "Accept": "application/json",
            "Referer": f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary",
        }, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"✅ {method} {path}")
            print(json.dumps(json.loads(r.read().decode()), ensure_ascii=False)[:300])
            break
    except urllib.error.HTTPError as e:
        print(f"❌ {method} {path}: HTTP {e.code}")

# 方案3: OpenAPI 触发部署
print("\n" + "=" * 60)
print("方案3: OpenAPI /studios/{owner}/{name}/deploy")
print("=" * 60)
for method, path in [
    ("POST", f"/openapi/v1/studios/{OWNER}/{NAME}/deploy"),
    ("PUT", f"/openapi/v1/studios/{OWNER}/{NAME}/deploy"),
    ("POST", f"/openapi/v1/studios/{OWNER}/{NAME}/restart"),
]:
    url = f"https://modelscope.cn{path}"
    req = urllib.request.Request(
        url, data=json.dumps({}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"✅ {method} {path}")
            print(json.dumps(json.loads(r.read().decode()), ensure_ascii=False)[:300])
            break
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"❌ {method} {path}: HTTP {e.code} - {body}")

# 方案4: 再次 force_rebuild，但去掉 SdkVersion（Docker 类型不需要）
print("\n" + "=" * 60)
print("方案4: force_rebuild 不带 SdkVersion")
print("=" * 60)
put_data = {
    "Name": NAME, "Owner": OWNER, "Visibility": 5,
    "DeployedByUser": True,
    "InstanceTypeName": "ecs.r7.large", "InstanceTypeId": 1,
    "InstanceNumber": 1, "DiskSize": 50,
    "SupportMobile": 0, "Revision": "master",
    "ExpiredMinutes": 0, "SupportWxMiniprogram": True,
    "ProtectedMode": 0, "ServerSideRender": False,
    "McpServer": False, "NeedLogin": False,
    "Type": "programmatic", "SdkType": "docker",
}
req = urllib.request.Request(
    f"https://www.modelscope.cn/api/v1/studio/{OWNER}/{NAME}",
    data=json.dumps(put_data).encode(),
    headers={
        "Cookie": cookie_str, "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0", "Accept": "application/json",
        "Referer": f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary",
    }, method="PUT",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read().decode())
        print(f"✅ force_rebuild 结果: {json.dumps(result, ensure_ascii=False)[:300]}")
except urllib.error.HTTPError as e:
    print(f"❌ HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:300]}")
