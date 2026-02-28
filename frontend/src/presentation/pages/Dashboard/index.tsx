import React, { useCallback, useEffect, useMemo } from 'react'
import { Card, DatePicker, Row, Col, Statistic, Space, Typography } from 'antd'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useFinanceStore } from '@/application/stores/financeStore'

const { RangePicker } = DatePicker
const { Title } = Typography

// X column per node type
const TYPE_X: Record<string, number> = {
  income_source: 0,
  account: 380,
  expense_category: 760,
  transfer: 380,
}

function buildLayout(flowTree: { nodes: any[]; edges: any[] }): { nodes: Node[]; edges: Edge[] } {
  // Group nodes by type so each column starts at y=0
  const typeCounters: Record<string, number> = {}

  const rfNodes: Node[] = flowTree.nodes.map((n) => {
    const col = typeCounters[n.node_type] ?? 0
    typeCounters[n.node_type] = col + 1
    const x = TYPE_X[n.node_type] ?? 0
    const y = col * 110

    return {
      id: n.id,
      position: { x, y },
      data: {
        label: (
          <div style={{ textAlign: 'center', fontSize: 12, lineHeight: 1.4 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>{n.label}</div>
            <div style={{ color: '#888', fontSize: 10 }}>
              ฿{Number(n.total_thb).toLocaleString('th-TH', { minimumFractionDigits: 0 })}
            </div>
          </div>
        ),
      },
      style: {
        background: n.color ?? '#fff',
        border: '1px solid rgba(0,0,0,0.15)',
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 140,
        color: n.node_type === 'account' ? '#fff' : '#222',
      },
    }
  })

  const rfEdges: Edge[] = flowTree.edges.map((e, idx) => ({
    id: `edge-${idx}`,
    source: e.source_id,
    target: e.target_id,
    // Show amount only when hovering (use tooltip label)
    label: `฿${Number(e.amount_thb).toLocaleString('th-TH', { maximumFractionDigits: 0 })}`,
    labelStyle: { fontSize: 10, fill: '#555' },
    labelBgStyle: { fill: '#fff', fillOpacity: 0.85 },
    labelBgPadding: [4, 4] as [number, number],
    labelBgBorderRadius: 4,
    animated: true,
    style: { stroke: e.label === 'Transfer' ? '#722ed1' : '#1677ff', strokeWidth: 1.5 },
    type: 'smoothstep',
  }))

  return { nodes: rfNodes, edges: rfEdges }
}

const Dashboard: React.FC = () => {
  const { flowTree, fetchFlowTree, isLoading } = useFinanceStore()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    fetchFlowTree()
  }, [fetchFlowTree])

  // Rebuild layout whenever flowTree data changes
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
