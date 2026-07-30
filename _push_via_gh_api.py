"""用 gh CLI Git Database API 批量推送文件到 GitHub（绕过 git push 网络问题）。

流程：遍历本地文件 → 创建 blob → 创建 tree → 创建 commit → 创建 ref
适用于：仓库为空 + git push 网络不通的场景。
"""
import os
import json
import base64
import subprocess
import tempfile
import sys

# 强制无缓冲输出，确保进度实时可见
sys.stdout.reconfigure(line_buffering=True)

REPO = "yigenfeng0707-netizen/small-but-promising"
BRANCH = "main"
ROOT = os.path.dirname(os.path.abspath(__file__))


def gh_api(endpoint, method="GET", input_data=None):
    """调用 gh api，返回 JSON。大 body 用 --input 从临时文件读取。"""
    cmd = ["gh", "api", endpoint, "-X", method]
    tmp_name = None
    if input_data:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(input_data, f)
            tmp_name = f.name
        cmd.extend(["--input", tmp_name])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(f"gh api {endpoint} failed: {r.stderr[:200]}")
        return json.loads(r.stdout) if r.stdout.strip() else {}
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main():
    # 1. 收集所有文件（排除 .git、运行时数据、缓存目录）
    files = []
    skip_names = {
        ".git", "_push_via_gh_api.py", "__pycache__", ".pytest_cache",
        "node_modules", "storage", "uploads", ".venv", "venv",
    }
    for root, dirs, filenames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_names]
        for filename in filenames:
            filepath = os.path.join(root, filename)
            relpath = os.path.relpath(filepath, ROOT).replace("\\", "/")
            files.append((filepath, relpath))

    total = len(files)
    print(f"共 {total} 个文件待上传")

    # 2. 初始化仓库（如果仓库为空，先创建 .gitkeep；否则跳过）
    try:
        ref = gh_api(f"repos/{REPO}/git/ref/heads/{BRANCH}")
        parent_sha = ref["object"]["sha"]
        print(f"✅ 仓库已初始化，当前 HEAD: {parent_sha[:7]}")
    except RuntimeError:
        # 仓库为空，用 Contents API 创建初始文件
        print("初始化仓库（创建 .gitkeep）...")
        init_content = base64.b64encode(b"").decode("ascii")
        gh_api(
            f"repos/{REPO}/contents/.gitkeep",
            method="PUT",
            input_data={
                "message": "init repo",
                "content": init_content,
                "branch": BRANCH,
            },
        )
        print("✅ 仓库已初始化")
        ref = gh_api(f"repos/{REPO}/git/ref/heads/{BRANCH}")
        parent_sha = ref["object"]["sha"]

    # 3. 获取初始 commit 的 tree sha（作为新 tree 的 base）
    parent_commit = gh_api(f"repos/{REPO}/git/commits/{parent_sha}")
    base_tree_sha = parent_commit["tree"]["sha"]
    print(f"✅ Parent commit: {parent_sha[:7]}, base tree: {base_tree_sha[:7]}")

    # 4. 创建 blob（每个文件一个）
    tree_entries = []
    for i, (filepath, relpath) in enumerate(files):
        with open(filepath, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")

        blob = gh_api(
            f"repos/{REPO}/git/blobs",
            method="POST",
            input_data={"content": content, "encoding": "base64"},
        )
        tree_entries.append(
            {"path": relpath, "mode": "100644", "type": "blob", "sha": blob["sha"]}
        )
        if (i + 1) % 10 == 0 or i == total - 1:
            print(f"  blob [{i+1}/{total}] {relpath}")

    print(f"✅ {total} 个 blob 创建完成")

    # 5. 创建 tree（基于初始 tree）
    tree = gh_api(
        f"repos/{REPO}/git/trees",
        method="POST",
        input_data={"base_tree": base_tree_sha, "tree": tree_entries},
    )
    print(f"✅ Tree created: {tree['sha']}")

    # 6. 创建 commit（有 parent）
    commit = gh_api(
        f"repos/{REPO}/git/commits",
        method="POST",
        input_data={
            "message": "feat: 安居智评 Agent 初始提交 + 魔搭创空间自动部署\n\n6 Agent 编排 + Qwen3/Qwen-VL + FastAPI + React + MSDS知识库 + Docker多阶段构建 + GitHub Actions自动部署到魔搭创空间",
            "tree": tree["sha"],
            "parents": [parent_sha],
        },
    )
    print(f"✅ Commit created: {commit['sha']}")

    # 7. 更新 main ref 指向新 commit
    gh_api(
        f"repos/{REPO}/git/refs/heads/{BRANCH}",
        method="PATCH",
        input_data={"sha": commit["sha"], "force": False},
    )
    print(f"✅ Branch '{BRANCH}' updated!")
    print(f"\n🎉 推送完成！")
    print(f"   仓库: https://github.com/{REPO}")
    print(f"   文件数: {total}")
    print(f"   Commit: {commit['sha'][:7]}")


if __name__ == "__main__":
    main()
