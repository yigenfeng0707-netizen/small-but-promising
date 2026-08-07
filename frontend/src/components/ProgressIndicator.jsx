// 评测进度指示器：显示 6 个 Agent 的执行进度
import { useEffect, useState } from 'react'
import { ScanLine, FlaskConical, AlertTriangle, Users, Lightbulb, Siren } from 'lucide-react'

const AGENT_STEPS = [
  { key: 'recognize', label: '识别', icon: ScanLine },
  { key: 'parse', label: '成分解析', icon: FlaskConical },
  { key: 'risk', label: '风险评测', icon: AlertTriangle },
  { key: 'family', label: '家庭画像', icon: Users },
  { key: 'scenario', label: '场景建议', icon: Lightbulb },
  { key: 'emergency', label: '应急指导', icon: Siren },
]

export default function ProgressIndicator() {
  const [activeStep, setActiveStep] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const stepTimer = setInterval(() => {
      setActiveStep((prev) => (prev < AGENT_STEPS.length - 1 ? prev + 1 : prev))
    }, 1500)

    const elapsedTimer = setInterval(() => {
      setElapsed((prev) => prev + 1)
    }, 1000)

    return () => {
      clearInterval(stepTimer)
      clearInterval(elapsedTimer)
    }
  }, [])

  return (
    <div className="progress-indicator" role="status" aria-live="polite" aria-label="评测进度">
      <div className="progress-header">
        <span className="progress-title">正在调用 6 个 Agent 协同分析</span>
        <span className="progress-elapsed">{elapsed}s</span>
      </div>
      <div className="progress-steps">
        {AGENT_STEPS.map((step, i) => {
          const Icon = step.icon
          const isActive = i === activeStep
          const isDone = i < activeStep
          return (
            <div
              key={step.key}
              className={`progress-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
            >
              <div className="progress-step-icon">
                <Icon size={16} />
              </div>
              <span className="progress-step-label">{step.label}</span>
            </div>
          )
        })}
      </div>
      <div className="progress-bar">
        <div
          className="progress-bar-fill"
          style={{ width: `${((activeStep + 1) / AGENT_STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  )
}
