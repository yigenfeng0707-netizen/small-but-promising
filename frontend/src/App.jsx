// 路由入口：用 react-router-dom 组织页面，Layout 包裹所有页面
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ResultPage from './pages/ResultPage'
import FamilyProfilePage from './pages/FamilyProfilePage'
import BatchPage from './pages/BatchPage'
import './App.css'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/family" element={<FamilyProfilePage />} />
        <Route path="/batch" element={<BatchPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
