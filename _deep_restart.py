"""尝试深度重启 API。

魔搭提示"该创空间建议使用深度重启"，尝试不同的深度重启接口路径：
- /deep-restart
- /force-restart
- /rebuild
- /deep_restart
"""
import json, os, pickle, urllib.request, urllib.error

OWNER = "gsym236998"
NAME = "home-chem-safety-agent"

cookie_path = os.path.expanduser("~/.modelscope/credentials/cookies")
with open(cookie_path, "rb") as f:
    cookies = pickle.loads(f.read())
cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

endpoints = [
    ("PUT", f"/api/v1/studio/{OWNER}/{NAME}/deep-restart"),
    ("PUT", f"/api/v1/studio/{OWNER}/{NAME}/deep_restart"),
    ("POST", f"/api/v1/studio/{OWNER}/{NAME}/deep-restart"),
    ("POST", f"/api/v1/studio/{OWNER}/{NAME}/rebuild"),
    ("PUT", f"/api/v1/studio/{OWNER}/{NAME}/force-restart"),
    ("POST", f"/api/v1/studio/{OWNER}/{NAME}/restart"),
]

for method, path in endpoints:
    url = f"https://www.modelscope.cn{path}"
    print(f"\n尝试 {method} {path}")
    req = urllib.request.Request(
        url,
        data=json.dumps({}).encode(),
        headers={
            "Cookie": cookie_str,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read().decode())
            print(f"  ✅ 成功: {json.dumps(result, ensure_ascii=False)[:300]}")
            break
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"  ❌ HTTP {e.code}: {body}")
    except Exception as e:
        print(f"  ❌ 异常: {e}")
