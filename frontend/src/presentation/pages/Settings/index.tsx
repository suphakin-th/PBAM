import React, { useEffect, useState } from 'react'
import {
  Card,
  Button,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Space,
  Typography,
  Table,
  Tag,
  Popconfirm,
  message,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useFinanceStore } from '@/application/stores/financeStore'
import type { Account } from '@/domain/finance'
import { accountsApi } from '@/infrastructure/api/finance'
import { useAuthStore } from '@/application/stores/authStore'

const { Title } = Typography

const Settings: React.FC = () => {
  const { accounts, fetchAccounts } = useFinanceStore()
  const { user, logout } = useAuthStore()
  const [accountModalOpen, setAccountModalOpen] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchAccounts()
  }, [fetchAccounts])

  const createAccount = async (values: any) => {
    await accountsApi.create({
      name: values.name,
      account_type: values.account_type,
      currency: values.currency ?? 'THB',
      initial_balance: values.initial_balance ?? 0,
      metadata: {},
    })
    await fetchAccounts()
    setAccountModalOpen(false)
    form.resetFields()
    message.success('Account created')
  }

  const deleteAccount = async (id: string) => {
    await accountsApi.delete(id)
    await fetchAccounts()
    message.success('Account deleted')
  }

  const columns: ColumnsType<Account> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Type',
      dataIndex: 'account_type',
      key: 'type',
      render: (type) => <Tag>{type}</Tag>,
    },
    { title: 'Currency', dataIndex: 'currency', key: 'currency' },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'active',
      render: (active) => <Tag color={active ? 'green' : 'default'}>{active ? 'Active' : 'Inactive'}</Tag>,
    },
    {
      title: '',
      key: 'actions',
      render: (_, record) => (
        <Popconfirm title="Delete this account?" onConfirm={() => deleteAccount(record.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Title level={3}>Settings</Title>

        {user && (
          <Card title="Profile">
            <p><strong>Username:</strong> {user.username}</p>
            <p><strong>Email:</strong> {user.email}</p>
            <Button danger onClick={() => logout()}>Sign Out</Button>
          </Card>
        )}

        <Card
          title="Accounts"
          extra={
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setAccountModalOpen(true)}>
              Add Account
            </Button>
          }
        >
          <Table dataSource={accounts} columns={columns} rowKey="id" size="small" pagination={false} />
        </Card>
      </Space>

      <Modal
        title="Add Account"
        open={accountModalOpen}
        onCancel={() => setAccountModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form form={form} onFinish={createAccount} layout="vertical">
          <Form.Item name="name" label="Account Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="account_type" label="Type" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'bank', label: 'Bank' },
                { value: 'cash', label: 'Cash' },
                { value: 'credit_card', label: 'Credit Card' },
                { value: 'savings', label: 'Savings' },
                { value: 'investment', label: 'Investment' },
              ]}
            />
          </Form.Item>
          <Form.Item name="currency" label="Currency" initialValue="THB">
            <Select
              options={[
                { value: 'THB', label: 'THB — Thai Baht' },
                { value: 'USD', label: 'USD — US Dollar' },
                { value: 'EUR', label: 'EUR — Euro' },
                { value: 'GBP', label: 'GBP — British Pound' },
                { value: 'JPY', label: 'JPY — Japanese Yen' },
                { value: 'SGD', label: 'SGD — Singapore Dollar' },
              ]}
            />
          </Form.Item>
          <Form.Item name="initial_balance" label="Initial Balance" initialValue={0}>
            <InputNumber style={{ width: '100%' }} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Settings
