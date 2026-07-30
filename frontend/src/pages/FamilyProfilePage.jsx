// 家庭画像设置页：儿童数/老人数/孕妇/宠物/慢性病多选，保存到 Context + localStorage
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Save, RotateCcw } from 'lucide-react'
import { useFamilyProfile, CHRONIC_DISEASE_OPTIONS } from '../context/FamilyProfileContext'

function FamilyProfilePage() {
  const navigate = useNavigate()
  const { profile, update, reset } = useFamilyProfile()
  const [saved, setSaved] = useState(false)

  // 慢性病多选切换
  const toggleDisease = (code) => {
    const set = new Set(profile.chronic_diseases || [])
    if (set.has(code)) set.delete(code)
    else set.add(code)
    update({ chronic_diseases: Array.from(set) })
  }

  const handleSave = () => {
    // FamilyProfileContext 已通过 useEffect 自动写 localStorage，这里只需反馈 + 跳回首页
    setSaved(true)
    setTimeout(() => navigate('/'), 600)
  }

  const handleReset = () => {
    reset()
    setSaved(false)
  }

  return (
    <div className="profile-page">
      <header className="page-title">
        <Users size={22} />
        <h1>家庭画像设置</h1>
      </header>
      <p className="page-desc">
        根据家庭成员情况给出差异化风险与建议。数据仅保存在本地浏览器，不上传。
      </p>

      <div className="profile-form">
        {/* 成员人数 */}
        <div className="form-row">
          <div className="form-field">
            <label>儿童数（&lt; 12 岁）</label>
            <input
              type="number"
              min="0"
              max="20"
              value={profile.children}
              onChange={(e) => update({ children: Number(e.target.value) || 0 })}
            />
          </div>
          <div className="form-field">
            <label>老人数（&ge; 65 岁）</label>
            <input
              type="number"
              min="0"
              max="20"
              value={profile.elderly}
              onChange={(e) => update({ elderly: Number(e.target.value) || 0 })}
            />
          </div>
        </div>

        {/* 开关：孕妇 / 宠物 */}
        <div className="form-row">
          <label className="switch-field">
            <input
              type="checkbox"
              checked={!!profile.pregnant}
              onChange={(e) => update({ pregnant: e.target.checked })}
            />
            <span className="switch-label">家中含孕妇</span>
          </label>
          <label className="switch-field">
            <input
              type="checkbox"
              checked={!!profile.pets}
              onChange={(e) => update({ pets: e.target.checked })}
            />
            <span className="switch-label">家中含宠物</span>
          </label>
        </div>

        {/* 慢性病多选 */}
        <div className="form-field full">
          <label>慢性病（可多选，影响用药与化学品建议）</label>
          <div className="checkbox-grid">
            {CHRONIC_DISEASE_OPTIONS.map((opt) => {
              const checked = (profile.chronic_diseases || []).includes(opt.value)
              return (
                <label
                  key={opt.value}
                  className={`checkbox-chip${checked ? ' checked' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleDisease(opt.value)}
                  />
                  <span>{opt.label}</span>
                </label>
              )
            })}
          </div>
        </div>
      </div>

      <div className="form-actions">
        <button className="action-btn primary" onClick={handleSave}>
          <Save size={16} /> {saved ? '已保存，返回首页…' : '保存并返回首页'}
        </button>
        <button className="action-btn" onClick={handleReset}>
          <RotateCcw size={16} /> 重置
        </button>
      </div>
    </div>
  )
}

export default FamilyProfilePage
