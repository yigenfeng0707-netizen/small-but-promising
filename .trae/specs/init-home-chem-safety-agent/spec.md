# 安居智评 Agent Spec

## Why

2026「小有可为」AI 向善创新挑战赛·绿色发展赛道要求"构建家庭化学品安全评测 Agent"。我国家庭化学品（清洁剂、消毒剂、农药、药品）中毒事件高发，儿童误服占相当比例，农村/独居老人风险更高。市面缺乏"拍一下就知道安不安全"的轻量工具。本项目以多 Agent 架构串联识别→评测→防护→应急全链路，紧扣公益价值、技术可行性、用户友好度、创新价值四维评审，目标 8.13 前交付初赛材料并晋级决赛。

## What Changes

- 新建项目骨架：FastAPI 后端 + React 前端 + 百炼 Qwen3/Qwen-VL 接入
- 实现 6 Agent 协作架构：识别/成分解析/风险评测/家庭画像/场景建议/应急指导
- 构建 MSDS 化学品安全知识库（RAG）
- 实现多模态输入（拍照 + 语音 + 文本），照顾低识字人群
- 提供绿色替代品推荐（呼应绿色发展主题）
- 预留公益机构对接接口（壹基金/社区/学校）
- **BREAKING**：无（全新项目，首版）

## Impact

- Affected specs: 无（项目首版 spec）
- Affected code: 全新代码库
  - `backend/` FastAPI + Agent 编排
  - `frontend/` React + Vite
  - `knowledge_base/` MSDS 数据 + RAG 索引
  - `docs/` 初赛材料（PPT/文档/Demo 视频）

## ADDED Requirements

### Requirement: 多 Agent 协作架构

系统 SHALL 提供 6 个专职 Agent 协作完成家庭化学品安全评测，每个 Agent 职责单一、可独立调用，由编排层串联。

#### Scenario: 用户拍照评测一瓶洁厕剂

- **WHEN** 用户上传洁厕剂包装照片 + 选择"家中含 5 岁儿童"
- **THEN** 识别 Agent 识别包装 → 成分解析 Agent 解析盐酸/表面活性剂 → 风险评测 Agent 评估强腐蚀/儿童误服高风险 → 家庭画像 Agent 结合儿童给出针对性风险 → 场景建议 Agent 给存储+防护+绿色替代品 → 应急指导 Agent 给误服处置（勿催吐、饮牛奶、就医）

### Requirement: 多模态输入

系统 SHALL 支持拍照（图片）、语音、文本三种输入方式，照顾低识字/老年/视障人群。

#### Scenario: 老人语音提问

- **WHEN** 老人对着麦克风说"84 消毒液和洁厕灵能混用吗"
- **THEN** 系统识别语音意图 → 风险评测 Agent 检测混合产生氯气剧毒 → 应急指导 Agent 警告禁止混用并给出通风+就医方案

### Requirement: MSDS 知识库与 RAG

系统 SHALL 内置 MSDS（化学品安全技术说明书）+ 国标 GB 数据，通过 RAG 提升成分解析与风险评测的准确性，避免纯大模型幻觉。

#### Scenario: 识别出"对氯苯二甲酸"

- **THEN** 成分解析 Agent 查 RAG 知识库匹配毒性数据 → 风险评测 Agent 基于真实数据评估而非臆测

### Requirement: 绿色替代品推荐

系统 SHALL 在场景建议中推荐绿色低毒替代品（如小苏打+白醋替代强碱清洁剂），呼应绿色发展主题，作为差异化卖点。

#### Scenario: 评测出强碱管道疏通剂高风险

- **THEN** 场景建议 Agent 推荐小苏打+热水+白醋的物理疏通法

### Requirement: 家庭画像个性化

系统 SHALL 根据家庭成员画像（儿童/老人/孕妇/宠物/慢性病）给出差异化风险与建议。

#### Scenario: 同样一瓶杀虫剂

- **WHEN** 家庭画像含婴儿
- **THEN** 风险等级上调为"极高"，建议婴儿回避 24 小时
- **WHEN** 家庭画像仅成年人
- **THEN** 风险等级"中"，建议使用时通风+戴口罩

### Requirement: 应急指导与一键呼救

系统 SHALL 在检测到高危场景时优先返回应急指导，并提供一键拨打 120/中毒咨询热线（010-83132345）入口。

#### Scenario: 用户报告儿童误服洁厕剂

- **THEN** 应急指导 Agent 立即返回：勿催吐、口服牛奶/蛋清保护胃黏膜、立即就医，并高亮 120 呼叫按钮

### Requirement: 公益机构对接接口

系统 SHALL 预留与壹基金/社区/学校对接的接口（数据导出、科普卡片生成、批量评测 API），满足赛事"真实落地非 Demo"要求。

#### Scenario: 社区批量评测

- **WHEN** 社区调 POST /api/batch-evaluate 上传 50 张家庭化学品照片
- **THEN** 系统批量返回评测报告，可导出 PDF 用于社区安全普查

### Requirement: 百炼千问模型接入

系统 SHALL 使用阿里云百炼 Qwen3（文本推理）+ Qwen-VL（多模态识别）作为核心模型，符合赛事要求并使用 Token 补贴。

#### Scenario: 调用 Qwen-VL 识别包装

- **THEN** 调用百炼 Qwen-VL API 传入图片 → 返回化学品名称/品牌/成分表识别结果

## MODIFIED Requirements

无（首版）

## REMOVED Requirements

无（首版）
