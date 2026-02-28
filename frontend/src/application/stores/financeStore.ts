import { create } from 'zustand'
import type { Account, FlowTree, Transaction, TransactionCategory } from '@/domain/finance'
import { accountsApi, categoriesApi, transactionsApi } from '@/infrastructure/api/finance'

interface FinanceState {
  accounts: Account[]
  categories: TransactionCategory[]
  transactions: Transaction[]
  transactionTotal: number
  flowTree: FlowTree | null
  isLoading: boolean
  fetchAccounts: () => Promise<void>
  fetchCategories: () => Promise<void>
  fetchTransactions: (params?: { page?: number; pageSize?: number; [key: string]: unknown }) => Promise<void>
  fetchFlowTree: (params?: { date_from?: string; date_to?: string }) => Promise<void>
}

export const useFinanceStore = create<FinanceState>((set) => ({
  accounts: [],
  categories: [],
  transactions: [],
  transactionTotal: 0,
  flowTree: null,
  isLoading: false,

  fetchAccounts: async () => {
    const { data } = await accountsApi.list()
    set({ accounts: data })
  },

  fetchCategories: async () => {
    const { data } = await categoriesApi.list()
    set({ categories: data })
  },

  fetchTransactions: async (params) => {
    set({ isLoading: true })
    try {
      const { page = 1, pageSize = 50, ...rest } = params ?? {}
      const offset = (page - 1) * pageSize
      const { data } = await transactionsApi.list({ limit: pageSize, offset, ...rest })
      set({ transactions: data.items, transactionTotal: data.total })
    } finally {
      set({ isLoading: false })
    }
  },

  fetchFlowTree: async (params) => {
    set({ isLoading: true })
    try {
      const { data } = await transactionsApi.flowTree(params)
      set({ flowTree: data })
    } finally {
      set({ isLoading: false })
    }
  },
}))
