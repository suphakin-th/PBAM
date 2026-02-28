import React, { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import { useAuthStore } from '@/application/stores/authStore'
import AppLayout from '@/presentation/AppLayout'
import Dashboard from '@/presentation/pages/Dashboard'
import Transactions from '@/presentation/pages/Transactions'
import Categories from '@/presentation/pages/Categories'
import Import from '@/presentation/pages/Import'
import Settings from '@/presentation/pages/Settings'
import Login from '@/presentation/pages/Login'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

const App: React.FC = () => {
  const { initialize } = useAuthStore()

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/import" element={<Import />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
