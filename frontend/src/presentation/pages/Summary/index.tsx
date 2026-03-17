import React, { useCallback, useEffect, useState } from 'react'
import {
  Badge,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Segmented,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  BankOutlined,
  ExclamationCircleOutlined,
  FallOutlined,
  FileTextOutlined,
  RiseOutlined,
  SyncOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { Column, Pie } from '@ant-design/plots'
import dayjs from 'dayjs'
import { summaryApi } from '@/infrastructure/api/finance'
import type { AccountStat, Summary } from '@/domain/finance'

const { RangePicker } = DatePicker
const { Title, Text } = Typography

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtThb = (v: number) =>
  `฿${v.toLocaleString('th-TH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

const PRESETS = [
  { label: 'This Month', value: 'this_month' },
  { label: 'Last 3 Mo.', value: 'last_3m' },
  { label: 'This Year', value: 'this_year' },
  { label: 'All Time', value: 'all_time' },
]

function presetDates(key: string): [string | null, string | null] {
  const today = dayjs()
  switch (key) {
    case 'this_month':
      return [today.startOf('month').format('YYYY-MM-DD'), today.endOf('month').format('YYYY-MM-DD')]
    case 'last_3m':
      return [today.subtract(3, 'month').startOf('month').format('YYYY-MM-DD'), today.format('YYYY-MM-DD')]
    case 'this_year':
      return [today.startOf('year').format('YYYY-MM-DD'), today.endOf('year').format('YYYY-MM-DD')]
    default:
      return [null, null]
  }
}

const ACCOUNT_COLORS: Record<string, string> = {
  bank: '#1677ff',
  cash: '#52c41a',
  credit_card: '#fa8c16',
  savings: '#13c2c2',
  investment: '#722ed1',
}

const PAYMENT_LABELS: Record<string, string> = {
  credit_card: 'Credit Card',
  debit_card: 'Debit Card',
  qr_code: 'QR Code',
  promptpay: 'PromptPay',
  bank_transfer: 'Bank Transfer',
  digital_wallet: 'Digital Wallet',
  atm: 'ATM',
  cash: 'Cash',
  online: 'Online',
  subscription: 'Subscription',
  unknown: 'Unknown',
}

// ── Account Table columns ─────────────────────────────────────────────────────

const accountColumns = [
  {
    title: 'Account',
    dataIndex: 'name',
    render: (name: string, rec: AccountStat) => (
      <Space size={6}>
        <Tag color={ACCOUNT_COLORS[rec.account_type] ?? '#1677ff'} style={{ margin: 0 }}>
          {rec.account_type}
        </Tag>
        {name}
      </Space>
    ),
  },
  { title: 'CCY', dataIndex: 'currency', width: 60 },
  {
    title: 'Balance',
    dataIndex: 'balance_thb',
    align: 'right' as const,
    render: (v: number) => (
      <Text strong style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
        {fmtThb(v)}
      </Text>
    ),
  },
  {
    title: 'Income (period)',
    dataIndex: 'period_income_thb',
    align: 'right' as const,
    render: (v: number) =>
      v > 0 ? (
        <Text style={{ color: '#52c41a' }}>{fmtThb(v)}</Text>
      ) : (
        <Text type="secondary">—</Text>
      ),
  },
  {
    title: 'Expense (period)',
    dataIndex: 'period_expense_thb',
    align: 'right' as const,
    render: (v: number) =>
      v > 0 ? (
        <Text style={{ color: '#ff4d4f' }}>{fmtThb(v)}</Text>
      ) : (
        <Text type="secondary">—</Text>
      ),
  },
]

// ── Category breakdown list ───────────────────────────────────────────────────

interface CatListProps {
  items: Summary['top_expense_categories']
  valueColor: string
}

const CategoryList: React.FC<CatListProps> = ({ items, valueColor }) => (
  <div style={{ marginTop: 12 }}>
    {items.map((c) => (
      <div
        key={c.category_id}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '5px 0',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Space size={8}>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: c.color ?? valueColor,
              flexShrink: 0,
            }}
          />
          <Text style={{ fontSize: 13 }}>{c.name}</Text>
        </Space>
        <Space size={12}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {c.count}x
          </Text>
          <Text strong style={{ fontSize: 13, color: valueColor }}>
            {fmtThb(Number(c.total_thb))}
          </Text>
          <Text type="secondary" style={{ fontSize: 11, minWidth: 42, textAlign: 'right' }}>
            {c.percentage}%
          </Text>
        </Space>
      </div>
    ))}
  </div>
)

// ── Main page ─────────────────────────────────────────────────────────────────

const SummaryPage: React.FC = () => {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(false)
  const [preset, setPreset] = useState('this_month')

  const fetchSummary = useCallback(async (from: string | null, to: string | null) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (from) params.date_from = from
      if (to) params.date_to = to
      const { data } = await summaryApi.get(params)
      setSummary(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const [from, to] = presetDates('this_month')
    fetchSummary(from, to)
  }, [fetchSummary])

  const handlePreset = (value: string) => {
    setPreset(value)
    const [from, to] = presetDates(value)
    fetchSummary(from, to)
  }

  const handleCustomRange = (dates: unknown) => {
    const d = dates as [{ format: (f: string) => string }, { format: (f: string) => string }] | null
    if (d) {
      setPreset('custom')
      fetchSummary(d[0].format('YYYY-MM-DD'), d[1].format('YYYY-MM-DD'))
    }
  }

  // Chart data
  const monthlyData = summary?.monthly_trend.flatMap((p) => [
    { month: p.month, type: 'Income', value: Number(p.income_thb) },
    { month: p.month, type: 'Expense', value: Number(p.expense_thb) },
  ]) ?? []

  const expensePieData = (summary?.top_expense_categories ?? []).map((c) => ({
    name: c.name,
    value: Number(c.total_thb),
  }))

  const incomePieData = (summary?.top_income_categories ?? []).map((c) => ({
    name: c.name,
    value: Number(c.total_thb),
  }))

  const paymentPieData = (summary?.payment_methods ?? []).map((p) => ({
    name: PAYMENT_LABELS[p.method] ?? p.method,
    value: Number(p.total_thb),
  }))

  const netPositive = Number(summary?.net_thb ?? 0) >= 0

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* ── Header ── */}
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              Summary
            </Title>
          </Col>
          <Col>
            <Space wrap>
              <Segmented
                options={PRESETS}
                value={PRESETS.find((p) => p.value === preset) ? preset : undefined}
                onChange={(v) => handlePreset(v as string)}
              />
              <RangePicker
                placeholder={['Custom start', 'Custom end']}
                onChange={handleCustomRange}
              />
            </Space>
          </Col>
        </Row>

        <Spin spinning={loading}>
          {/* ── KPI Cards ── */}
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Total Income"
                  value={Number(summary?.total_income_thb ?? 0)}
                  formatter={(v) => fmtThb(Number(v))}
                  prefix={<RiseOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Total Expense"
                  value={Number(summary?.total_expense_thb ?? 0)}
                  formatter={(v) => fmtThb(Number(v))}
                  prefix={<FallOutlined />}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Net Cash Flow"
                  value={Number(summary?.net_thb ?? 0)}
                  formatter={(v) => fmtThb(Number(v))}
                  prefix={<SwapOutlined />}
                  valueStyle={{ color: netPositive ? '#52c41a' : '#ff4d4f' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Transactions"
                  value={summary?.transaction_count ?? 0}
                  prefix={<FileTextOutlined />}
                  suffix={
                    summary?.uncategorized_count ? (
                      <Tooltip title={`${summary.uncategorized_count} uncategorized`}>
                        <Badge
                          count={summary.uncategorized_count}
                          color="orange"
                          style={{ marginLeft: 4 }}
                        />
                      </Tooltip>
                    ) : undefined
                  }
                />
                {(summary?.recurring_count ?? 0) > 0 && (
                  <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                    <SyncOutlined style={{ marginRight: 4 }} />
                    {summary!.recurring_count} recurring
                  </Text>
                )}
                {(summary?.uncategorized_count ?? 0) > 0 && (
                  <Text type="warning" style={{ fontSize: 12, display: 'block' }}>
                    <ExclamationCircleOutlined style={{ marginRight: 4 }} />
                    {summary!.uncategorized_count} uncategorized
                  </Text>
                )}
              </Card>
            </Col>
          </Row>

          {/* ── Monthly Trend ── */}
          {monthlyData.length > 0 && (
            <Card title="Monthly Trend">
              <Column
                data={monthlyData}
                xField="month"
                yField="value"
                colorField="type"
                group
                color={['#52c41a', '#ff4d4f']}
                axis={{
                  y: {
                    labelFormatter: (v: number) =>
                      v >= 1000 ? `฿${(v / 1000).toFixed(0)}k` : `฿${v}`,
                  },
                }}
                height={280}
                legend={{ position: 'top-right' }}
              />
            </Card>
          )}

          {/* ── Category Charts ── */}
          <Row gutter={[16, 16]}>
            {/* Expense categories */}
            <Col xs={24} lg={12}>
              <Card
                title="Top Expense Categories"
                extra={
                  summary && (
                    <Text type="secondary">{fmtThb(Number(summary.total_expense_thb))} total</Text>
                  )
                }
              >
                {expensePieData.length > 0 ? (
                  <>
                    <Pie
                      data={expensePieData}
                      angleField="value"
                      colorField="name"
                      innerRadius={0.62}
                      height={220}
                      legend={false}
                      label={false}
                      tooltip={{ items: [{ field: 'value', valueFormatter: (v: number) => fmtThb(v) }] }}
                      annotations={[
                        {
                          type: 'text',
                          style: {
                            text: 'Expenses',
                            x: '50%',
                            y: '50%',
                            textAlign: 'center',
                            fontSize: 13,
                            fill: '#aaa',
                          },
                        },
                      ]}
                    />
                    <CategoryList items={summary!.top_expense_categories} valueColor="#ff4d4f" />
                  </>
                ) : (
                  <Empty description="No expense data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>

            {/* Income categories */}
            <Col xs={24} lg={12}>
              <Card
                title="Top Income Sources"
                extra={
                  summary && (
                    <Text type="secondary">{fmtThb(Number(summary.total_income_thb))} total</Text>
                  )
                }
              >
                {incomePieData.length > 0 ? (
                  <>
                    <Pie
                      data={incomePieData}
                      angleField="value"
                      colorField="name"
                      innerRadius={0.62}
                      height={220}
                      legend={false}
                      label={false}
                      tooltip={{ items: [{ field: 'value', valueFormatter: (v: number) => fmtThb(v) }] }}
                      annotations={[
                        {
                          type: 'text',
                          style: {
                            text: 'Income',
                            x: '50%',
                            y: '50%',
                            textAlign: 'center',
                            fontSize: 13,
                            fill: '#aaa',
                          },
                        },
                      ]}
                    />
                    <CategoryList items={summary!.top_income_categories} valueColor="#52c41a" />
                  </>
                ) : (
                  <Empty description="No income data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
          </Row>

          {/* ── Accounts & Payment Methods ── */}
          <Row gutter={[16, 16]}>
            {/* Accounts */}
            <Col xs={24} lg={14}>
              <Card title="Accounts" extra={<BankOutlined />}>
                <Table
                  dataSource={summary?.accounts ?? []}
                  rowKey="account_id"
                  pagination={false}
                  size="small"
                  columns={accountColumns}
                  locale={{ emptyText: 'No accounts' }}
                />
              </Card>
            </Col>

            {/* Payment methods */}
            <Col xs={24} lg={10}>
              <Card title="Payment Methods">
                {paymentPieData.length > 0 ? (
                  <>
                    <Pie
                      data={paymentPieData}
                      angleField="value"
                      colorField="name"
                      innerRadius={0.55}
                      height={180}
                      legend={false}
                      label={false}
                      tooltip={{ items: [{ field: 'value', valueFormatter: (v: number) => fmtThb(v) }] }}
                    />
                    <div style={{ marginTop: 12 }}>
                      {summary?.payment_methods.map((p) => (
                        <div
                          key={p.method}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '4px 0',
                            borderBottom: '1px solid #f0f0f0',
                          }}
                        >
                          <Text style={{ fontSize: 13 }}>
                            {PAYMENT_LABELS[p.method] ?? p.method}
                          </Text>
                          <Space size={10}>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {p.count}x
                            </Text>
                            <Text strong style={{ fontSize: 13 }}>
                              {fmtThb(Number(p.total_thb))}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 11, minWidth: 38, textAlign: 'right' }}>
                              {p.percentage}%
                            </Text>
                          </Space>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <Empty description="No payment data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
          </Row>
        </Spin>
      </Space>
    </div>
  )
}

export default SummaryPage
