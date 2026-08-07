"""首次部署触发：用 force_rebuild API（PUT /api/v1/studio/{owner}/{name}）。

借鉴 MedEvidence-AI modelscope-studio-manager Skill 的 force_rebuild 方法。
适用于：创空间刚创建，Status 为 Empty/Initialized，从未部署过的场景。
"""
import json
import os
import pickle
import urllib.request
import urllib.error

OWNER = "gsym236998"
NAME = "home-chem-safety-agent"

# 1. 读取 cookie
cookie_path = os.path.expanduser("~/.modelscope/credentials/cookies")
with open(cookie_path, "rb") as f:
    cookies = pickle.loads(f.read())
cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
print(f"✅ Cookie 加载成功，长度: {len(cookie_str)}")

# 2. 获取当前创空间信息（获取现有配置）
req = urllib.request.Request(
    f"https://www.modelscope.cn/api/v1/studio/{OWNER}/{NAME}",
    headers={
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    },
)
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())
    studio_data = data.get("Data", {})
    print(f"当前 Status: {studio_data.get('Status')}")
    print(f"当前 Revision: {studio_data.get('Revision')}")
    print(f"当前 SdkVersion: {studio_data.get('SdkVersion')}")

# 3. 获取魔搭创空间 master 分支最新 commit SHA（作为 Revision）
req = urllib.request.Request(
    f"https://www.modelscope.cn/api/v1/models/{OWNER}/{NAME}/repo?Revision=master&FilePath=&Recursive=true",
    headers={
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    },
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        repo_data = json.loads(r.read().decode())
        # 获取最新 commit
        rev_data = repo_data.get("Data", {}).get("Revision", {})
        if isinstance(rev_data, dict):
            latest_commit = rev_data.get("CommitId", "")
        else:
            latest_commit = str(rev_data)
        print(f"魔搭 master 最新 commit: {latest_commit[:12]}")
except urllib.error.HTTPError as e:
    print(f"获取 commit 失败: HTTP {e.code}")
    latest_commit = ""
    # 尝试另一个接口
    try:
        req2 = urllib.request.Request(
            f"https://www.modelscope.cn/api/v1/studio/{OWNER}/{NAME}",
            headers={"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req2, timeout=15) as r2:
            d = json.loads(r2.read().decode()).get("Data", {})
            latest_commit = d.get("Revision", "")
            print(f"从 studio API 获取 Revision: {latest_commit}")
    except Exception as e2:
        print(f"备用接口也失败: {e2}")

# 4. force_rebuild：PUT 完整部署配置触发首次部署
# 借鉴 MedEvidence-AI skill 的 force_rebuild 函数
put_data = {
    "Name": NAME,
    "Owner": OWNER,
    "Visibility": 5,  # public
    "DeployedByUser": True,
    "InstanceTypeName": "ecs.r7.large",
    "InstanceTypeId": 1,
    "InstanceNumber": 1,
    "DiskSize": 50,
    "SupportMobile": 0,
    "SdkVersion": "6.17.3",  # MedEvidence-AI 用的版本
    "Revision": latest_commit or "master",  # 用最新 commit SHA 或 master
    "ExpiredMinutes": 0,
    "SupportWxMiniprogram": True,
    "ProtectedMode": 0,
    "ServerSideRender": False,
    "McpServer": False,
    "NeedLogin": False,
    "Type": "programmatic",
    "SdkType": "docker",
}

print(f"\n🚀 触发 force_rebuild（首次部署）...")
print(f"配置: {json.dumps(put_data, ensure_ascii=False, indent=2)}")

req = urllib.request.Request(
    f"https://www.modelscope.cn/api/v1/studio/{OWNER}/{NAME}",
    data=json.dumps(put_data).encode(),
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
        print(f"\n✅ force_rebuild 结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
except urllib.error.HTTPError as e:
    print(f"\n❌ force_rebuild 失败: HTTP {e.code}")
    print(e.read().decode("utf-8", errors="ignore")[:500])
