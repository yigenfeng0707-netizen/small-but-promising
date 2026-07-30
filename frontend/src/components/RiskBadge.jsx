// 风险等级徽章：低=绿 / 中=黄 / 高=橙 / 极高=红
function RiskBadge({ level, label }) {
  const text = label || level || '未知'
  let cls = 'risk-badge '
  const lv = String(level || '').trim()
  if (lv === '低' || lv.toLowerCase() === 'low') cls += 'lvl-low'
  else if (lv === '中' || lv.toLowerCase() === 'medium') cls += 'lvl-mid'
  else if (lv === '高' || lv.toLowerCase() === 'high') cls += 'lvl-high'
  else if (lv === '极高' || lv.toLowerCase() === 'critical') cls += 'lvl-critical'
  else cls += 'lvl-unknown'

  return <span className={cls}>{text}</span>
}

export default RiskBadge
