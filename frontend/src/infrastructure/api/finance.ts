import { apiClient } from './client'
import type {
  Account,
  FlowTree,
  Transaction,
  TransactionCategory,
  TransactionComment,
  TransactionGroup,
  TransactionListResponse,
} from '@/domain/finance'

export const accountsApi = {
  list: () => apiClient.get<Account[]>('/accounts'),
  create: (data: Omit<Account, 'id' | 'created_at'>) => apiClient.post<Account>('/accounts', data),
  update: (id: string, data: Partial<Account>) => apiClient.patch<Account>(`/accounts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/accounts/${id}`),
}

export const categoriesApi = {
  list: () => apiClient.get<TransactionCategory[]>('/categories'),
  create: (data: object) => apiClient.post<TransactionCategory>('/categories', data),
  update: (id: string, data: object) => apiClient.patch<TransactionCategory>(`/categories/${id}`, data),
  delete: (id: string) => apiClient.delete(`/categories/${id}`),
}

export const transactionsApi = {
  list: (params?: object) => apiClient.get<TransactionListResponse>('/transactions', { params }),
  create: (data: object) => apiClient.post<Transaction>('/transactions', data),
  update: (id: string, data: object) => apiClient.patch<Transaction>(`/transactions/${id}`, data),
  delete: (id: string) => apiClient.delete(`/transactions/${id}`),
  linkTransfer: (id: string, pairId: string) =>
    apiClient.post<Transaction>(`/transactions/${id}/link-transfer/${pairId}`),
  unlinkTransfer: (id: string) => apiClient.delete(`/transactions/${id}/link-transfer`),
  flowTree: (params?: { date_from?: string; date_to?: string }) =>
    apiClient.get<FlowTree>('/transactions/flow-tree', { params }),
  listComments: (txId: string) => apiClient.get<TransactionComment[]>(`/transactions/${txId}/comments`),
  addComment: (txId: string, content: string) =>
    apiClient.post<TransactionComment>(`/transactions/${txId}/comments`, { content }),
  deleteComment: (txId: string, commentId: string) =>
    apiClient.delete(`/transactions/${txId}/comments/${commentId}`),
}

export const groupsApi = {
  list: () => apiClient.get<TransactionGroup[]>('/groups'),
  create: (data: object) => apiClient.post<TransactionGroup>('/groups', data),
  addMember: (groupId: string, txId: string) =>
    apiClient.post(`/groups/${groupId}/members/${txId}`),
  removeMember: (groupId: string, txId: string) =>
    apiClient.delete(`/groups/${groupId}/members/${txId}`),
}
