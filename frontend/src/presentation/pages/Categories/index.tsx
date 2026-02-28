import React, { useEffect, useState } from 'react'
import {
  Tree,
  Button,
  Modal,
  Form,
  Input,
  Select,
  ColorPicker,
  Space,
  Typography,
  Tag,
  Popconfirm,
  message,
  Tooltip,
} from 'antd'
import { PlusOutlined, PlusCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import { useFinanceStore } from '@/application/stores/financeStore'
import type { TransactionCategory } from '@/domain/finance'
import { categoriesApi } from '@/infrastructure/api/finance'

const { Title, Text } = Typography

interface CreateModalState {
  open: boolean
  parentId: string | null
  defaultType: 'income' | 'expense' | 'transfer' | null
}

function buildTreeData(
  categories: TransactionCategory[],
  onAddChild: (cat: TransactionCategory) => void,
  onDelete: (cat: TransactionCategory) => void
): DataNode[] {
  return categories.map((cat) => ({
    key: cat.id,
    title: (
      <Space size={6} style={{ padding: '2px 0' }}>
        {cat.color && (
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: cat.color,
              flexShrink: 0,
            }}
          />
        )}
        <Text style={{ flex: 1 }}>{cat.name}</Text>
        <Tag
          color={cat.category_type === 'income' ? 'green' : cat.category_type === 'expense' ? 'red' : 'blue'}
          style={{ fontSize: 10, margin: 0 }}
        >
          {cat.category_type}
        </Tag>
        <Tooltip title="Add sub-category">
          <Button
            type="text"
            size="small"
            icon={<PlusCircleOutlined />}
            onClick={(e) => { e.stopPropagation(); onAddChild(cat) }}
            style={{ opacity: 0.6 }}
          />
        </Tooltip>
        {!cat.is_system && (
          <Popconfirm
            title="Delete this category?"
            description="Child categories will become root-level."
            onConfirm={(e) => { e?.stopPropagation(); onDelete(cat) }}
            onCancel={(e) => e?.stopPropagation()}
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
              style={{ opacity: 0.6 }}
            />
          </Popconfirm>
        )}
      </Space>
    ),
    children: cat.children.length ? buildTreeData(cat.children, onAddChild, onDelete) : undefined,
  }))
}

const Categories: React.FC = () => {
  const { categories, fetchCategories } = useFinanceStore()
  const [modalState, setModalState] = useState<CreateModalState>({ open: false, parentId: null, defaultType: null })
  const [form] = Form.useForm()
  const [selectedType, setSelectedType] = useState<string | undefined>(undefined)

  useEffect(() => {
    fetchCategories()
  }, [fetchCategories])

  const openCreate = () => {
    setSelectedType(undefined)
    form.resetFields()
    setModalState({ open: true, parentId: null, defaultType: null })
  }

  const openAddChild = (parent: TransactionCategory) => {
    setSelectedType(parent.category_type)
    form.resetFields()
    form.setFieldsValue({ category_type: parent.category_type, parent_id: parent.id })
    setModalState({ open: true, parentId: parent.id, defaultType: parent.category_type })
  }

  const closeModal = () => {
    setModalState({ open: false, parentId: null, defaultType: null })
    form.resetFields()
    setSelectedType(undefined)
  }

  const handleDelete = async (cat: TransactionCategory) => {
    try {
      await categoriesApi.delete(cat.id)
      message.success(`"${cat.name}" deleted`)
      await fetchCategories()
    } catch {
      message.error('Delete failed')
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await categoriesApi.create({
        name: values.name,
        category_type: values.category_type,
        color: values.color?.toHexString?.() ?? values.color ?? null,
        parent_id: values.parent_id ?? null,
      })
      await fetchCategories()
      closeModal()
    } catch {
      message.error('Create failed')
    }
  }

  // Flatten categories for parent selector
  const flatCategories: TransactionCategory[] = []
  const flatten = (cats: TransactionCategory[]) => {
    for (const cat of cats) {
      flatCategories.push(cat)
      if (cat.children.length) flatten(cat.children)
    }
  }
  flatten(categories)

  // Filter parent options by the currently selected type (must match)
  const parentOptions = flatCategories
    .filter((c) => !selectedType || c.category_type === selectedType)
    .map((c) => ({ value: c.id, label: c.name }))

  const treeData = buildTreeData(categories, openAddChild, handleDelete)
  const isChildModal = modalState.parentId !== null

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space>
          <Title level={3} style={{ margin: 0 }}>Categories</Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            New Category
          </Button>
        </Space>

        {categories.length === 0 ? (
          <Text type="secondary">No categories yet. Create your first one.</Text>
        ) : (
          <Tree
            treeData={treeData}
            defaultExpandAll
            showLine
            blockNode
          />
        )}
      </Space>

      <Modal
        title={isChildModal ? 'Add sub-category' : 'New Category'}
        open={modalState.open}
        onCancel={closeModal}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}>
            <Input placeholder="e.g. Groceries, Salary, Rent" />
          </Form.Item>

          <Form.Item name="category_type" label="Type" rules={[{ required: true, message: 'Type is required' }]}>
            <Select
              placeholder="Select type"
              disabled={isChildModal}
              onChange={(v) => {
                setSelectedType(v)
                form.setFieldValue('parent_id', undefined)
              }}
              options={[
                { value: 'income', label: 'Income — money coming in' },
                { value: 'expense', label: 'Expense — money going out' },
                { value: 'transfer', label: 'Transfer — between accounts' },
              ]}
            />
          </Form.Item>

          <Form.Item
            name="parent_id"
            label={
              <Space>
                Parent category
                <Text type="secondary" style={{ fontSize: 12 }}>(optional)</Text>
              </Space>
            }
          >
            <Select
              allowClear
              placeholder={
                selectedType
                  ? `Select a ${selectedType} parent`
                  : 'Select type first'
              }
              disabled={!selectedType || isChildModal}
              options={parentOptions}
            />
          </Form.Item>

          <Form.Item name="color" label="Color (optional)">
            <ColorPicker format="hex" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Categories
