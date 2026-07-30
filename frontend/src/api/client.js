// axios 实例 + 各后端 API 封装
// 所有请求通过 Vite 代理 /api 转发到后端 http://localhost:8000
import axios from 'axios'

// 统一 axios 实例：超时 60s（评测链路较长，含多 Agent 调用）
const client = axios.create({
  baseURL: '/api',
  timeout: 60_000,
})

// 统一拦截：把后端错误信息规范化抛出
client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail =
      error?.response?.data?.detail || error?.response?.data?.message
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(error)
  },
)

/**
 * 统一评测入口（语音/文本/图片 URL 任选其一）
 * POST /api/evaluate
 */
export async function evaluate({ imageUrl, voiceText, familyProfile, emergencyType } = {}) {
  const res = await client.post('/evaluate', {
    image_url: imageUrl,
    voice_text: voiceText,
    family_profile: familyProfile,
    emergency_type: emergencyType,
  })
  return res.data
}

/**
 * 上传图片文件并评测
 * POST /api/evaluate/upload  multipart/form-data  字段名 file
 */
export async function evaluateUpload(file, { familyProfile, emergencyType } = {}) {
  const form = new FormData()
  form.append('file', file)
  // family_profile / emergency_type 通过 FormData 一并提交（后端当前只取 file，
  // 这里附带不影响调用；如后端扩展接收即可生效）
  const res = await client.post('/evaluate/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: {
      family_profile: familyProfile ? JSON.stringify(familyProfile) : undefined,
      emergency_type: emergencyType,
    },
  })
  return res.data
}

/**
 * 语音/文本评测入口（语义等价 /api/evaluate 的语音分支）
 * POST /api/voice
 */
export async function evaluateVoice({ voiceText, familyProfile, emergencyType } = {}) {
  const res = await client.post('/voice', {
    voice_text: voiceText,
    family_profile: familyProfile,
    emergency_type: emergencyType,
  })
  return res.data
}

/**
 * 批量评测（公益机构对接）
 * POST /api/batch-evaluate  body: { items: [{image_url?, voice_text?, family_profile?}] }
 */
export async function batchEvaluate(items) {
  const res = await client.post('/batch-evaluate', { items })
  return res.data
}

/**
 * 查询评测报告 JSON
 * GET /api/report/{request_id}
 */
export async function getReport(requestId) {
  const res = await client.get(`/report/${requestId}`)
  return res.data
}

/**
 * 导出报告 PDF（返回完整 URL，调用方自行新窗口打开）
 * GET /api/report/{request_id}/pdf
 */
export function getReportPdfUrl(requestId) {
  return `/api/report/${requestId}/pdf`
}

export default client
