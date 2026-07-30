// 语音输入组件：用 Web Speech API（webkitSpeechRecognition || SpeechRecognition）
// 中文 lang='zh-CN'，点击开始录音、再点击结束，识别结果通过 onResult 回调
import { useEffect, useRef, useState } from 'react'
import { Mic, Square } from 'lucide-react'

function VoiceInput({ onResult, placeholder }) {
  const [supported, setSupported] = useState(true)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const recRef = useRef(null)

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setSupported(false)
      return
    }
    const rec = new SR()
    rec.lang = 'zh-CN'
    rec.continuous = false
    rec.interimResults = true
    rec.maxAlternatives = 1

    rec.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i]
        if (r.isFinal) finalText += r[0].transcript
        else interimText += r[0].transcript
      }
      setInterim(interimText || finalText)
      if (finalText) {
        setInterim('')
        onResult && onResult(finalText.trim())
      }
    }
    rec.onend = () => {
      setListening(false)
      setInterim('')
    }
    rec.onerror = (e) => {
      setListening(false)
      setInterim('')
      // no-speech / not-allowed 等错误静默处理，避免控制台噪声
      console.warn('语音识别错误:', e.error)
    }
    recRef.current = rec

    return () => {
      try {
        rec.abort()
      } catch {
        // 忽略
      }
    }
  }, [onResult])

  const toggle = () => {
    if (!supported || !recRef.current) return
    try {
      if (listening) {
        recRef.current.stop()
        setListening(false)
      } else {
        setInterim('')
        recRef.current.start()
        setListening(true)
      }
    } catch (err) {
      // 非安全上下文（非 HTTPS/非 localhost）下 start 可能抛错
      setListening(false)
      console.error('启动语音识别失败:', err)
    }
  }

  if (!supported) {
    return (
      <div className="voice-unsupported">
        <Mic size={18} />
        <span>当前浏览器不支持语音识别，请改用文本输入（建议 Chrome + localhost 访问）</span>
      </div>
    )
  }

  return (
    <button
      type="button"
      className={`voice-btn${listening ? ' listening' : ''}`}
      onClick={toggle}
      title={listening ? '点击结束录音' : '点击开始说话'}
    >
      {listening ? <Square size={18} /> : <Mic size={18} />}
      <span>{listening ? '正在聆听…点击结束' : placeholder || '点击说话'}</span>
    </button>
  )
}

export default VoiceInput
