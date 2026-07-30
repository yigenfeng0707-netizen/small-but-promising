# 安居智评 Agent 部署指南

本文档说明如何把「安居智评」家庭化学品安全评测 Agent 部署到云端或本地 Docker。
项目采用 **前后端合并部署**：前端 React/Vite build 后产物由 FastAPI 同一服务托管，
对外只暴露一个 HTTP 端口（默认 8000），同时提供 `/api/*` 接口和 `/` 前端页面。

> 适用版本：Task 8 配套。如需独立部署前端到 CDN，参考文末「备选方案」。

---

## 1. 部署架构

```
┌───────────────────────────────────────────────────────┐
│  容器 (anju-zhiping)                                  │
│                                                       │
│   uvicorn main:app --host 0.0.0.0 --port 8000        │
│                                                       │
│   ┌──────────────────────────────────────────────┐    │
│   │  FastAPI (backend/main.py)                   │    │
│   │                                              │    │
│   │  /health            → 健康检查               │    │
│   │  /api/evaluate      → 单次评测               │    │
│   │  /api/evaluate/upload → 上传图片评测         │    │
│   │  /api/voice         → 语音/文本评测          │    │
│   │  /api/batch-evaluate→ 批量评测（公益对接）   │    │
│   │  /api/report/{id}   → 查询报告               │    │
│   │  /api/report/{id}/pdf → 导出 PDF             │    │
│   │  /uploads/...       → 上传图片静态服务       │    │
│   │  /                  → 前端 index.html (SPA)  │    │
│   │  /assets/...        → 前端 JS/CSS 静态资源   │    │
│   └──────────────────────────────────────────────┘    │
│                                                       │
│   /app/static/        ← frontend build 产物          │
│   /app/backend/       ← FastAPI 源码                  │
│   /app/knowledge_base/ ← MSDS 知识库 (58 条)          │
└───────────────────────────────────────────────────────┘
        ▲
        │ HTTPS
        ▼
   云平台负载均衡 (Zeabur / Railway / Render / Cloud Run)
```

---

## 2. 环境变量清单

| 变量名 | 必填 | 默认值 | 说明 |
|--------|:---:|--------|------|
| `DASHSCOPE_API_KEY` | **是** | — | 阿里云百炼 DashScope API Key。在 [百炼控制台](https://bailian.console.aliyun.com/) 获取，用于调用 Qwen3 / Qwen-VL。 |
| `REDIS_URL` | 否 | `redis://localhost:6379` | Redis 连接地址，用于任务队列/缓存。本地或单实例部署可不配。 |
| `QWEN3_MODEL` | 否 | `qwen-plus` | Qwen3 文本推理模型名。可选 `qwen-plus` / `qwen-max` / `qwen-turbo` 等。 |
| `QWEN_VL_MODEL` | 否 | `qwen-vl-plus` | Qwen-VL 多模态模型名。可选 `qwen-vl-plus` / `qwen-vl-max`。 |
| `CORS_ORIGINS` | 否 | `http://localhost:5173,http://127.0.0.1:5173` | CORS 允许的前端来源，逗号分隔。**同源部署时（前端由 FastAPI 托管）可留空**。 |

> 安全提示：**绝不把 `.env` 文件提交到 Git 仓库**。所有平台请用各自控制台的「环境变量/Secrets」功能注入。

---

## 3. 本地 Docker 部署

### 3.1 前置要求

- Docker 20.10+（含 BuildKit）
- 已获取 `DASHSCOPE_API_KEY`

### 3.2 构建与运行

```bash
# 在项目根目录执行
docker build -t anju-zhiping .

# 启动容器（必填 DASHSCOPE_API_KEY）
docker run -d \
  --name anju-zhiping \
  -p 8000:8000 \
  -e DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx \
  -e CORS_ORIGINS=http://localhost:8000 \
  anju-zhiping
```

### 3.3 验证

```bash
# 健康检查
curl http://localhost:8000/health
# 期望：{"status":"ok"}

# 访问前端首页
curl -I http://localhost:8000/
# 期望：HTTP/1.1 200 OK，Content-Type: text/html

# 调用评测接口
curl -X POST http://localhost:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"voice_text":"84消毒液和洁厕灵能混用吗"}'
```

### 3.4 查看日志 / 停止

```bash
docker logs -f anju-zhiping
docker stop anju-zhiping && docker rm anju-zhiping
```

---

## 4. 云平台部署（三选一）

### 4.1 Zeabur（推荐，国内访问快）

1. **注册账号**：访问 [https://zeabur.com](https://zeabur.com)，用 GitHub 账号登录。
2. **新建项目**：Dashboard → New Project → 取名 `anju-zhiping`。
3. **部署服务**：
   - 方式 A（Git 自动部署）：Service → New Service → Git Repository → 选择本项目仓库 → 主分支。
     Zeabur 会自动识别根目录的 `zeabur.json`，按 Dockerfile 构建。
   - 方式 B（镜像部署）：先在本地 `docker build` 后 `docker push` 到 Docker Hub / GHCR，再 New Service → Image。
4. **配置环境变量**：服务详情 → Variables → 添加：
   - `DASHSCOPE_API_KEY` = 你的百炼 Key（必填）
   - `CORS_ORIGINS` 留空（同源部署）
   - 其余按需
5. **开放端口**：Networking → 添加暴露端口 `8000`，绑定域名（Zeabur 提供 `*.zeabur.app` 免费域名，也可绑自定义域名）。
6. **健康检查**：Zeabur 自动按 `zeabur.json` 中的 `healthCheckPath: /health` 探测。
7. **验证**：浏览器打开 `https://<你的域名>/`，看到首页即部署成功；访问 `/health` 返回 `{"status":"ok"}`。

### 4.2 Railway

1. **注册账号**：访问 [https://railway.app](https://railway.app)，用 GitHub 登录。
2. **新建项目**：New Project → Deploy from GitHub repo → 选择本项目仓库。
3. **配置服务**：
   - Railway 会自动识别根目录 `Dockerfile` 并按其构建。
   - Settings → Build → Builder 选 `Dockerfile`。
   - Settings → Deploy → Start Command 默认用 Dockerfile 的 `CMD`，无需改。
4. **配置环境变量**：Variables → 添加 `DASHSCOPE_API_KEY`（必填）等。
5. **配置健康检查**：Settings → Healthcheck → Path 填 `/health`，Timeout 30s。
6. **生成域名**：Settings → Networking → Generate Domain，得到 `*.up.railway.app` 域名。
7. **验证**：访问 `https://<生成的域名>/health`。

> Railway 免费额度有限，长时间不访问会休眠，首次唤醒需 30s 左右。

### 4.3 Render（备选，海外）

1. **注册账号**：访问 [https://render.com](https://render.com)，用 GitHub 登录。
2. **新建 Blueprint**：New + → Blueprint → 选择本项目仓库。Render 会自动识别根目录 `render.yaml`。
3. **确认服务**：Blueprint 自动创建一个名为 `anju-zhiping` 的 web service（Docker runtime）。
4. **填入 Secret**：在服务页面的 Environment 中，把 `DASHSCOPE_API_KEY` 的值填上（`sync: false` 的变量需手动填）。
5. **触发部署**：Save → 自动构建部署。构建过程约 5-8 分钟（npm ci + pip install）。
6. **健康检查**：Render 自动按 `render.yaml` 中 `healthCheckPath: /health` 探测。
7. **域名**：Settings → 拿到默认 `https://anju-zhiping.onrender.com`，可绑自定义域名。
8. **验证**：访问 `https://anju-zhiping.onrender.com/health`。

> Render 免费层 Web Service 750 小时/月，15 分钟无访问会休眠。

---

## 5. 部署后验证清单

| 检查项 | 方法 | 期望结果 |
|--------|------|----------|
| 健康检查 | `GET /health` | `{"status":"ok"}`，HTTP 200 |
| 前端首页 | `GET /` | 返回 HTML，含 `<div id="root">` |
| 前端静态资源 | `GET /assets/index-*.js` | HTTP 200，`Content-Type: application/javascript` |
| SPA 路由兜底 | `GET /result/xxx` | 返回首页 HTML（不是 404） |
| API 评测 | `POST /api/evaluate` (voice_text) | 返回评测 JSON |
| 上传评测 | `POST /api/evaluate/upload` (图片) | 返回评测 JSON |
| 批量评测 | `POST /api/batch-evaluate` | 返回 `{results, total, success, failed}` |
| 报告查询 | `GET /api/report/{request_id}` | 返回报告 JSON |
| PDF 导出 | `GET /api/report/{request_id}/pdf` | HTTP 200，`Content-Type: application/pdf` |
| 百炼连通性 | 上传一张真实化学品图片 | 识别结果非空，无 5xx 错误 |

---

## 6. 备选方案：前后端分离部署

如需前端走 CDN 加速（独立静态站点），后端单独部署为 API 服务：

1. 前端：在 `frontend/` 跑 `npm run build`，把 `dist/` 上传到 CDN（Vercel / Netlify / Cloudflare Pages / 阿里云 OSS+CDN）。
   - 配置 SPA fallback：所有未命中静态文件的路径返回 `index.html`。
   - 配置 API 反向代理：`/api/*` 转发到后端域名（参考 `render.yaml` 中注释掉的 static service 段）。
2. 后端：用同一 Dockerfile，但前端 `dist/` 可以不打进镜像（修改 Dockerfile 删除 `COPY --from=frontend-build` 一行）。
3. 必须设置 `CORS_ORIGINS=https://你的前端域名`，否则浏览器跨域被拦。

> 公益场景内网部署时建议保持「同源合并部署」（默认方案），运维更简单。

---

## 7. 常见问题

### Q1：PDF 导出中文乱码或报错？
Docker 镜像已安装 `fonts-wqy-zenhei` 字体兜底。如在 Windows 本地直接跑（非容器），后端会优先使用 `C:\Windows\Fonts\simhei.ttf`。其他系统若无可中文字体，PDF 会自动降级为英文字段。

### Q2：百炼 API 报 401 / Invalid API Key？
检查 `DASHSCOPE_API_KEY` 是否填对，是否开通了百炼服务并申请了 Qwen3 / Qwen-VL 模型权限。赛事 Token 补贴需在 [百炼控制台](https://bailian.console.aliyun.com/) 领取。

### Q3：容器启动后立即退出？
查看 `docker logs <容器名>`。常见原因：
- 端口被占用：改 `-p` 映射。
- 环境变量缺失：`DASHSCOPE_API_KEY` 没填。
- 知识库加载失败：检查 `knowledge_base/msds_data.json` 是否被打入镜像（应被 `COPY knowledge_base/`）。

### Q4：上传图片评测返回 500？
`/api/evaluate/upload` 流程中，Qwen-VL 会通过 HTTP 回拉 `https://<你的域名>/uploads/<file>`。若部署在反向代理后且未透传 `Host` 头，可能导致生成的 URL 不可访问。排查：检查 `request.base_url` 是否正确。

### Q5：SPA 刷新子路由 404？
确认 `backend/main.py` 中的 `spa_fallback` 路由已生效（static 目录存在时才会注册）。访问 `GET /result/xxx` 应返回 `index.html` 而非 404。

---

## 8. 回滚

各平台均支持「Rollback to previous deploy」：
- Zeabur：Deployments → 选择历史版本 → Redeploy
- Railway：Settings → Rollback
- Render：Manual Deploy → Deploy from commit → 选历史 commit

---

如需对接公益机构（壹基金/社区/学校），请参考 [PARTNER_API.md](./PARTNER_API.md)。
