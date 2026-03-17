/** TypeScript interfaces mirroring the finance domain entities. */

export type AccountType = 'bank' | 'cash' | 'credit_card' | 'savings' | 'investment'
export type TransactionType = 'income' | 'expense' | 'transfer'
export type CategoryType = 'income' | 'expense' | 'transfer'

export interface Account {
  id: string
  name: string
  account_type: AccountType
  currency: string
  is_active: boolean
  created_at: string
}

export interface TransactionCategory {
  id: string
  name: string
  category_type: CategoryType
  parent_id: string | null
  color: string | null
  icon: string | null
  sort_order: number
  is_system: boolean
  children: TransactionCategory[]
}

export interface Transaction {
  id: string
  account_id: string
  category_id: string | null
  payment_method: string | null
  counterparty_ref: string | null
  counterparty_name: string | null
  transfer_pair_id: string | null
  amount_thb: number
  original_amount: number | null
  original_currency: string | null
  transaction_type: TransactionType
  description: string
  transaction_date: string
  tags: string[]
  is_recurring: boolean
  /** OCR metadata — includes transaction_time (HH:MM) when imported from a PDF */
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface TransactionListResponse {
  items: Transaction[]
  total: number
  limit: number
  offset: number
}

export interface TransactionComment {
  id: string
  transaction_id: string
  content: string
  created_at: string
  updated_at: string
}

export interface TransactionGroup {
  id: string
  name: string
  description: string | null
  color: string | null
  created_at: string
}

// Flow tree types for visualization
export interface FlowNode {
  id: string
  label: string
  node_type: 'income_source' | 'account' | 'expense_category' | 'transfer'
  total_thb: number
  color: string | null
  icon: string | null
}

export interface FlowEdge {
  source_id: string
  target_id: string
  amount_thb: number
  label: string | null
}

export interface FlowTree {
  nodes: FlowNode[]
  edges: FlowEdge[]
  total_income_thb: number
  total_expense_thb: number
  net_thb: number
}

// ── Summary types ─────────────────────────────────────────────────────────────

export interface CategoryStat {
  category_id: string
  name: string
  color: string | null
  icon: string | null
  total_thb: number
  count: number
  percentage: number
}

export interface MonthlyPoint {
  month: string
  income_thb: number
  expense_thb: number
  net_thb: number
  count: number
}

export interface AccountStat {
  account_id: string
  name: string
  account_type: AccountType
  currency: string
  balance_thb: number
  period_income_thb: number
  period_expense_thb: number
}

export interface PaymentMethodStat {
  method: string
  total_thb: number
  count: number
  percentage: number
}

export interface Summary {
  date_from: string | null
  date_to: string | null
  total_income_thb: number
  total_expense_thb: number
  net_thb: number
  transaction_count: number
  uncategorized_count: number
  recurring_count: number
  monthly_trend: MonthlyPoint[]
  top_expense_categories: CategoryStat[]
  top_income_categories: CategoryStat[]
  accounts: AccountStat[]
  payment_methods: PaymentMethodStat[]
}
