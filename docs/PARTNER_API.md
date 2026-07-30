# 安居智评 Agent · 公益机构对接文档

面向 **壹基金 / 社区 / 学校** 等公益机构的技术对接说明。任何能发 HTTP 请求的
语言（Python / Java / Shell curl / 浏览器 JS）都能接入，无需安装专用 SDK。

> 文档版本：v1.0（Task 8）
> 适用场景：社区安全普查、学校科普、独居老人关怀、应急知识宣传等公益用途。

---

## 1. 项目简介

**安居智评 Agent** 是一款面向家庭化学品安全的智能评测工具。我国家庭化学品（清洁
剂、消毒剂、农药、药品）中毒事件高发，儿童误服占相当比例，农村/独居老人风险更高；
市面缺乏"拍一下就知道安不安全"的轻量工具。

本项目以多 Agent 架构串联 **识别 → 成分解析 → 风险评测 → 家庭画像 → 场景建议 →
应急指导** 全链路，用户只需拍照或语音描述家中化学品，即可获得：

- 该化学品的 **5 维风险评分**（毒性/易燃/腐蚀/致敏/环境）
- 结合 **家庭成员画像**（儿童/老人/孕妇/宠物/慢性病）的个性化风险等级
- **存储与防护建议** + **绿色低毒替代品**（呼应绿色发展）
- 误服/误触/泄漏的 **应急指导** + 一键拨打 120/中毒咨询热线

公益机构可用本系统做 **社区安全普查、学校科普、独居老人关怀**，无需自研模型与知
识库，按本文档调用 API 即可。

---

## 2. 接入方式

| 项 | 说明 |
|----|------|
| 协议 | HTTP/HTTPS |
| 数据格式 | JSON（请求体 `application/json`；文件上传 `multipart/form-data`） |
| 编码 | UTF-8 |
| 是否需要 SDK | **不需要**。任何能发 HTTP 请求的语言均可（Python `requests` / Java `HttpClient` / Node `axios` / 浏览器 `fetch` / `curl`） |
| 调用模式 | 同步（评测类接口在请求返回时即带结果；批量评测会等所有子项完成） |

### 2.1 Base URL

部署后服务地址，例如：

- 内网部署：`http://10.0.0.5:8000`
- 云端部署：`https://anju-zhiping.zeabur.app`（示例）

下文示例中统一写作 `{{BASE_URL}}`，对接方按实际地址替换。

### 2.2 健康检查

```bash
curl {{BASE_URL}}/health
# {"status":"ok"}
```

---

## 3. 认证

**当前版本：无认证**（公益场景默认内网部署，假定网络层已隔离）。

后续如需公网部署或多机构隔离，可扩展为 **API Key** 模式：

```
GET /api/evaluate
Header: X-API-Key: <由我方分配的 key>
```

届时本文档会同步更新。当前对接方可直接调用，无需任何 Header。

---

## 4. 核心 API 列表

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/evaluate` | 单次评测（图片 URL / 语音文本 / 应急类型组合） |
| POST | `/api/evaluate/upload` | 直接上传图片文件评测（无需先传图床） |
| POST | `/api/voice` | 语音/文本语义评测（等价 `/api/evaluate` 的语音分支） |
| POST | `/api/batch-evaluate` | 批量评测（公益机构主用） |
| GET  | `/api/report/{request_id}` | 查询某次评测报告 JSON |
| GET  | `/api/report/{request_id}/pdf` | 导出评测报告 PDF |
| DELETE | `/api/report/{request_id}` | 删除报告（按需） |

### 4.1 POST `/api/evaluate` 单次评测

**请求体**（JSON）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `image_url` | string | 否* | 待识别图片的可访问 URL（http/https）。`image_url` 与 `voice_text` 至少传一个 |
| `voice_text` | string | 否* | 语音转写后的文字，或用户直接输入的文本（如"84 消毒液和洁厕灵能混用吗"） |
| `family_profile` | object | 否 | 家庭成员画像，影响风险等级调整 |
| `emergency_type` | string | 否 | 应急类型：`误服` / `误触` / `泄漏` 等，触发应急指导 Agent |

`family_profile` 结构示例：

```json
{
  "members": [
    {"role": "child", "age": 5},
    {"role": "elderly", "age": 72, "chronic_disease": ["高血压"]},
    {"role": "adult", "age": 35},
    {"role": "pet", "species": "cat"}
  ],
  "pregnant": false
}
```

**curl 示例**：

```bash
# 语音/文本评测
curl -X POST {{BASE_URL}}/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "voice_text": "84消毒液和洁厕灵能混用吗",
    "family_profile": {"members": [{"role": "child", "age": 5}]}
  }'

# 图片 URL 评测
curl -X POST {{BASE_URL}}/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/toilet_cleaner.jpg",
    "family_profile": {"members": [{"role": "elderly", "age": 75}]}
  }'
```

**响应体**（关键字段）：

```json
{
  "request_id": "a1b2c3d4e5f6...",
  "mode": "image",
  "recognition": {
    "chemical_name": "盐酸洁厕剂",
    "brand": "某某品牌",
    "category": "洁厕剂",
    "ingredients_text": "盐酸、表面活性剂..."
  },
  "risk": {
    "overall_level": "高",
    "scores": {
      "toxicity": 4,
      "flammability": 1,
      "corrosivity": 5,
      "allergy": 3,
      "environment": 3
    },
    "key_risks": ["强腐蚀", "儿童误服高风险"],
    "interactions": ["与84消毒液混合产生剧毒氯气"]
  },
  "family_adjustment": {
    "adjusted_level": "极高",
    "adjustment_reasons": ["家中有5岁儿童"],
    "specific_warnings": ["必须放在儿童无法触及处"]
  },
  "scenario_advice": {
    "storage": ["阴凉通风处，远离儿童"],
    "protection": ["戴橡胶手套使用"],
    "green_alternatives": [
      {"original": "强酸洁厕剂", "alternatives": ["小苏打+白醋"]}
    ]
  },
  "emergency_guide": {
    "immediate_actions": ["误服：勿催吐，口服牛奶/蛋清保护胃黏膜，立即就医"],
    "do_not": ["禁止催吐", "禁止与84混用"],
    "seek_medical_help": true,
    "hotlines": ["120", "010-83132345"]
  },
  "summary": "本品为强腐蚀性洁厕剂，家中含5岁儿童，风险极高……",
  "partial": false
}
```

> `partial: true` 表示有 Agent 降级，结果中对应字段可能为空，可继续展示但需提示用户。

### 4.2 POST `/api/evaluate/upload` 上传图片评测

适合公益机构工作人员用手机/平板直接拍照上传，无需先传图床获取 URL。

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `file` | file | 是 | 图片文件，单文件，大小上限 10MB。支持 jpg/png/webp 等 |

> 该接口内部会自动把图片保存到服务端 `/uploads/`，并生成可访问 URL 供 Qwen-VL 拉取识别。

**curl 示例**：

```bash
curl -X POST {{BASE_URL}}/api/evaluate/upload \
  -F "file=@/path/to/toilet_cleaner.jpg"
```

**响应体**：同 4.1。

### 4.3 POST `/api/batch-evaluate` 批量评测

**公益机构主用接口**。一次性提交多个评测项，服务端并发执行（信号量限流 5 并发，
避免压垮百炼 API），单条失败不影响整批。

**请求体**（JSON）：

```json
{
  "items": [
    {
      "image_url": "https://example.com/photo1.jpg",
      "family_profile": {"members": [{"role": "child", "age": 5}]}
    },
    {
      "voice_text": "84消毒液和洁厕灵能混用吗"
    },
    {
      "image_url": "https://example.com/photo3.jpg"
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `items` | array | 是 | 评测项列表，每项字段同 4.1 中的 `image_url` / `voice_text` / `family_profile` |

**curl 示例**：

```bash
curl -X POST {{BASE_URL}}/api/batch-evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"image_url": "https://example.com/photo1.jpg"},
      {"voice_text": "我家有杀虫剂，孕妇能用吗"}
    ]
  }'
```

**响应体**：

```json
{
  "results": [
    { /* 评测结果 1，结构同 4.1 响应 */ },
    { /* 评测结果 2 */ }
  ],
  "total": 2,
  "success": 2,
  "failed": 0
}
```

> 失败项会带 `"partial": true` 与 `"error"` 字段；`success` 计数不含这些。

### 4.4 GET `/api/report/{request_id}` 查询报告

每次评测返回的 `request_id` 都会自动落地为 JSON 报告，便于后续查询。

```bash
curl {{BASE_URL}}/api/report/a1b2c3d4e5f6...
```

**响应体**：同 4.1 响应。报告不存在返回 404。

### 4.5 GET `/api/report/{request_id}/pdf` 导出 PDF

导出排版好的 PDF 报告，含化学品名/风险等级/5 维评分/家庭建议/应急指导/绿色替代品，
适合打印分发或归档到社区安全普查档案。

```bash
# 下载到本地
curl -o report.pdf {{BASE_URL}}/api/report/a1b2c3d4e5f6.../pdf

# 浏览器直接打开预览
# 访问 https://{{BASE_URL}}/api/report/{id}/pdf
```

**响应**：`Content-Type: application/pdf`，`Content-Disposition: inline; filename="report_{id}.pdf"`。

> PDF 中文字体在 Docker 镜像内已预装 `fonts-wqy-zenhei`；Windows 本地部署使用 `simhei.ttf`。

---

## 5. 典型场景用例

### 场景 A：社区安全普查（最常用）

**痛点**：社区需对辖区家庭做安全普查，传统方式人工逐户登记，效率低、专业度不足。

**对接流程**：

1. 社区工作者入户，用手机对每户家庭的化学品拍照（每户 5~10 张）。
2. 社区后台批量调 `/api/batch-evaluate`，把所有图片 URL 提交。
3. 系统返回每张图片的评测报告 + `request_id`。
4. 社区后台按户归档：调 `/api/report/{id}/pdf` 导出 PDF，与户主信息绑定。
5. 普查结束后，按 `risk.overall_level` 筛查"极高/高"风险家庭，针对性回访。

**Python 示例**：

```python
import requests

BASE = "https://anju-zhiping.zeabur.app"

# 1. 批量评测
resp = requests.post(f"{BASE}/api/batch-evaluate", json={
    "items": [
        {"image_url": "https://cdn.community.org/home1_01.jpg",
         "family_profile": {"members": [{"role": "child", "age": 3}]}},
        {"image_url": "https://cdn.community.org/home1_02.jpg"},
        {"image_url": "https://cdn.community.org/home2_01.jpg"},
    ]
}, timeout=300)
data = resp.json()
print(f"成功 {data['success']}/{data['total']} 条")

# 2. 导出每份 PDF
for item in data["results"]:
    rid = item["request_id"]
    pdf = requests.get(f"{BASE}/api/report/{rid}/pdf")
    with open(f"report_{rid}.pdf", "wb") as f:
        f.write(pdf.content)

# 3. 筛查高风险
high_risk = [r for r in data["results"]
             if (r.get("family_adjustment", {}).get("adjusted_level")
                 or r.get("risk", {}).get("overall_level")) in ("极高", "高")]
print(f"需回访家庭数：{len(high_risk)}")
```

### 场景 B：学校科普卡片生成

**痛点**：学校化学安全课需要素材，教师没精力逐个查 MSDS。

**对接流程**：

1. 教师在后台选一组常见家庭化学品（如 84 消毒液、洁厕灵、杀虫剂、酒精、管道疏通剂）。
2. 用 `voice_text` 模式调 `/api/evaluate`，传化学品名。
3. 系统返回风险评测 + **绿色替代品**。
4. 教师把 `scenario_advice.green_alternatives` 字段做成科普卡片，印发给学生家长。

**curl 示例**：

```bash
curl -X POST {{BASE_URL}}/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"voice_text": "84消毒液"}'
```

返回中包含：

```json
"scenario_advice": {
  "green_alternatives": [
    {"original": "84消毒液（强氧化）", "alternatives": ["阳光暴晒", "煮沸消毒"]}
  ]
}
```

### 场景 C：独居老人入户评估

**痛点**：社区工作者每月入户关怀独居老人，老人不识字，化学品存放混乱风险高。

**对接流程**：

1. 工作者入户，对老人卫生间/厨房化学品拍照。
2. 用 `/api/evaluate/upload` 直接上传图片，附 `family_profile` 标注"独居老人"。
3. 系统返回风险等级与 **存储建议**（如"勿放床头"、"通风处保存"）。
4. 工作者按 `emergency_guide.hotlines` 把急救热线贴在老人家中显眼处。
5. 如评测出"极高"风险（如发现 84 + 洁厕灵同时存放），按 `emergency_guide.immediate_actions`
   立即处置。

**curl 示例**：

```bash
curl -X POST {{BASE_URL}}/api/evaluate/upload \
  -F "file=@elder_home_cleaner.jpg"
```

> 老人也可通过前端页面的"语音"按钮直接说话提问（前端 Web Speech API 转写后调 `/api/voice`），
> 无需识字。

---

## 6. 数据隐私

本系统**不上传、不存储任何用户身份信息**。请公益机构在对接时遵循以下原则：

| 类别 | 是否收集 | 说明 |
|------|----------|------|
| 姓名 / 身份证 / 手机号 | **否** | 系统不需要，请勿在 `family_profile` 中传 |
| 家庭住址 | **否** | 同上 |
| 图片 | 是（匿名） | 仅化学品包装/场景照片，用于识别。**请勿拍人脸、家门牌号、私人证件** |
| 语音转写文本 | 是（匿名） | 仅化学品相关问题，不含个人信息 |
| 家庭画像 | 是（匿名） | 仅"儿童/老人/孕妇/宠物/慢性病"等角色描述，不含身份信息 |
| 评测报告 | 是（按 request_id） | 落地到服务端 `storage/reports/{request_id}.json`，可按需 DELETE |

**报告数据保留**：默认长期保留（用于普查归档）。如需删除某份报告，调
`DELETE /api/report/{request_id}`。如需全量清理，联系部署方清空 `storage/reports/` 目录。

**数据传输**：内网部署走 HTTP 即可；公网部署务必启用 HTTPS（云平台默认提供）。

**合规建议**：普查场景下，建议公益机构在入户前征得户主同意，并明确告知"仅拍摄化学品，
不拍摄人脸与证件"。

---

## 7. 错误码

| HTTP 状态码 | 含义 | 处理建议 |
|-------------|------|----------|
| 200 | 成功 | — |
| 400 | 请求参数错误 | 检查 `image_url` 与 `voice_text` 是否至少传一个 |
| 404 | 报告不存在 | `request_id` 错误或报告已被删除 |
| 413 | 上传文件过大 | `/api/evaluate/upload` 单文件上限 10MB，请压缩或分批 |
| 422 | JSON 格式错误 | 检查请求体 JSON 语法 |
| 500 | 服务端错误 | 查看响应 `detail`；可能是百炼 API 异常或图片 URL 不可访问 |
| 502/504 | 上游超时 | 百炼 API 偶发慢，重试 1~2 次 |

> 评测类接口响应时间：纯文本约 5~10s，图片约 10~20s，批量取决于条数（并发 5）。

---

## 8. 限流与配额

- 单实例默认无限流（公益场景假定内部使用）。
- 批量评测内置信号量限流 5 并发，避免压垮百炼 API。
- 百炼 API Token 配额由赛事补贴 + 公益机构账号决定，超额会返回 5xx，重试即可。

如需多机构共享一套部署并按机构限流，联系我方在网关层加配额。

---

## 9. 联系方式

| 项 | 内容 |
|----|------|
| 项目方 | （待填，例如：XX 大学 XX 实验室 / 项目组名称） |
| 对接负责人 | （待填） |
| 邮箱 | （待填） |
| 电话 | （待填） |
| 微信 / 飞书 | （待填） |
| 项目仓库 | （待填，如 https://github.com/your-org/anju-zhiping） |
| 在线 Demo | （待填，部署后填入 {{BASE_URL}}） |
| Issue 反馈 | （待填，建议用 GitHub Issue） |

> 以上信息将在公益机构对接前由项目方填写完整。

---

## 10. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-29 | 首版：5 个核心 API + 3 个典型场景 + 隐私规范 |
