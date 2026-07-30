// 一键呼救按钮：点击弹出 120 + 中毒咨询热线（010-83132345）
// 用 window.open tel: 触发系统拨号面板（移动端有效，桌面端会提示）
import { useState } from 'react'
import { Phone, PhoneCall, X } from 'lucide-react'

const HOTLINES = [
  { name: '急救中心', number: '120', desc: '突发中毒/误服/严重不适' },
  { name: '全国中毒咨询热线', number: '010-83132345', desc: '化学品中毒专业咨询' },
]

function EmergencyButton({ compact }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        className={`emergency-btn${compact ? ' compact' : ''}`}
        onClick={() => setOpen(true)}
      >
        <PhoneCall size={compact ? 16 : 20} />
        <span>{compact ? '一键呼救' : '一键呼救'}</span>
      </button>

      {open && (
        <div className="modal-mask" onClick={() => setOpen(false)}>
          <div className="modal emergency-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setOpen(false)} aria-label="关闭">
              <X size={18} />
            </button>
            <h2>紧急求助</h2>
            <p className="emergency-tip">
              如果出现误服、误触、严重不适或意识不清，请立即拨打以下电话：
            </p>
            <div className="hotline-list">
              {HOTLINES.map((h) => (
                <a
                  key={h.number}
                  className="hotline-item"
                  href={`tel:${h.number}`}
                >
                  <span className="hotline-icon">
                    <Phone size={18} />
                  </span>
                  <span className="hotline-info">
                    <span className="hotline-name">{h.name}</span>
                    <span className="hotline-desc">{h.desc}</span>
                  </span>
                  <span className="hotline-number">{h.number}</span>
                </a>
              ))}
            </div>
            <p className="emergency-note">
              就医时请携带化学品包装或拍照，方便医生判断成分。
            </p>
          </div>
        </div>
      )}
    </>
  )
}

export default EmergencyButton
