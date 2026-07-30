// 评测结果页：顶部识别摘要 + 总体风险徽章 + 6 个 Agent 输出分块 + 应急横幅 + 导出 PDF
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  ScanLine,
  FlaskConical,
  AlertTriangle,
  Users,
  Lightbulb,
  Siren,
  Loader2,
  FileDown,
  RotateCcw,
  PhoneCall,
  Leaf,
} from 'lucide-react'
import { getReport } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import AgentCard from '../components/AgentCard'
import EmergencyButton from '../components/EmergencyButton'

// 5 维评分展示配置（key → 中文标签 + 颜色）
const SCORE_DIMS = [
  { key: 'toxicity', label: '毒性', color: '#dc2626' },
  { key: 'flammability', label: '易燃性', color: '#ea580c' },
  { key: 'corrosivity', label: '腐蚀性', color: '#d97706' },
  { key: 'allergy', label: '致敏性', color: '#7c3aed' },
  { key: 'environment', label: '环境影响', color: '#0891b2' },
]

function ScoreBars({ scores }) {
  const data = scores || {}
  return (
    <div className="score-bars">
      {SCORE_DIMS.map((d) => {
        const v = Number(data[d.key]) || 0
        return (
          <div className="score-row" key={d.key}>
            <span className="score-label">{d.label}</span>
            <div className="score-track">
              <div
                className="score-fill"
                style={{ width: `${Math.min(100, Math.max(0, v))}%`, background: d.color }}
              />
            </div>
            <span className="score-value">{v}</span>
          </div>
        )
      })}
    </div>
  )
}

function ResultPage() {
  const navigate = useNavigate()
  const location = useLocation()
  // 优先用跳转时传入的 state.result；若没有（如直接刷新），从 URL 取 request_id 重新拉取
  const passedResult = location.state?.result
  const requestIdFromQuery = new URLSearchParams(location.search).get('id')

  const [data, setData] = useState(passedResult || null)
  const [loading, setLoading] = useState(!passedResult && !!requestIdFromQuery)
  const [error, setError] = useState('')

  useEffect(() => {
    if (passedResult || !requestIdFromQuery) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const report = await getReport(requestIdFromQuery)
        if (!cancelled) setData(report)
      } catch (err) {
        if (!cancelled) setError(err.message || '加载报告失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [passedResult, requestIdFromQuery])

  // 派生数据：各分块（统一兜底为空结构，避免降级时崩溃）
  const view = useMemo(() => {
    const d = data || {}
    return {
      mode: d.mode || '未知',
      recognition: d.recognition || {},
      ingredients: d.ingredients || {},
      risk: d.risk || {},
      family_adjustment: d.family_adjustment || {},
      scenario_advice: d.scenario_advice || {},
      emergency_guide: d.emergency_guide || {},
      summary: d.summary || '',
      errors: d.errors || [],
      partial: !!d.partial,
      request_id: d.request_id || requestIdFromQuery || '',
    }
  }, [data, requestIdFromQuery])

  const seekMedical = view.emergency_guide.seek_medical_help === true
  const overallLevel = view.risk.overall_level
  const adjustedLevel = view.family_adjustment.adjusted_level

  if (loading) {
    return (
      <div className="result-loading">
        <Loader2 size={28} className="spin" />
        <p>正在加载评测报告…</p>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="result-error">
        <AlertTriangle size={28} />
        <p>{error}</p>
        <button className="submit-btn" onClick={() => navigate('/')}>
          返回首页
        </button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="result-error">
        <AlertTriangle size={28} />
        <p>未找到评测结果，请先发起一次评测。</p>
        <button className="submit-btn" onClick={() => navigate('/')}>
          返回首页评测
        </button>
      </div>
    )
  }

  return (
    <div className="result">
      {/* 顶部：识别摘要 + 总体风险 + 模式 */}
      <header className="result-header">
        <div className="result-recog">
          <h2>{view.recognition.chemical_name || '未识别到化学品'}</h2>
          <p className="result-meta">
            {view.recognition.brand && <span>品牌：{view.recognition.brand}　</span>}
            {view.recognition.category && <span>类别：{view.recognition.category}　</span>}
            <span>模式：{view.mode === 'photo' ? '拍照' : view.mode === 'voice' ? '语音/文本' : view.mode}</span>
          </p>
        </div>
        <div className="result-risk">
          <div className="risk-block">
            <span className="risk-block-label">原始风险</span>
            <RiskBadge level={overallLevel} />
          </div>
          {adjustedLevel && adjustedLevel !== overallLevel && (
            <div className="risk-block">
              <span className="risk-block-label">家庭调整后</span>
              <RiskBadge level={adjustedLevel} />
            </div>
          )}
        </div>
      </header>

      {/* 应急横幅：seek_medical_help=true 时显示 */}
      {seekMedical && (
        <div className="emergency-banner">
          <Siren size={22} />
          <div className="emergency-banner-text">
            <strong>建议立即就医！</strong>
            <span>检测到高危场景，请按下方应急指导处理并拨打急救电话。</span>
          </div>
          <EmergencyButton compact />
        </div>
      )}

      {/* 降级提示 */}
      {view.partial && (
        <div className="partial-banner">
          <AlertTriangle size={16} />
          本次评测有部分步骤降级（可能未配置百炼 API Key），结果已尽可能展示。
        </div>
      )}

      {/* 6 个 Agent 输出分块 */}
      <div className="agent-grid">
        {/* 1. 识别结果 */}
        <AgentCard title="识别结果" icon={<ScanLine size={18} />}>
          <ul className="kv-list">
            <li><span>化学品名</span><b>{view.recognition.chemical_name || '—'}</b></li>
            <li><span>品牌</span><b>{view.recognition.brand || '—'}</b></li>
            <li><span>类别</span><b>{view.recognition.category || '—'}</b></li>
            {view.recognition.ingredients_text && (
              <li><span>成分文本</span><b>{view.recognition.ingredients_text}</b></li>
            )}
          </ul>
        </AgentCard>

        {/* 2. 成分解析 */}
        <AgentCard title="成分解析" icon={<FlaskConical size={18} />}>
          <IngredientList ingredients={view.ingredients} />
        </AgentCard>

        {/* 3. 风险评测 */}
        <AgentCard title="风险评测" icon={<AlertTriangle size={18} />} accent={overallLevel}>
          <ScoreBars scores={view.risk.scores} />
          {view.risk.key_risks?.length > 0 && (
            <div className="tag-block">
              <span className="tag-block-title">主要风险</span>
              <div className="tag-wrap">
                {view.risk.key_risks.map((k, i) => (
                  <span className="tag tag-risk" key={i}>{k}</span>
                ))}
              </div>
            </div>
          )}
          {view.risk.interactions?.length > 0 && (
            <div className="tag-block">
              <span className="tag-block-title">相互作用</span>
              <div className="tag-wrap">
                {view.risk.interactions.map((k, i) => (
                  <span className="tag tag-interact" key={i}>{k}</span>
                ))}
              </div>
            </div>
          )}
        </AgentCard>

        {/* 4. 家庭画像调整 */}
        <AgentCard title="家庭画像调整" icon={<Users size={18} />}>
          {adjustedLevel ? (
            <div className="family-adjust">
              <div className="family-adjust-level">
                调整后等级：<RiskBadge level={adjustedLevel} />
              </div>
              {view.family_adjustment.adjustment_reasons?.length > 0 && (
                <div className="tag-block">
                  <span className="tag-block-title">调整原因</span>
                  <ul className="bullet-list">
                    {view.family_adjustment.adjustment_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {view.family_adjustment.specific_warnings?.length > 0 && (
                <div className="tag-block">
                  <span className="tag-block-title">针对性警告</span>
                  <ul className="bullet-list warn">
                    {view.family_adjustment.specific_warnings.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="empty-hint">未设置家庭画像或无需调整</p>
          )}
        </AgentCard>

        {/* 5. 场景建议（含绿色替代品高亮） */}
        <AgentCard title="场景建议" icon={<Lightbulb size={18} />}>
          <div className="scenario">
            {view.scenario_advice.storage?.length > 0 && (
              <div className="scenario-block">
                <span className="scenario-title">存储建议</span>
                <ul className="bullet-list">
                  {view.scenario_advice.storage.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            {view.scenario_advice.protection?.length > 0 && (
              <div className="scenario-block">
                <span className="scenario-title">防护建议</span>
                <ul className="bullet-list">
                  {view.scenario_advice.protection.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            {view.scenario_advice.green_alternatives?.length > 0 && (
              <div className="scenario-block green-block">
                <span className="scenario-title">
                  <Leaf size={14} /> 绿色替代品
                </span>
                <div className="green-list">
                  {view.scenario_advice.green_alternatives.map((g, i) => (
                    <div className="green-item" key={i}>
                      <div className="green-from">{g.original || '原品'} →</div>
                      <div className="green-to">
                        {(g.alternatives || []).map((a, j) => (
                          <span className="green-alt" key={j}>{a}</span>
                        ))}
                      </div>
                      {g.reason && <div className="green-reason">{g.reason}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </AgentCard>

        {/* 6. 应急指导 */}
        <AgentCard title="应急指导" icon={<Siren size={18} />} accent={seekMedical ? '极高' : undefined}>
          {view.emergency_guide.immediate_actions?.length > 0 && (
            <div className="emergency-block">
              <span className="emergency-label">立即行动</span>
              <ol className="num-list">
                {view.emergency_guide.immediate_actions.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </div>
          )}
          {view.emergency_guide.do_not?.length > 0 && (
            <div className="emergency-block">
              <span className="emergency-label danger">禁止事项</span>
              <ul className="bullet-list danger">
                {view.emergency_guide.do_not.map((s, i) => <li key={i}>⚠ {s}</li>)}
              </ul>
            </div>
          )}
          {view.emergency_guide.hotlines?.length > 0 && (
            <div className="emergency-block">
              <span className="emergency-label">急救热线</span>
              <div className="hotline-inline">
                {view.emergency_guide.hotlines.map((h, i) => (
                  <a key={i} className="hotline-chip" href={`tel:${h.number}`}>
                    <PhoneCall size={14} />
                    {h.name} {h.number}
                  </a>
                ))}
              </div>
            </div>
          )}
          {seekMedical && (
            <div className="emergency-cta">
              <EmergencyButton />
            </div>
          )}
        </AgentCard>
      </div>

      {/* 总结（markdown 渲染） */}
      {view.summary && (
        <AgentCard title="总结" icon={<Lightbulb size={18} />}>
          <div className="summary-markdown">
            <ReactMarkdown>{view.summary}</ReactMarkdown>
          </div>
        </AgentCard>
      )}

      {/* 底部操作 */}
      <div className="result-actions">
        <button
          className="action-btn primary"
          onClick={() => window.open(`/api/report/${view.request_id}/pdf`, '_blank')}
          disabled={!view.request_id}
        >
          <FileDown size={16} /> 导出 PDF 报告
        </button>
        <button className="action-btn" onClick={() => navigate('/')}>
          <RotateCcw size={16} /> 重新评测
        </button>
      </div>

      {view.errors?.length > 0 && (
        <details className="result-errors">
          <summary>调试信息（{view.errors.length} 条）</summary>
          <ul>
            {view.errors.map((e, i) => <li key={i}>{typeof e === 'string' ? e : JSON.stringify(e)}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}

// 成分列表子组件：展示成分名 + MSDS 匹配标记
function IngredientList({ ingredients }) {
  const list = ingredients?.ingredients || []
  const unmatched = ingredients?.unmatched_ingredients || []
  if (list.length === 0 && unmatched.length === 0) {
    return <p className="empty-hint">未解析到成分信息</p>
  }
  return (
    <div className="ingredient-list">
      {list.map((ing, i) => (
        <div className="ingredient-item" key={i}>
          <span className="ingredient-name">{ing.name}</span>
          {ing.matched ? (
            <span className="ingredient-match matched">✓ MSDS 匹配</span>
          ) : (
            <span className="ingredient-match unmatched">未匹配</span>
          )}
          {ing.msds?.hazard_level && (
            <span className="ingredient-hazard">危害：{ing.msds.hazard_level}</span>
          )}
        </div>
      ))}
      {unmatched.length > 0 && (
        <div className="ingredient-unmatched">
          <span>未匹配成分：</span>
          {unmatched.map((u, i) => (
            <span className="tag tag-unmatched" key={i}>{typeof u === 'string' ? u : u.name}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default ResultPage
