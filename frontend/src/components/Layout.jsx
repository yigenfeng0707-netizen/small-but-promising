// 顶部导航 + 页面容器
import { Link, useLocation } from 'react-router-dom'
import { Home, Users, Layers, ShieldCheck } from 'lucide-react'

function Layout({ children }) {
  const { pathname } = useLocation()

  return (
    <div className="layout">
      <header className="topbar">
        <Link to="/" className="brand">
          <ShieldCheck size={22} />
          <span>安居智评</span>
        </Link>
        <nav className="topnav">
          <Link to="/" className={pathname === '/' ? 'active' : ''}>
            <Home size={16} /> 首页
          </Link>
          <Link to="/family" className={pathname === '/family' ? 'active' : ''}>
            <Users size={16} /> 家庭画像
          </Link>
          <Link to="/batch" className={pathname === '/batch' ? 'active' : ''}>
            <Layers size={16} /> 批量评测
          </Link>
        </nav>
      </header>
      <main className="page">{children}</main>
    </div>
  )
}

export default Layout
