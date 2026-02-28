import React from 'react'
import { Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  SwapOutlined,
  TagsOutlined,
  UploadOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'

const { Sider, Content, Header } = Layout
const { Title } = Typography

const MENU_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/transactions', icon: <SwapOutlined />, label: 'Transactions' },
  { key: '/categories', icon: <TagsOutlined />, label: 'Categories' },
  { key: '/import', icon: <UploadOutlined />, label: 'Import PDF' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings' },
]

const AppLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={220}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Title level={5} style={{ color: '#fff', margin: 0 }}>PBAM</Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Content style={{ background: '#f5f5f5', minHeight: '100vh' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
