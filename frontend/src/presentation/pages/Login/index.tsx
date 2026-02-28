import React, { useState } from 'react'
import { Card, Form, Input, Button, Typography, Tabs, message } from 'antd'
import { LockOutlined, UserOutlined, MailOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/application/stores/authStore'
import { useNavigate } from 'react-router-dom'

const { Title, Text } = Typography

const Login: React.FC = () => {
  const { login, register, isLoading } = useAuthStore()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('login')

  const handleLogin = async (values: { username_or_email: string; password: string }) => {
    try {
      await login(values.username_or_email, values.password)
      navigate('/')
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? 'Login failed')
    }
  }

  const handleRegister = async (values: { email: string; username: string; password: string }) => {
    try {
      await register(values.email, values.username, values.password)
      navigate('/')
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? 'Registration failed')
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          PBAM
        </Title>
        <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}>
          Private Banking &amp; Analytic Management
        </Text>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'login',
              label: 'Sign In',
              children: (
                <Form onFinish={handleLogin} layout="vertical">
                  <Form.Item name="username_or_email" rules={[{ required: true }]}>
                    <Input prefix={<UserOutlined />} placeholder="Username or Email" size="large" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block size="large" loading={isLoading}>
                      Sign In
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: 'Register',
              children: (
                <Form onFinish={handleRegister} layout="vertical">
                  <Form.Item name="email" rules={[{ required: true, type: 'email' }]}>
                    <Input prefix={<MailOutlined />} placeholder="Email" size="large" />
                  </Form.Item>
                  <Form.Item name="username" rules={[{ required: true, min: 3 }]}>
                    <Input prefix={<UserOutlined />} placeholder="Username" size="large" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, min: 8 }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="Password (min 8 chars)" size="large" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block size="large" loading={isLoading}>
                      Create Account
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}

export default Login
