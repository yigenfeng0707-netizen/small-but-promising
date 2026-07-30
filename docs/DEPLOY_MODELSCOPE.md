# 魔搭创空间部署指南

本文档说明如何把「安居智评 Agent」部署到魔搭 ModelScope 创空间。
创空间提供免费的 CPU 云资源（2vCPU/16G）和稳定的外部可访问 URL，适合作为比赛 Demo 长期托管。

## 部署架构

```
魔搭创空间 Docker SDK
├── Dockerfile (多阶段构建：前端 build + 后端 runtime)
├── ms_deploy.json (魔搭部署配置：port 7860 + 免费CPU资源)
├── /mnt/workspace (创空间唯一持久化卷)
│   ├── uploads/       ← 评测图片持久化
│   └── storage/reports/  ← 评测报告 JSON 持久化
└── 端口 7860 (前后端同端口，FastAPI 内置 SPA 兜底)
```

**关键适配点**（已在代码中完成）：

1. `backend/config.py` 集中解析 `UPLOAD_DIR` / `REPORT_DIR`，检测到 `/mnt/workspace` 存在时自动重定向到持久化卷
2. `backend/config.py` 新增 `PORT` 配置项（默认 8000，魔搭部署时由环境变量设为 7860）
3. `Dockerfile` `EXPOSE 7860`，启动命令通过 `${PORT:-8000}` 读取环境变量
4. `ms_deploy.json` 声明 Docker SDK + port 7860 + 免费资源

## 前置准备

1. 注册魔搭账号并登录：https://www.modelscope.cn
2. 本地安装 `git` 和 `git-lfs`：
   ```powershell
   # Windows: 从 https://git-scm.com 安装 Git
   # 然后启用 LFS
   git lfs install
   ```
3. 准备好百炼 `DASHSCOPE_API_KEY`（普通账号 Key 形如 `sk-xxx`）

## 部署步骤

### 步骤 1：在魔搭创建创空间

1. 访问 https://modelscope.cn/studios/create?template=quick （快速创建并部署模式）
2. 填写基础信息：
   - **空间英文名称**：`home-chem-safety-agent`（自定义）
   - **空间中文名称**：`安居智评 Agent`
   - **空间描述**：家庭化学品安全智能评测 Agent —— 拍照识别 → 风险评测 → 应急指导
   - **是否公开**：建议公开（便于评委访问）
   - **License**：选 Apache 2.0 或 MIT
3. 顶部切换到「快速部署并创建」模式（重要：不是「自定义创建」）

### 步骤 2：本地准备部署包

项目根目录已包含魔搭部署所需文件：

- `ms_deploy.json` —— 魔搭部署配置
- `Dockerfile` —— 多阶段构建（前端 build + 后端 runtime）
- `backend/`、`frontend/`、`knowledge_base/` —— 应用代码

无需额外准备，整个项目目录直接上传即可。

### 步骤 3：上传项目并部署

**方式 A：网页拖拽上传（推荐，最简单）**

1. 在步骤 1 的创建页面，点击或拖拽上传整个项目文件夹
2. 平台自动检测 `ms_deploy.json`，确认配置无误
3. 点击「确认创建并部署」

**方式 B：Git push 上传**

```powershell
# 1. 创建创空间后，从创空间详情页获取 Git 仓库地址
# 形如：https://www.modelscope.cn/studios/<your-name>/home-chem-safety-agent.git

# 2. 获取访问令牌
# 访问 https://modelscope.cn/my/myaccesstoken 创建令牌

# 3. 克隆创空间仓库（用令牌替换 <token>）
git clone http://oauth2:<your_access_token>@www.modelscope.cn/studios/<your-name>/home-chem-safety-agent.git
cd home-chem-safety-agent

# 4. 把项目所有文件复制进来（覆盖初始 README.md 之外的所有文件）

# 5. 提交并推送
git add .
git commit -m "deploy: 安居智评 Agent 首次部署"
git push
```

推送完成后，回到创空间网页，点击「立即发布」或「上线」按钮触发部署。

### 步骤 4：配置环境变量（关键）

部署前或部署失败后，在创空间**设置页 → 环境变量管理**添加以下变量：

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `DASHSCOPE_API_KEY` | ✅ 必填 | 百炼 DashScope API Key（形如 `sk-xxx`） |
| `PORT` | ✅ 已内置 | `7860`（已通过 ms_deploy.json 注入，无需手动添加） |
| `DASHSCOPE_API_BASE` | 可选 | 业务空间专属网关 URL（普通账号 Key 留空） |
| `QWEN3_MODEL` | 可选 | 默认 `qwen-plus`，可改为 `qwen-max` 等 |
| `QWEN_VL_MODEL` | 可选 | 默认 `qwen-vl-plus` |
| `CORS_ORIGINS` | 可选 | 创空间同端口无跨域，可留默认 |

**注意**：环境变量添加/修改后，必须点击「重启创空间」才生效。

### 步骤 5：验证部署

部署成功后（状态变为「运行中」），按以下清单验证：

1. **访问首页**：打开创空间 URL，应看到安居智评首页（拍照/上传/语音三种入口）
2. **健康检查**：浏览器访问 `https://<创空间URL>/health`，应返回 `{"status":"ok"}`
3. **API 文档**：访问 `https://<创空间URL>/docs`，应看到 FastAPI 自动生成的 OpenAPI 文档
4. **功能验证**：
   - 上传一张清洁剂照片 → 等待评测 → 看到识别结果 + 风险评分 + 应急指导
   - 语音/文本输入"84消毒液" → 看到完整评测结果
   - 点击「导出 PDF」→ 下载评测报告 PDF
5. **持久化验证**：评测一次后，点击「重启创空间」，再访问之前的报告 URL（`/api/report/{request_id}`），应仍能读取（说明 `/mnt/workspace` 持久化生效）

### 步骤 6：查看日志排错

如果部署失败或运行异常：
1. 创空间详情页右上角 `...` → 「查看日志」
2. 切换到「构建日志」查看镜像构建阶段问题
3. 切换到「运行日志」查看应用启动/运行时问题
4. 常见错误：
   - `Address already in use port 7860`：检查是否其他进程占用，或重启创空间
   - `DASHSCOPE_API_KEY not set`：环境变量未配置或未重启
   - `ModuleNotFoundError`：检查 `backend/requirements.txt` 是否完整

## 常见问题

### Q1: 部署后访问首页是空白？

检查运行日志，可能是前端 build 产物未正确挂载。Dockerfile Stage 1 会构建前端到 `/app/static`，`main.py` 的 SPA 兜底路由会从这里读 `index.html`。如果日志显示 `Static index not found`，确认 Dockerfile 第 51 行 `COPY --from=frontend-build /app/frontend/dist /app/static` 执行成功。

### Q2: 评测请求报 500？

最可能是 `DASHSCOPE_API_KEY` 未配置或无效。在创空间设置页确认环境变量已添加并重启。

### Q3: 重启后报告丢失？

确认 `config.py` 路径检测逻辑生效：运行日志启动时应能看到 `UPLOAD_DIR` / `REPORT_DIR` 指向 `/mnt/workspace/...`。如果仍指向 `backend/uploads`，说明 `/mnt/workspace` 不存在（创空间环境异常），联系魔搭客服。

### Q4: 想用 GPU 加速？

`ms_deploy.json` 的 `resource_configuration` 改为 `xgpu/8v-cpu-32g-mem-16g`（需先加入「xGPU乐园」组织）。本项目用 Qwen-VL API 调用远端大模型，本地无需 GPU，免费 CPU 资源足够。

### Q5: 如何更新代码？

本地修改后 `git push`，然后在创空间设置页点击「重启创空间」，平台会拉取最新代码重新部署。

## 资源与链接

- 魔搭创空间文档：https://www.modelscope.cn/docs/创空间创建与搭建
- 快速创建并部署文档：https://www.modelscope.cn/docs/studios/quick-create
- 部署 Schema：https://modelscope.cn/api/v1/studios/deploy_schema.json
- 访问令牌：https://modelscope.cn/my/myaccesstoken
- 技术交流钉钉群：44837352
