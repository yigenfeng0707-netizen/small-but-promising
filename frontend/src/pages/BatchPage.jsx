// 公益机构批量评测页：粘贴多条文本/图片 URL，并发评测，展示汇总结果
// 简单实现：文本逐行评测，结果列表可点击查看
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layers, Loader2, FileDown } from 'lucide-react'
import { batchEvaluate } from '../api/client'
import { useFamilyProfile, toBackendProfile } from '../context/FamilyProfileContext'
import RiskBadge from '../components/RiskBadge'

function BatchPage() {
  const navigate = useNavigate()
  const { profile } = useFamilyProfile()
  const familyProfile = toBackendProfile(profile)

  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null) // {results, total, success, failed}
  const [expanded, setExpanded] = useState(null)

  const handleRun = async () => {
    const lines = text
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length === 0) return

    setLoading(true)
    setError('')
    setSummary(null)
    try {
      // 每行作为一条 voice_text 评测项
      const items = lines.map((voiceText) => ({ voice_text: voiceText, family_profile: familyProfile }))
      const data = await batchEvaluate(items)
      setSummary(data)
    } catch (err) {
      setError(err.message || '批量评测失败，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="batch-page">
      <header className="page-title">
        <Layers size={22} />
        <h1>公益机构批量评测</h1>
      </header>
      <p className="page-desc">
        适合社区/学校/志愿者对一批家庭化学品做安全普查。每行输入一条化学品名称或疑问，并发评测后导出。
      </p>

      <textarea
        className="text-input batch-input"
        placeholder={'每行一条，例如：\n84 消毒液和洁厕灵能混用吗\n威猛先生洁厕灵\n强效管道疏通剂'}
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        disabled={loading}
      />

      <div className="form-actions">
        <button className="action-btn primary" onClick={handleRun} disabled={loading || !text.trim()}>
          {loading ? <Loader2 size={16} className="spin" /> : <Layers size={16} />}
          {loading ? '批量评测中…' : '开始批量评测'}
        </button>
      </div>

      {error && <div className="home-error">❌ {error}</div>}

      {summary && (
        <div className="batch-summary">
          <div className="batch-stat">
            <span className="stat-num">{summary.total}</span>
            <span className="stat-label">总数</span>
          </div>
          <div className="batch-stat ok">
            <span className="stat-num">{summary.success}</span>
            <span className="stat-label">成功</span>
          </div>
          <div className="batch-stat warn">
            <span className="stat-num">{summary.failed}</span>
            <span className="stat-label">降级/失败</span>
          </div>

          <div className="batch-list">
            {summary.results.map((r, i) => (
              <div className="batch-item" key={r.request_id || i}>
                <div className="batch-item-head" onClick={() => setExpanded(expanded === i ? null : i)}>
                  <span className="batch-item-title">
                    {r.recognition?.chemical_name || r.error || `第 ${i + 1} 条`}
                  </span>
                  {r.risk?.overall_level && <RiskBadge level={r.risk.overall_level} />}
                  {r.partial && <span className="tag tag-unmatched">降级</span>}
                </div>
                {expanded === i && (
                  <div className="batch-item-body">
                    <p>{r.summary || JSON.stringify(r)}</p>
                    {r.request_id && (
                      <button
                        className="action-btn small"
                        onClick={() => navigate('/result', { state: { result: r } })}
                      >
                        查看详情
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default BatchPage
