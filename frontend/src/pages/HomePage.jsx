// 首页：三种入口（拍照/语音/文本）+ 家庭画像入口 + 批量评测入口
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Mic, MessageSquare, Users, Loader2, Layers } from 'lucide-react'
import { evaluate, evaluateUpload, evaluateVoice } from '../api/client'
import { useFamilyProfile, toBackendProfile } from '../context/FamilyProfileContext'
import VoiceInput from '../components/VoiceInput'

function HomePage() {
  const navigate = useNavigate()
  const { profile } = useFamilyProfile()
  const fileRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState('')

  const familyProfile = toBackendProfile(profile)

  // 统一跳转结果页：把完整结果通过 state 传递，避免结果页再请求一次
  const goResult = (data) => {
    navigate('/result', { state: { result: data } })
  }

  // 拍照/上传图片评测
  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = '' // 允许同一文件再次触发
    setLoading(true)
    setError('')
    try {
      const data = await evaluateUpload(file, { familyProfile })
      goResult(data)
    } catch (err) {
      setError(err.message || '评测失败，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  // 语音识别完成回调：拿到文字后调语音评测接口
  const handleVoiceResult = async (voiceText) => {
    if (!voiceText) return
    setLoading(true)
    setError('')
    try {
      const data = await evaluateVoice({ voiceText, familyProfile })
      goResult(data)
    } catch (err) {
      setError(err.message || '语音评测失败，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  // 文本提交
  const handleTextSubmit = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError('')
    try {
      // 文本走 /api/evaluate 的 voice_text 分支（后端语义一致）
      const data = await evaluate({ voiceText: text.trim(), familyProfile })
      goResult(data)
    } catch (err) {
      setError(err.message || '评测失败，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="home">
      <header className="home-hero">
        <h1 className="home-title">安居智评 Agent</h1>
        <p className="home-subtitle">拍一下，知道家里的化学品安不安全</p>
      </header>

      <div className="entry-cards">
        {/* 拍照评测 */}
        <button
          type="button"
          className="entry-card entry-photo"
          onClick={() => fileRef.current?.click()}
          disabled={loading}
        >
          <Camera size={32} />
          <h3>拍照评测</h3>
          <p>拍一下化学品包装，识别成分并评估风险</p>
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFile}
          style={{ display: 'none' }}
        />

        {/* 语音提问 */}
        <div className="entry-card entry-voice">
          <Mic size={32} />
          <h3>语音提问</h3>
          <p>按住说话，问一句"84 和洁厕灵能混用吗"</p>
          <VoiceInput onResult={handleVoiceResult} />
        </div>

        {/* 文本提问 */}
        <div className="entry-card entry-text">
          <MessageSquare size={32} />
          <h3>文本提问</h3>
          <p>输入化学品名称或疑问，立即评测</p>
          <textarea
            className="text-input"
            placeholder="例如：84 消毒液和洁厕灵能混用吗"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleTextSubmit()
            }}
          />
          <button
            type="button"
            className="submit-btn"
            onClick={handleTextSubmit}
            disabled={loading || !text.trim()}
          >
            {loading ? <Loader2 size={16} className="spin" /> : null}
            {loading ? '评测中…' : '提交评测'}
          </button>
        </div>
      </div>

      {error && <div className="home-error">❌ {error}</div>}
      {loading && (
        <div className="home-loading">
          <Loader2 size={20} className="spin" /> 正在调用 6 个 Agent 协同分析，请稍候…
        </div>
      )}

      <nav className="home-extras">
        <button className="extra-link" onClick={() => navigate('/family')}>
          <Users size={18} /> 家庭画像设置
        </button>
        <button className="extra-link" onClick={() => navigate('/batch')}>
          <Layers size={18} /> 公益机构批量评测
        </button>
      </nav>

      <footer className="home-footer">
        AI 向善·2026 小有可为参赛作品 | 公益机构批量评测入口
      </footer>
    </div>
  )
}

export default HomePage
