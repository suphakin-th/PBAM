import React, { useState, useCallback, useEffect } from 'react'
import {
  Steps,
  Upload,
  Button,
  Table,
  Tag,
  Space,
  Typography,
  Alert,
  Spin,
  Select,
  InputNumber,
  DatePicker,
  message,
  Tooltip,
  Popconfirm,
} from 'antd'
import {
  InboxOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { OcrJob, StagingRow } from '@/domain/document'
import { ocrApi } from '@/infrastructure/api/ocr'
import { useFinanceStore } from '@/application/stores/financeStore'
import dayjs from 'dayjs'

const { Dragger } = Upload
const { Title, Text } = Typography
const { Step } = Steps

type ImportStep = 'upload' | 'processing' | 'review' | 'done'

const CONFIDENCE_COLOR = (val: number) => {
  if (val >= 0.8) return '#52c41a'
  if (val >= 0.5) return '#faad14'
  return '#ff4d4f'
}

const ConfidenceDot: React.FC<{ value: number }> = ({ value }) => (
  <Tooltip title={`Confidence: ${(value * 100).toFixed(0)}%`}>
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: CONFIDENCE_COLOR(value),
        marginLeft: 4,
      }}
    />
  </Tooltip>
)

const Import: React.FC = () => {
  const { accounts, fetchAccounts } = useFinanceStore()
  const [step, setStep] = useState<ImportStep>('upload')
  const [currentJob, setCurrentJob] = useState<OcrJob | null>(null)
  const [stagingRows, setStagingRows] = useState<StagingRow[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string>('')
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    fetchAccounts()
  }, [fetchAccounts])

  // Poll job status while processing
  useEffect(() => {
    if (!polling || !currentJob) return
    const interval = setInterval(async () => {
      const { data } = await ocrApi.getJob(currentJob.id)
      setCurrentJob(data)
      if (data.status === 'review') {
        setPolling(false)
        const { data: rows } = await ocrApi.getStaging(currentJob.id)
        setStagingRows(rows.sort((a, b) => a.sort_order - b.sort_order))
        setStep('review')
      } else if (data.status === 'failed') {
        setPolling(false)
        message.error(`OCR failed: ${data.error_message}`)
        setStep('upload')
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [polling, currentJob])

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      message.error('Only PDF files are accepted')
      return false
    }
    try {
      const { data: job } = await ocrApi.upload(file)
      setCurrentJob(job)
      setStep('processing')
      if (job.status === 'review') {
        const { data: rows } = await ocrApi.getStaging(job.id)
        setStagingRows(rows)
        setStep('review')
      } else {
        setPolling(true)
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      // Duplicate file — load the existing job and navigate straight to review
      if (err.response?.status === 409 && detail?.existing_job_id) {
        message.info('This file was already imported. Loading existing data...')
        try {
          const { data: existingJob } = await ocrApi.getJob(detail.existing_job_id)
          setCurrentJob(existingJob)
          if (existingJob.status === 'review') {
            const { data: rows } = await ocrApi.getStaging(existingJob.id)
            setStagingRows(rows.sort((a, b) => a.sort_order - b.sort_order))
            setStep('review')
          } else if (existingJob.status === 'committed') {
            message.success('This file was already committed. All transactions are in your ledger.')
          } else {
            setStep('processing')
            setPolling(true)
          }
        } catch {
          message.error('Could not load existing import job')
        }
      } else {
        message.error(typeof detail === 'string' ? detail : (detail?.message ?? 'Upload failed'))
      }
    }
    return false // prevent auto-upload
  }, [])

  const updateRow = async (rowId: string, updates: Partial<StagingRow>) => {
    if (!currentJob) return
    const { data } = await ocrApi.updateStagingRow(currentJob.id, rowId, updates)
    setStagingRows((prev) => prev.map((r) => (r.id === rowId ? data : r)))
  }

  const discardRow = async (rowId: string) => {
    if (!currentJob) return
    await ocrApi.discardStagingRow(currentJob.id, rowId)
    setStagingRows((prev) =>
      prev.map((r) => (r.id === rowId ? { ...r, review_status: 'discarded' as const } : r))
    )
  }

  const handleCommit = async () => {
    if (!currentJob || !selectedAccountId) {
      message.warning('Please select a default account')
      return
    }
    try {
      const { data } = await ocrApi.commit(currentJob.id, selectedAccountId)
      message.success(`${data.committed_count} transactions imported successfully!`)
      setStep('done')
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? 'Commit failed')
    }
  }

  const columns: ColumnsType<StagingRow> = [
    {
      title: 'Date',
      dataIndex: 'transaction_date',
      key: 'date',
      width: 120,
      render: (d, row) => (
        <Space>
          <DatePicker
            value={d ? dayjs(d) : null}
            size="small"
            format="DD/MM/YYYY"
            onChange={(date) => updateRow(row.id, { transaction_date: date?.format('YYYY-MM-DD') ?? null })}
            disabled={row.review_status === 'discarded'}
          />
          {row.confidence.date !== undefined && <ConfidenceDot value={row.confidence.date} />}
        </Space>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (d, row) => (
        <Space>
          <Text
            editable={
              row.review_status !== 'discarded'
                ? { onChange: (v) => updateRow(row.id, { description: v }) }
                : false
            }
          >
            {d ?? '—'}
          </Text>
          {row.confidence.description !== undefined && (
            <ConfidenceDot value={row.confidence.description} />
          )}
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'transaction_type',
      key: 'type',
      width: 110,
      render: (type, row) => (
        <Select
          value={type ?? undefined}
          size="small"
          style={{ width: '100%' }}
          disabled={row.review_status === 'discarded'}
          onChange={(v) => updateRow(row.id, { transaction_type: v })}
          options={[
            { value: 'income', label: 'Income' },
            { value: 'expense', label: 'Expense' },
            { value: 'transfer', label: 'Transfer' },
          ]}
        />
      ),
    },
    {
      title: 'Amount (THB)',
      dataIndex: 'amount_thb',
      key: 'amount',
      width: 130,
      render: (amount, row) => (
        <Space>
          <InputNumber
            value={amount ? Number(amount) : undefined}
            size="small"
            style={{ width: 100 }}
            precision={2}
            disabled={row.review_status === 'discarded'}
            onChange={(v) => updateRow(row.id, { amount_thb: v ?? undefined })}
            formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
          />
          {row.confidence.amount !== undefined && <ConfidenceDot value={row.confidence.amount} />}
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'review_status',
      key: 'status',
      width: 90,
      render: (status) => {
        const colors: Record<string, string> = {
          pending: 'default',
          edited: 'blue',
          confirmed: 'green',
          discarded: 'red',
        }
        return <Tag color={colors[status] ?? 'default'}>{status}</Tag>
      },
    },
    {
      title: '',
      key: 'actions',
      width: 50,
      render: (_, row) =>
        row.review_status !== 'discarded' ? (
          <Popconfirm title="Discard this row?" onConfirm={() => discardRow(row.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        ) : null,
    },
  ]

  const stepIndex = { upload: 0, processing: 1, review: 2, done: 3 }[step]

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>Import from PDF</Title>

      <Steps current={stepIndex} style={{ marginBottom: 32 }}>
        <Step title="Upload PDF" />
        <Step title="Processing" />
        <Step title="Review & Correct" />
        <Step title="Done" />
      </Steps>

      {step === 'upload' && (
        <Dragger
          accept=".pdf"
          multiple={false}
          beforeUpload={handleUpload}
          showUploadList={false}
          style={{ padding: 24 }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ fontSize: 48, color: '#1677ff' }} />
          </p>
          <p className="ant-upload-text">Click or drag a bank statement PDF to upload</p>
          <p className="ant-upload-hint">
            Supports Thai bank statements. OCR will extract transactions automatically.
          </p>
        </Dragger>
      )}

      {step === 'processing' && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
          <br />
          <Text style={{ marginTop: 16, display: 'block' }}>
            Extracting transactions from PDF... this may take a moment.
          </Text>
        </div>
      )}

      {step === 'review' && (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            type="info"
            message={`${stagingRows.filter((r) => r.review_status !== 'discarded').length} transactions extracted. Review and correct any errors before confirming.`}
            showIcon
          />

          <Space>
            <Text>Default account for import:</Text>
            <Select
              value={selectedAccountId || undefined}
              onChange={setSelectedAccountId}
              placeholder="Select account"
              style={{ width: 200 }}
              options={accounts.map((a) => ({ value: a.id, label: a.name }))}
            />
          </Space>

          <Table
            dataSource={stagingRows}
            columns={columns}
            rowKey="id"
            size="small"
            pagination={false}
            rowClassName={(row) => (row.review_status === 'discarded' ? 'opacity-50' : '')}
            scroll={{ x: 700 }}
          />

          <Space>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={handleCommit}
              disabled={!selectedAccountId}
              size="large"
            >
              Confirm & Import ({stagingRows.filter((r) => r.review_status !== 'discarded').length} transactions)
            </Button>
            <Button onClick={() => setStep('upload')}>Cancel</Button>
          </Space>
        </Space>
      )}

      {step === 'done' && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a' }} />
          <br />
          <Title level={4} style={{ marginTop: 16 }}>Import Complete!</Title>
          <Button type="primary" onClick={() => setStep('upload')}>
            Import Another File
          </Button>
        </div>
      )}
    </div>
  )
}

export default Import
