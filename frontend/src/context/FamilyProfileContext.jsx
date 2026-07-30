// 家庭画像全局状态：用 React Context + localStorage 持久化
// 供评测请求与家庭画像设置页共享
import { createContext, useContext, useEffect, useState } from 'react'

const STORAGE_KEY = 'home_chem_family_profile'

// 默认画像：成年人家庭，无特殊成员
const DEFAULT_PROFILE = {
  children: 0,
  elderly: 0,
  pregnant: false,
  pets: false,
  // 慢性病列表（多选）：高血压/糖尿病/肝病/肾病/哮喘
  chronic_diseases: [],
}

// 慢性病可选项（与表单 checkbox 对应）
export const CHRONIC_DISEASE_OPTIONS = [
  { value: 'hypertension', label: '高血压' },
  { value: 'diabetes', label: '糖尿病' },
  { value: 'liver_disease', label: '肝病' },
  { value: 'kidney_disease', label: '肾病' },
  { value: 'asthma', label: '哮喘' },
]

const FamilyProfileContext = createContext(null)

/**
 * 把家庭画像转成后端期望的结构。
 * 后端 family_profile 接收任意 dict，这里给一个稳定 schema：
 * { has_children, children_count, has_elderly, elderly_count,
 *   has_pregnant, has_pets, chronic_diseases: [label...] }
 */
export function toBackendProfile(profile) {
  if (!profile) return undefined
  return {
    has_children: Number(profile.children) > 0,
    children_count: Number(profile.children) || 0,
    has_elderly: Number(profile.elderly) > 0,
    elderly_count: Number(profile.elderly) || 0,
    has_pregnant: !!profile.pregnant,
    has_pets: !!profile.pets,
    // 后端用中文 label 更直观，这里映射成中文
    chronic_diseases: (profile.chronic_diseases || []).map((code) => {
      const opt = CHRONIC_DISEASE_OPTIONS.find((o) => o.value === code)
      return opt ? opt.label : code
    }),
  }
}

export function FamilyProfileProvider({ children }) {
  const [profile, setProfile] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) return { ...DEFAULT_PROFILE, ...JSON.parse(raw) }
    } catch {
      // localStorage 读取失败忽略，用默认值
    }
    return DEFAULT_PROFILE
  })

  // profile 变更时同步写入 localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
    } catch {
      // 写入失败忽略（隐私模式等）
    }
  }, [profile])

  const update = (patch) => setProfile((prev) => ({ ...prev, ...patch }))
  const reset = () => setProfile(DEFAULT_PROFILE)

  return (
    <FamilyProfileContext.Provider value={{ profile, update, reset }}>
      {children}
    </FamilyProfileContext.Provider>
  )
}

/**
 * 获取家庭画像 context。必须在 FamilyProfileProvider 内调用。
 */
export function useFamilyProfile() {
  const ctx = useContext(FamilyProfileContext)
  if (!ctx) {
    throw new Error('useFamilyProfile 必须在 FamilyProfileProvider 内使用')
  }
  return ctx
}
