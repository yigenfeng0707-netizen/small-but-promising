# 安居智评 Agent

> 家庭化学品安全智能评测 Agent —— 2026「小有可为」参赛项目

## 项目简介

「安居智评 Agent」面向家庭场景，通过拍照/上传/语音输入 household 化学品（清洁剂、消毒剂、农药、药品等），基于百炼 Qwen3 + Qwen-VL 多模态大模型与 6 个协同 Agent，完成识别 → 成分解析 → 风险评测 → 家庭画像匹配 → 场景建议（含绿色替代品）→ 应急指导的全流程评测，输出可分享的公益科普卡片与 PDF 报告，并支持一键呼救。

项目面向社区与公益机构（如壹基金）落地，提升家庭化学品安全意识，降低误服、误触、泄漏等事故风险。

## 技术栈

- **后端**：FastAPI + Uvicorn + SQLAlchemy + Redis，接入阿里云百炼（DashScope）Qwen3 文本模型与 Qwen-VL 多模态模型
- **前端**：React + Vite + axios + react-router-dom
- **知识库**：MSDS 数据 + 向量检索（FAISS / 百炼知识库服务）
- **导出**：fpdf2 生成 PDF 评测报告

## 目录结构

```
small_but_promising/
├── backend/              # FastAPI 后端
│   ├── main.py           # 应用入口 + 健康检查
│   ├── config.py         # pydantic-settings 配置
│   ├── requirements.txt  # Python 依赖
│   └── .env.example      # 环境变量示例
├── frontend/             # React + Vite 前端
├── knowledge_base/       # MSDS 知识库与 RAG 检索
├── docs/                 # 项目文档与对接材料
└── .trae/specs/          # 规格与任务清单
```

## 快速开始

### 1. 后端

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env        # 按需填入 DASHSCOPE_API_KEY
python -m uvicorn main:app --reload --port 8000
```

健康检查：

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 Vite 提示的本地地址（默认 http://localhost:5173 ），首页点击「测试 /api/health」按钮可验证前后端连通（Vite 已将 `/api/*` 代理到 `http://localhost:8000`）。

## 开发计划

详见 `.trae/specs/init-home-chem-safety-agent/tasks.md`，按 Task 1 ~ Task 9 推进，初赛材料需在 8.13 前提交。

## 部署

项目支持多种部署方式，按需选用：

- **魔搭创空间（推荐，免费 CPU + 稳定 URL）**：详见 [docs/DEPLOY_MODELSCOPE.md](docs/DEPLOY_MODELSCOPE.md)
  - 配置文件 `ms_deploy.json`（Docker SDK + port 7860 + 免费资源）
  - 自动持久化到 `/mnt/workspace`（评测图片/报告重启不丢）
  - 环境变量在创空间设置页配置 `DASHSCOPE_API_KEY`
- **Zeabur / Railway / Render**：备好 `Dockerfile` + `zeabur.json` + `render.yaml`，详见 [docs/DEPLOY.md](docs/DEPLOY.md)
