// 通用卡片：展示 Agent 输出（标题 + 内容区 + 可选图标）
function AgentCard({ title, icon, children, accent }) {
  return (
    <section className={`agent-card${accent ? ` accent-${accent}` : ''}`}>
      <header className="agent-card-head">
        {icon}
        <h3>{title}</h3>
      </header>
      <div className="agent-card-body">{children}</div>
    </section>
  )
}

export default AgentCard
