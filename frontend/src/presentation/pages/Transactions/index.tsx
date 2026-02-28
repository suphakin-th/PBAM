import React, { useEffect, useMemo, useState } from 'react'
import {
  Table,
  Button,
  Tag,
  Space,
  Drawer,
  Input,
  Typography,
  Popconfirm,
  message,
  Modal,
  Select,
  Tooltip,
} from 'antd'
import {
  PlusOutlined,
  CommentOutlined,
  DeleteOutlined,
  LinkOutlined,
  DisconnectOutlined,
  BulbOutlined,
} from '@ant-design/icons'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useFinanceStore } from '@/application/stores/financeStore'
import type { Transaction, TransactionCategory, TransactionComment } from '@/domain/finance'
import { transactionsApi } from '@/infrastructure/api/finance'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { TextArea } = Input

const PAGE_SIZE = 50

// Flatten category tree into a flat list
function flattenCategories(cats: TransactionCategory[]): TransactionCategory[] {
  const result: TransactionCategory[] = []
  const walk = (list: TransactionCategory[]) => {
    for (const c of list) {
      result.push(c)
      if (c.children.length) walk(c.children)
    }
  }
  walk(cats)
  return result
}

// Score how well a category name matches a transaction description (0 = no match)
function matchScore(description: string, catName: string): number {
  const desc = description.toLowerCase()
  const name = catName.toLowerCase()
  if (desc.includes(name)) return 2         // exact substring match
  // word-level partial: any word in catName appears in desc
  const words = name.split(/\s+/).filter((w) => w.length >= 2)
  if (words.some((w) => desc.includes(w))) return 1
  return 0
}

const Transactions: React.FC = () => {
  const {
    accounts,
    categories,
    transactions,
    transactionTotal,
    fetchAccounts,
    fetchCategories,
    fetchTransactions,
    isLoading,
  } = useFinanceStore()
  const [page, setPage] = useState(1)

  // Comments drawer
  const [commentDrawerOpen, setCommentDrawerOpen] = useState(false)
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null)
  const [comments, setComments] = useState<TransactionComment[]>([])
  const [newComment, setNewComment] = useState('')
  const [commentLoading, setCommentLoading] = useState(false)

  // Transfer link modal
  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [linkSourceTx, setLinkSourceTx] = useState<Transaction | null>(null)
  const [linkTargetId, setLinkTargetId] = useState<string | undefined>(undefined)
  const [linkLoading, setLinkLoading] = useState(false)

  useEffect(() => {
    fetchAccounts()
    fetchCategories()
  }, [fetchAccounts, fetchCategories])

  useEffect(() => {
    fetchTransactions({ page, pageSize: PAGE_SIZE })
  }, [page, fetchTransactions])

  // Lookup maps
  const accountMap = useMemo(
    () => Object.fromEntries(accounts.map((a) => [a.id, a])),
    [accounts]
  )
  const flatCats = useMemo(() => flattenCategories(categories), [categories])
  const catMap = useMemo(
    () => Object.fromEntries(flatCats.map((c) => [c.id, c])),
    [flatCats]
  )

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  // ── Category assignment ─────────────────────────────────────────────────────

  const handleCategoryChange = async (tx: Transaction, categoryId: string | null) => {
    try {
      await transactionsApi.update(tx.id, { category_id: categoryId })
      // Refresh current page
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch {
      message.error('Failed to update category')
    }
  }

  // Build options for a transaction's category select, with suggestions highlighted
  const buildCategoryOptions = (tx: Transaction) => {
    const matchType = tx.transaction_type // 'income' | 'expense' | 'transfer'
    const eligible = flatCats.filter((c) => c.category_type === matchType)

    const scored = eligible.map((c) => ({
      cat: c,
      score: matchScore(tx.description, c.name),
    }))
    // Suggestions first, then the rest alphabetically
    scored.sort((a, b) => b.score - a.score || a.cat.name.localeCompare(b.cat.name))

    return scored.map(({ cat, score }) => ({
      value: cat.id,
      label: (
        <Space size={4}>
          {cat.color && (
            <span
              style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: cat.color,
              }}
            />
          )}
          {cat.name}
          {score > 0 && (
            <Tooltip title="Suggested — name matches description">
              <BulbOutlined style={{ color: '#faad14', fontSize: 12 }} />
            </Tooltip>
          )}
        </Space>
      ),
      // plain text for search filtering
      searchLabel: cat.name,
    }))
  }

  // ── Comments ────────────────────────────────────────────────────────────────

  const openComments = async (tx: Transaction) => {
    setSelectedTx(tx)
    setCommentDrawerOpen(true)
    const { data } = await transactionsApi.listComments(tx.id)
    setComments(data)
  }

  const submitComment = async () => {
    if (!selectedTx || !newComment.trim()) return
    setCommentLoading(true)
    try {
      const { data } = await transactionsApi.addComment(selectedTx.id, newComment.trim())
      setComments((prev) => [...prev, data])
      setNewComment('')
    } finally {
      setCommentLoading(false)
    }
  }

  const deleteComment = async (commentId: string) => {
    if (!selectedTx) return
    await transactionsApi.deleteComment(selectedTx.id, commentId)
    setComments((prev) => prev.filter((c) => c.id !== commentId))
    message.success('Comment deleted')
  }

  // ── Transfer linking ────────────────────────────────────────────────────────

  const openLinkModal = (tx: Transaction) => {
    setLinkSourceTx(tx)
    setLinkTargetId(undefined)
    setLinkModalOpen(true)
  }

  const handleLink = async () => {
    if (!linkSourceTx || !linkTargetId) return
    setLinkLoading(true)
    try {
      await transactionsApi.linkTransfer(linkSourceTx.id, linkTargetId)
      message.success('Transfer linked successfully')
      setLinkModalOpen(false)
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? 'Link failed')
    } finally {
      setLinkLoading(false)
    }
  }

  const handleUnlink = async (tx: Transaction) => {
    try {
      await transactionsApi.unlinkTransfer(tx.id)
      message.success('Transfer unlinked')
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? 'Unlink failed')
    }
  }

  const transferCandidates = transactions.filter(
    (t) => t.transaction_type === 'transfer' && !t.transfer_pair_id && t.id !== linkSourceTx?.id
  )

  // ── Table columns ───────────────────────────────────────────────────────────

  const columns: ColumnsType<Transaction> = [
    {
      title: 'Date',
      dataIndex: 'transaction_date',
      key: 'date',
      width: 100,
      render: (d) => dayjs(d).format('DD MMM YY'),
      sorter: (a, b) => a.transaction_date.localeCompare(b.transaction_date),
      defaultSortOrder: 'descend',
    },
    {
      title: 'Account',
      dataIndex: 'account_id',
      key: 'account',
      width: 110,
      render: (id) => (
        <Text style={{ fontSize: 12 }} type="secondary">
          {accountMap[id]?.name ?? '—'}
        </Text>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Type',
      dataIndex: 'transaction_type',
      key: 'type',
      width: 100,
      render: (type, record) => (
        <Space size={4}>
          <Tag color={type === 'income' ? 'green' : type === 'expense' ? 'red' : 'blue'} style={{ margin: 0 }}>
            {type.toUpperCase()}
          </Tag>
          {record.transfer_pair_id && (
            <Tooltip title="Linked transfer">
              <LinkOutlined style={{ color: '#1677ff', fontSize: 11 }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: 'Category',
      dataIndex: 'category_id',
      key: 'category',
      width: 200,
      render: (catId: string | null, record) => {
        const cat = catId ? catMap[catId] : null
        const opts = buildCategoryOptions(record)
        const hasSuggestion = !catId && opts.some((o) => (o as any).searchLabel && matchScore(record.description, (o as any).searchLabel) > 0)

        return (
          <Select
            value={catId ?? undefined}
            size="small"
            style={{ width: '100%', minWidth: 150 }}
            placeholder={
              hasSuggestion ? (
                <Space size={4}>
                  <BulbOutlined style={{ color: '#faad14' }} />
                  <span style={{ color: '#faad14' }}>Suggested</span>
                </Space>
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>Uncategorized</Text>
              )
            }
            allowClear
            showSearch
            filterOption={(input, option) =>
              ((option as any)?.searchLabel ?? '').toLowerCase().includes(input.toLowerCase())
            }
            onChange={(v) => handleCategoryChange(record, v ?? null)}
            options={opts}
            dropdownStyle={{ minWidth: 220 }}
            // Show colored dot for the selected value
            labelRender={() =>
              cat ? (
                <Space size={4}>
                  {cat.color && (
                    <span
                      style={{
                        display: 'inline-block',
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: cat.color,
                      }}
                    />
                  )}
                  <span style={{ fontSize: 12 }}>{cat.name}</span>
                </Space>
              ) : undefined
            }
          />
        )
      },
    },
    {
      title: 'Amount (THB)',
      dataIndex: 'amount_thb',
      key: 'amount',
      align: 'right',
      width: 130,
      render: (amount, record) => (
        <span style={{
          color: record.transaction_type === 'income' ? '#52c41a'
            : record.transaction_type === 'expense' ? '#ff4d4f'
            : '#1677ff',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {record.transaction_type === 'expense' ? '-' : '+'} ฿{Number(amount).toLocaleString('th-TH', { minimumFractionDigits: 2 })}
        </span>
      ),
      sorter: (a, b) => Number(a.amount_thb) - Number(b.amount_thb),
    },
    {
      title: '',
      key: 'actions',
      width: 90,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="Comments">
            <Button icon={<CommentOutlined />} size="small" onClick={() => openComments(record)} />
          </Tooltip>
          {record.transaction_type === 'transfer' && !record.transfer_pair_id && (
            <Tooltip title="Link counterpart transfer">
              <Button icon={<LinkOutlined />} size="small" onClick={() => openLinkModal(record)} />
            </Tooltip>
          )}
          {record.transaction_type === 'transfer' && record.transfer_pair_id && (
            <Tooltip title="Unlink transfer pair">
              <Popconfirm title="Unlink this transfer pair?" onConfirm={() => handleUnlink(record)}>
                <Button icon={<DisconnectOutlined />} size="small" danger />
              </Popconfirm>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space>
          <Title level={3} style={{ margin: 0 }}>Transactions</Title>
          <Button type="primary" icon={<PlusOutlined />}>Add Transaction</Button>
        </Space>

        <Table
          dataSource={transactions}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          onChange={handleTableChange}
          size="small"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: transactionTotal,
            showTotal: (total) => `${total} transactions`,
            showSizeChanger: false,
          }}
          scroll={{ x: 900 }}
        />
      </Space>

      {/* Comment Drawer */}
      <Drawer
        title={`Comments — ${selectedTx?.description ?? ''}`}
        open={commentDrawerOpen}
        onClose={() => setCommentDrawerOpen(false)}
        width={400}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {comments.map((c) => (
            <div
              key={c.id}
              style={{ background: '#f5f5f5', borderRadius: 8, padding: '8px 12px', position: 'relative' }}
            >
              <Text>{c.content}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 11 }}>
                {dayjs(c.created_at).format('DD MMM YYYY HH:mm')}
              </Text>
              <Popconfirm title="Delete comment?" onConfirm={() => deleteComment(c.id)}>
                <Button
                  type="text" danger icon={<DeleteOutlined />} size="small"
                  style={{ position: 'absolute', top: 8, right: 8 }}
                />
              </Popconfirm>
            </div>
          ))}
          <TextArea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Add a comment..."
            rows={3}
          />
          <Button type="primary" onClick={submitComment} loading={commentLoading} disabled={!newComment.trim()}>
            Add Comment
          </Button>
        </Space>
      </Drawer>

      {/* Link Transfer Modal */}
      <Modal
        title={`Link counterpart for: "${linkSourceTx?.description ?? ''}"`}
        open={linkModalOpen}
        onCancel={() => setLinkModalOpen(false)}
        onOk={handleLink}
        okText="Link"
        okButtonProps={{ loading: linkLoading, disabled: !linkTargetId }}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
          <Text type="secondary">
            Select the matching transfer from the other account.
            Example: "โอนเงินไป SCB" pairs with "รับเงินจาก KBank".
          </Text>
          <Select
            style={{ width: '100%' }}
            placeholder="Select counterpart transaction"
            value={linkTargetId}
            onChange={setLinkTargetId}
            showSearch
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={transferCandidates.map((t) => ({
              value: t.id,
              label: `${dayjs(t.transaction_date).format('DD MMM')} — ${t.description} — ฿${Number(t.amount_thb).toLocaleString()}`,
            }))}
          />
          {transferCandidates.length === 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              No unlinked transfer transactions on this page.
            </Text>
          )}
        </Space>
      </Modal>
    </div>
  )
}

export default Transactions
