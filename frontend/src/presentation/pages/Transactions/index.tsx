import React, { useCallback, useEffect, useMemo, useState } from 'react'
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

/**
 * Try to extract a counterparty label from a Thai bank-statement description.
 * Handles patterns like:
 *   "รับโอนจาก KBANK x0244 บจก. เอ็กโซโกร"
 *   "โอนจาก SCB x7290 นาย สุภกิณห์ ธิวง"
 *   "จาก KBANK x1234 บริษัท เอบีซี"
 *
 * Returns { label, isInternal } or null when the pattern is not recognised.
 * isInternal = true when the source bank maps to one of the user's own accounts.
 */
function parseCounterpartyFromDescription(
  description: string,
  accountNames: string[],
): { label: string; isInternal: boolean } | null {
  // Full pattern: KEYWORD + BANK_CODE + REF + NAME
  const full = description.match(
    /(?:รับโอนจาก|โอนเงินจาก|โอนจาก|transferred\s+from)\s+([A-Za-z]+)\s+\S+\s+([\S\s]+)/i,
  )
  if (full) {
    const bankCode = full[1].trim()
    const name     = full[2].trim()
    if (name) {
      const lBank = bankCode.toLowerCase()
      // Check if the source bank keyword matches one of the user's account names
      const matchedAcc = accountNames.find((acc) => {
        const lAcc = acc.toLowerCase()
        return lAcc.includes(lBank) || lBank.includes(lAcc.split(' ')[0])
      })
      if (matchedAcc) {
        // Source bank is user's own account — but is the name a company (external payee)?
        const isCompany = /บจก\.|หจก\.|บริษัท|corp\b|co\.|ltd\b/i.test(name)
        if (isCompany) return { label: name, isInternal: false }
        return { label: matchedAcc, isInternal: true }
      }
      // External bank — show the extracted name
      return { label: name, isInternal: false }
    }
  }

  // Shorter pattern: "จาก NAME" (no bank ref)
  const short = description.match(/(?:^|\s)จาก\s+([\u0E00-\u0E7Fa-zA-Z][\S\s]+)/i)
  if (short) {
    const name = short[1].trim()
    if (name && name.length >= 2) return { label: name, isInternal: false }
  }

  return null
}

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

// Score how well a category NAME matches a transaction description (0 = no match)
function matchScore(description: string, catName: string): number {
  const desc = description.toLowerCase()
  const name = catName.toLowerCase()
  if (desc.includes(name)) return 2
  const words = name.split(/\s+/).filter((w) => w.length >= 2)
  if (words.some((w) => desc.includes(w))) return 1
  return 0
}

// Score similarity between two transaction DESCRIPTIONS (for learned suggestions)
// Returns 0–4; values > 0 are boosted by +10 to take priority over name-based scores
function learnedMatchScore(a: string, b: string): number {
  const da = a.toLowerCase().trim()
  const db = b.toLowerCase().trim()
  if (!da || !db) return 0
  if (da === db) return 4
  if (da.includes(db) || db.includes(da)) return 3
  // Shared prefix ≥ 10 chars (recurring payments often start the same way)
  if (da.length >= 10 && db.length >= 10 && da.slice(0, 10) === db.slice(0, 10)) return 3
  // Word overlap
  const setA = new Set(da.split(/[\s\W]+/).filter((w) => w.length >= 3))
  const wordsB = db.split(/[\s\W]+/).filter((w) => w.length >= 3)
  const overlap = wordsB.filter((w) => setA.has(w)).length
  if (overlap >= 2) return 2
  if (overlap >= 1) return 1
  return 0
}

const ColorDot: React.FC<{ color?: string | null }> = ({ color }) =>
  color ? (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
      }}
    />
  ) : null

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
  const [bulkApproving, setBulkApproving] = useState(false)

  // Comments drawer
  const [commentDrawerOpen, setCommentDrawerOpen] = useState(false)
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null)
  const [comments, setComments] = useState<TransactionComment[]>([])
  const [newComment, setNewComment] = useState('')
  const [commentLoading, setCommentLoading] = useState(false)

  // Inline counterparty editor (for when both counterparty_name & ref are null and parsing fails)
  const [editingCpId, setEditingCpId]     = useState<string | null>(null)
  const [editingCpValue, setEditingCpValue] = useState('')

  const startEditCp = (tx: Transaction) => {
    setEditingCpId(tx.id)
    setEditingCpValue(tx.counterparty_name ?? '')
  }

  const saveCounterparty = async (tx: Transaction) => {
    const trimmed = editingCpValue.trim()
    setEditingCpId(null)
    if (!trimmed || trimmed === (tx.counterparty_name ?? '')) return
    try {
      await transactionsApi.update(tx.id, { counterparty_name: trimmed })
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch {
      message.error('Failed to save counterparty')
    }
  }

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
  // Index current-page transactions by id so linked transfer pairs can be resolved
  const txById = useMemo(
    () => Object.fromEntries(transactions.map((t) => [t.id, t])),
    [transactions]
  )
  const flatCats = useMemo(() => flattenCategories(categories), [categories])
  const catMap = useMemo(
    () => Object.fromEntries(flatCats.map((c) => [c.id, c])),
    [flatCats]
  )

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  // ── Learned suggestion engine ────────────────────────────────────────────────
  // Pre-build: categoryId → list of descriptions of already-categorized transactions
  // so that build/compute functions can learn from the user's past choices.
  const learnedDescsByCat = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const tx of transactions) {
      if (!tx.category_id) continue
      const list = map.get(tx.category_id) ?? []
      list.push(tx.description)
      map.set(tx.category_id, list)
    }
    return map
  }, [transactions])

  // Build dropdown options for one transaction.
  // Scoring: learned match (11–14) > name match (1–2).
  const buildCategoryOptions = useCallback(
    (tx: Transaction) => {
      const eligible = flatCats.filter((c) => c.category_type === tx.transaction_type)

      const scored = eligible.map((c) => {
        // 1. Category-name match (existing heuristic)
        let score = matchScore(tx.description, c.name)
        let isLearned = false

        // 2. Learned from the user's past choices for this category
        for (const refDesc of learnedDescsByCat.get(c.id) ?? []) {
          const ls = learnedMatchScore(tx.description, refDesc)
          if (ls > 0 && ls + 10 > score) {
            score = ls + 10
            isLearned = true
          }
        }

        return { cat: c, score, isLearned }
      })

      // Suggestions first, then alphabetical
      scored.sort((a, b) => b.score - a.score || a.cat.name.localeCompare(b.cat.name))

      return scored.map(({ cat, score, isLearned }) => ({
        value: cat.id,
        score,
        label: (
          <Space size={4}>
            <ColorDot color={cat.color} />
            {cat.name}
            {score > 0 && (
              <Tooltip
                title={
                  isLearned
                    ? 'Suggested — similar to a transaction you already categorized'
                    : 'Suggested — category name matches description'
                }
              >
                <BulbOutlined
                  style={{ color: isLearned ? '#52c41a' : '#faad14', fontSize: 12 }}
                />
              </Tooltip>
            )}
          </Space>
        ),
        searchLabel: cat.name,
      }))
    },
    [flatCats, learnedDescsByCat]
  )

  // Compute the single best suggested category for a transaction (null if none)
  const computeSuggestedCategory = useCallback(
    (tx: Transaction): string | null => {
      if (tx.category_id) return null
      const eligible = flatCats.filter((c) => c.category_type === tx.transaction_type)
      let bestId: string | null = null
      let bestScore = 0

      for (const c of eligible) {
        let score = matchScore(tx.description, c.name)
        for (const refDesc of learnedDescsByCat.get(c.id) ?? []) {
          const ls = learnedMatchScore(tx.description, refDesc)
          if (ls > 0 && ls + 10 > score) score = ls + 10
        }
        if (score > bestScore) {
          bestScore = score
          bestId = c.id
        }
      }

      return bestScore > 0 ? bestId : null
    },
    [flatCats, learnedDescsByCat]
  )

  // All uncategorized transactions on this page that have at least one suggestion
  const pendingSuggestions = useMemo(
    () =>
      transactions
        .filter((tx) => !tx.category_id)
        .map((tx) => ({ tx, catId: computeSuggestedCategory(tx) }))
        .filter((s): s is { tx: Transaction; catId: string } => s.catId !== null),
    [transactions, computeSuggestedCategory]
  )

  // ── Category assignment ─────────────────────────────────────────────────────

  const handleCategoryChange = async (tx: Transaction, categoryId: string | null) => {
    try {
      await transactionsApi.update(tx.id, { category_id: categoryId })
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch {
      message.error('Failed to update category')
    }
  }

  const handleTypeChange = async (tx: Transaction, newType: string) => {
    if (newType === tx.transaction_type) return
    try {
      await transactionsApi.update(tx.id, { transaction_type: newType })
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch {
      message.error('Failed to update transaction type')
    }
  }

  const handleApproveAll = async () => {
    setBulkApproving(true)
    try {
      await Promise.all(
        pendingSuggestions.map(({ tx, catId }) =>
          transactionsApi.update(tx.id, { category_id: catId })
        )
      )
      message.success(
        `Applied ${pendingSuggestions.length} category suggestion${pendingSuggestions.length !== 1 ? 's' : ''}`
      )
      fetchTransactions({ page, pageSize: PAGE_SIZE })
    } catch {
      message.error('Some category updates failed')
    } finally {
      setBulkApproving(false)
    }
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
      width: 110,
      render: (d: string, record: Transaction) => {
        const pdfTime = record.metadata?.transaction_time as string | undefined
        return (
          <Space direction="vertical" size={0}>
            <Text style={{ fontSize: 13 }}>{dayjs(d).format('DD MMM YY')}</Text>
            {pdfTime && (
              <Text type="secondary" style={{ fontSize: 11 }}>{pdfTime}</Text>
            )}
          </Space>
        )
      },
      sorter: (a, b) => a.transaction_date.localeCompare(b.transaction_date),
      defaultSortOrder: 'descend',
    },
    {
      title: 'Source → Destination',
      key: 'flow',
      width: 290,
      render: (_: unknown, record: Transaction) => {
        const thisAcc     = accountMap[record.account_id]
        const accNames    = Object.values(accountMap).map((a) => a.name)

        // Resolve the "other party" label and whether it is an internal account
        let otherLabel: string | null = null
        let isInternal = false
        let isParsed   = false   // true when we inferred the label from description

        if (record.transaction_type === 'transfer' && record.transfer_pair_id) {
          const paired    = txById[record.transfer_pair_id]
          const pairedAcc = paired ? accountMap[paired.account_id] : null
          if (pairedAcc) {
            otherLabel = pairedAcc.name
            isInternal = true
          } else {
            otherLabel = record.counterparty_ref ?? record.counterparty_name ?? null
          }
        } else {
          otherLabel = record.counterparty_name ?? record.counterparty_ref ?? null
        }

        // Fallback: try to extract counterparty from description text
        if (!otherLabel) {
          const parsed = parseCounterpartyFromDescription(record.description, accNames)
          if (parsed) {
            otherLabel = parsed.label
            isInternal = parsed.isInternal
            isParsed   = true
          }
        }

        const arrowColor =
          record.transaction_type === 'income'   ? '#52c41a'
          : record.transaction_type === 'expense' ? '#ff4d4f'
          : '#722ed1'

        const AccTag = ({ name }: { name: string }) => (
          <Tag color="blue" style={{ margin: 0, fontSize: 11, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {name}
          </Tag>
        )

        const OtherEl = () => {
          // Inline editor: shown when user clicks the "—" placeholder
          if (editingCpId === record.id) {
            return (
              <Input
                autoFocus
                size="small"
                value={editingCpValue}
                onChange={(e) => setEditingCpValue(e.target.value)}
                onPressEnter={() => saveCounterparty(record)}
                onBlur={() => saveCounterparty(record)}
                style={{ width: 110, fontSize: 11 }}
                placeholder="Counterparty…"
              />
            )
          }

          if (!otherLabel) {
            // No name known and no parse result → let user type it
            return (
              <Tooltip title="Click to set counterparty">
                <Text
                  type="secondary"
                  style={{ fontSize: 11, cursor: 'pointer', borderBottom: '1px dashed #d9d9d9' }}
                  onClick={() => startEditCp(record)}
                >
                  —
                </Text>
              </Tooltip>
            )
          }

          if (isInternal) {
            return (
              <Tag color="blue" style={{ margin: 0, fontSize: 11, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {otherLabel}
              </Tag>
            )
          }

          // External — show plain text; if inferred from description, add a subtle indicator
          return (
            <Tooltip title={isParsed ? 'Inferred from description — click to correct' : undefined}>
              <Text
                type="secondary"
                style={{
                  fontSize: 11,
                  maxWidth: 120,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: 'inline-block',
                  whiteSpace: 'nowrap',
                  cursor: isParsed ? 'pointer' : 'default',
                  borderBottom: isParsed ? '1px dashed #bfbfbf' : undefined,
                }}
                onClick={isParsed ? () => startEditCp(record) : undefined}
              >
                {otherLabel}
              </Text>
            </Tooltip>
          )
        }

        const thisEl = <AccTag name={thisAcc?.name ?? '—'} />
        const arrow  = <span style={{ color: arrowColor, fontWeight: 700, flexShrink: 0 }}>→</span>

        return (
          <Space size={4} style={{ flexWrap: 'nowrap', alignItems: 'center' }}>
            {record.transaction_type === 'income' ? <OtherEl /> : thisEl}
            {arrow}
            {record.transaction_type === 'income' ? thisEl : <OtherEl />}
          </Space>
        )
      },
    },
    {
      title: 'Description',
      key: 'description',
      render: (_: unknown, record: Transaction) => {
        // Format payment_method key (e.g. "bank_transfer" → "Bank Transfer") for display
        const method = record.payment_method
          ? record.payment_method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
          : null
        return (
          <Space direction="vertical" size={2} style={{ width: '100%' }}>
            <Text style={{ fontSize: 13 }}>{record.description}</Text>
            {method && (
              <Tag style={{ margin: 0, fontSize: 10, lineHeight: '16px' }} color="default">
                {method}
              </Tag>
            )}
          </Space>
        )
      },
    },
    {
      title: 'Type',
      dataIndex: 'transaction_type',
      key: 'type',
      width: 150,
      render: (type: string, record: Transaction) => {
        const tagColor = type === 'income' ? 'green' : type === 'expense' ? 'red' : 'blue'
        const tagLabel = type === 'income' ? 'Income' : type === 'expense' ? 'Expense' : 'Transfer'
        return (
          <Space size={4}>
            <Select
              value={type}
              size="small"
              style={{ width: 120 }}
              onChange={(v) => handleTypeChange(record, v)}
              labelRender={() => (
                <Tag color={tagColor} style={{ margin: 0, cursor: 'pointer' }}>{tagLabel}</Tag>
              )}
              options={[
                { value: 'income',   label: 'Income' },
                { value: 'expense',  label: 'Expense' },
                { value: 'transfer', label: 'Transfer' },
              ]}
            />
            {record.transfer_pair_id && (
              <Tooltip title="Linked transfer">
                <LinkOutlined style={{ color: '#1677ff', fontSize: 11 }} />
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: 'Category',
      dataIndex: 'category_id',
      key: 'category',
      width: 200,
      render: (catId: string | null, record) => {
        const cat = catId ? catMap[catId] : null
        const opts = buildCategoryOptions(record)
        const hasSuggestion = !catId && opts[0]?.score > 0

        return (
          <Select
            value={catId ?? undefined}
            size="small"
            style={{ width: '100%', minWidth: 150 }}
            placeholder={
              hasSuggestion ? (
                <Space size={4}>
                  <BulbOutlined style={{ color: opts[0]?.score >= 11 ? '#52c41a' : '#faad14' }} />
                  <span style={{ color: opts[0]?.score >= 11 ? '#52c41a' : '#faad14' }}>
                    {opts[0]?.score >= 11 ? 'Learned' : 'Suggested'}
                  </span>
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
            labelRender={() =>
              cat ? (
                <Space size={4}>
                  <ColorDot color={cat.color} />
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
        <Space wrap>
          <Title level={3} style={{ margin: 0 }}>Transactions</Title>
          <Button type="primary" icon={<PlusOutlined />}>Add Transaction</Button>
          {pendingSuggestions.length > 0 && (
            <Popconfirm
              title={`Apply ${pendingSuggestions.length} suggestion${pendingSuggestions.length !== 1 ? 's' : ''}?`}
              description={
                <Space direction="vertical" size={2}>
                  <span>Categorize all highlighted transactions using the best match.</span>
                  <span style={{ fontSize: 12, color: '#888' }}>
                    Green bulb = learned from your past choices · Yellow bulb = name match
                  </span>
                </Space>
              }
              onConfirm={handleApproveAll}
              okText="Apply all"
              cancelText="Cancel"
            >
              <Button
                icon={<BulbOutlined style={{ color: '#52c41a' }} />}
                loading={bulkApproving}
              >
                Apply {pendingSuggestions.length} Suggestion{pendingSuggestions.length !== 1 ? 's' : ''}
              </Button>
            </Popconfirm>
          )}
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
          scroll={{ x: 1200 }}
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
