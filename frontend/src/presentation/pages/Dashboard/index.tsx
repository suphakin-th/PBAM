import React, { useCallback, useEffect } from 'react'
import { Card, DatePicker, Row, Col, Statistic, Space, Typography } from 'antd'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Position,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useFinanceStore } from '@/application/stores/financeStore'

const { RangePicker } = DatePicker
const { Title } = Typography

// Row Y positions — top-to-bottom layout.
// Each node type occupies a horizontal row; edges flow strictly top → bottom.
// Transfer nodes are split (__in above income, __out below expenses) so that
// every edge points downward with zero upward crossings.
const ROW_Y = {
  transfer_in:      -220,
  income_source:       0,
  account:           300,
  expense_category:  600,
  transfer_out:      820,
}

const NODE_W = 210  // horizontal gap between nodes in the same row

/**
 * Top-to-bottom hierarchical layout with horizontal barycenter sort.
 *
 * Why top-to-bottom?
 *   With a single income source fanning out to 6 accounts, a left-to-right
 *   layout stacks all 6 edges on the same vertical line → they overlap
 *   completely.  Rotating 90° spreads those edges *horizontally*, so they
 *   diverge from the source and never overlap.
 *
 * Algorithm:
 *   1. Pin accounts evenly in a horizontal row (the anchor).
 *   2. Sort income / expenses by their barycenter X (avg X of neighbours).
 *   3. Center each row around the accounts row midpoint so the diagram
 *      looks balanced.
 *   4. Transfer nodes are placed directly above/below their connected
 *      account's average X.
 */
function buildLayout(flowTree: { nodes: any[]; edges: any[] }): { nodes: Node[]; edges: Edge[] } {
  const byType = (t: string) => flowTree.nodes.filter(n => n.node_type === t)

  const accountNodes  = byType('account')
  const incomeNodes   = byType('income_source')
  const expenseNodes  = byType('expense_category')
  const transferNodes = byType('transfer')
  const transferIds   = new Set(transferNodes.map(n => n.id))

  const transferSends    = new Set<string>()
  const transferReceives = new Set<string>()
  flowTree.edges.forEach(e => {
    if (transferIds.has(e.source_id)) transferSends.add(e.source_id)
    if (transferIds.has(e.target_id)) transferReceives.add(e.target_id)
  })

  // ── 1. Pin accounts horizontally (the anchor row) ─────────────────────
  const accountX: Record<string, number> = {}
  accountNodes.forEach((n, i) => { accountX[n.id] = i * NODE_W })
  const accountsMidX = (accountNodes.length - 1) * NODE_W / 2

  // ── 2. Horizontal barycenter helper ───────────────────────────────────
  const bary = (id: string, refX: Record<string, number>, asSource: boolean): number => {
    const xs = flowTree.edges
      .filter(e => (asSource ? e.source_id : e.target_id) === id)
      .map(e => refX[asSource ? e.target_id : e.source_id])
      .filter((x): x is number => x !== undefined)
    return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : accountsMidX
  }

  // ── 3. Sort income by barycenter X, center row on accounts midpoint ───
  incomeNodes.sort((a, b) => bary(a.id, accountX, true) - bary(b.id, accountX, true))
  const incomeOffX = accountsMidX - (incomeNodes.length - 1) * NODE_W / 2
  const incomeX: Record<string, number> = {}
  incomeNodes.forEach((n, i) => { incomeX[n.id] = incomeOffX + i * NODE_W })

  // ── 4. Sort expenses by barycenter X, center row on accounts midpoint ─
  expenseNodes.sort((a, b) => bary(a.id, accountX, false) - bary(b.id, accountX, false))
  const expenseOffX = accountsMidX - (expenseNodes.length - 1) * NODE_W / 2
  const expenseX: Record<string, number> = {}
  expenseNodes.forEach((n, i) => { expenseX[n.id] = expenseOffX + i * NODE_W })

  // ── 5. Transfer nodes: x = barycenter of connected accounts ──────────
  const tInX: Record<string, number>  = {}
  const tOutX: Record<string, number> = {}
  transferNodes.forEach(n => {
    if (transferSends.has(n.id))    tInX[n.id]  = bary(n.id, accountX, true)
    if (transferReceives.has(n.id)) tOutX[n.id] = bary(n.id, accountX, false)
  })

  // ── 6. Build ReactFlow nodes ──────────────────────────────────────────
  const makeLabel = (n: any, dimmed = false) => (
    <div style={{ textAlign: 'center', fontSize: 12, lineHeight: 1.4 }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{n.label}</div>
      <div style={{ fontSize: 10, color: dimmed ? 'rgba(255,255,255,0.75)' : '#888' }}>
        ฿{Number(n.total_thb).toLocaleString('th-TH', { minimumFractionDigits: 0 })}
      </div>
    </div>
  )

  const rfNodes: Node[] = []

  flowTree.nodes.forEach(n => {
    if (n.node_type === 'transfer') {
      const base = {
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        style: {
          background: n.color ?? '#722ed1',
          border: '1px solid rgba(114,46,209,0.4)',
          borderRadius: 8,
          padding: '8px 12px',
          minWidth: 140,
          color: '#fff',
        },
      }
      if (transferSends.has(n.id))
        rfNodes.push({ ...base, id: `${n.id}__in`,  position: { x: tInX[n.id]  ?? accountsMidX, y: ROW_Y.transfer_in  }, data: { label: makeLabel(n, true) } })
      if (transferReceives.has(n.id))
        rfNodes.push({ ...base, id: `${n.id}__out`, position: { x: tOutX[n.id] ?? accountsMidX, y: ROW_Y.transfer_out }, data: { label: makeLabel(n, true) } })
    } else {
      const y = ROW_Y[n.node_type as keyof typeof ROW_Y] ?? 0
      const x = n.node_type === 'income_source' ? (incomeX[n.id]  ?? accountsMidX)
              : n.node_type === 'account'        ? (accountX[n.id] ?? 0)
              : (expenseX[n.id] ?? accountsMidX)
      rfNodes.push({
        id: n.id,
        position: { x, y },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        data: { label: makeLabel(n) },
        style: {
          background: n.color ?? '#fff',
          border: '1px solid rgba(0,0,0,0.15)',
          borderRadius: 8,
          padding: '8px 12px',
          minWidth: 140,
          color: n.node_type === 'account' ? '#fff' : '#222',
        },
      })
    }
  })

  // ── 8. Build edges — remap transfer IDs to their split virtual nodes ──
  const amounts = flowTree.edges.map((e) => Number(e.amount_thb))
  const maxAmt  = Math.max(...amounts, 1)

  const rfEdges: Edge[] = flowTree.edges.map((e, idx) => {
    const amt      = Number(e.amount_thb)
    const logScale = Math.log(amt + 1) / Math.log(maxAmt + 1)
    const stroke   = e.label === 'Transfer' ? '#722ed1' : '#1677ff'

    // Transfer sources map to __in (left node); transfer targets map to __out (right node)
    const source = transferIds.has(e.source_id) ? `${e.source_id}__in`  : e.source_id
    const target = transferIds.has(e.target_id) ? `${e.target_id}__out` : e.target_id

    return {
      id: `edge-${idx}`,
      source,
      target,
      label: `฿${amt.toLocaleString('th-TH', { maximumFractionDigits: 0 })}`,
      labelStyle: { fontSize: 10, fill: '#555' },
      labelBgStyle: { fill: '#fff', fillOpacity: 0.85 },
      labelBgPadding: [4, 4] as [number, number],
      labelBgBorderRadius: 4,
      animated: logScale > 0.15,
      style: {
        stroke,
        strokeWidth:   1 + logScale * 5,
        strokeOpacity: 0.35 + logScale * 0.5,
      },
      type: 'smoothstep',
    }
  })

  return { nodes: rfNodes, edges: rfEdges }
}

const Dashboard: React.FC = () => {
  const { flowTree, fetchFlowTree, isLoading } = useFinanceStore()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    fetchFlowTree()
  }, [fetchFlowTree])

  useEffect(() => {
    if (!flowTree) return
    const { nodes: n, edges: e } = buildLayout(flowTree)
    setNodes(n)
    setEdges(e)
  }, [flowTree, setNodes, setEdges])

  const onDateChange = useCallback((dates: any) => {
    if (dates) {
      fetchFlowTree({
        date_from: dates[0].format('YYYY-MM-DD'),
        date_to: dates[1].format('YYYY-MM-DD'),
      })
    } else {
      fetchFlowTree()
    }
  }, [fetchFlowTree])

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>Money Flow</Title>
          </Col>
          <Col>
            <RangePicker onChange={onDateChange} />
          </Col>
        </Row>

        {flowTree && (
          <Row gutter={16}>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Total Income"
                  value={Number(flowTree.total_income_thb)}
                  prefix="฿"
                  precision={2}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Total Expense"
                  value={Number(flowTree.total_expense_thb)}
                  prefix="฿"
                  precision={2}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Net"
                  value={Number(flowTree.net_thb)}
                  prefix="฿"
                  precision={2}
                  valueStyle={{ color: Number(flowTree.net_thb) >= 0 ? '#52c41a' : '#ff4d4f' }}
                />
              </Card>
            </Col>
          </Row>
        )}

        <Card
          title="Income → Account → Expenses"
          loading={isLoading}
          style={{ height: 620 }}
          styles={{ body: { height: 'calc(100% - 56px)', padding: 0 } }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={2}
            deleteKeyCode={null}
          >
            <Background gap={20} color="#f0f0f0" />
            <Controls />
            <MiniMap nodeStrokeWidth={3} zoomable pannable />
          </ReactFlow>
        </Card>
      </Space>
    </div>
  )
}

export default Dashboard
