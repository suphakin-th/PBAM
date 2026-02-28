import { apiClient } from './client'
import type { OcrJob, StagingRow } from '@/domain/document'

export const ocrApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<OcrJob>('/ocr/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => apiClient.get<OcrJob[]>('/ocr'),
  getJob: (id: string) => apiClient.get<OcrJob>(`/ocr/${id}`),
  getStaging: (jobId: string) => apiClient.get<StagingRow[]>(`/ocr/${jobId}/staging`),
  updateStagingRow: (jobId: string, rowId: string, updates: Partial<StagingRow>) =>
    apiClient.patch<StagingRow>(`/ocr/${jobId}/staging/${rowId}`, updates),
  discardStagingRow: (jobId: string, rowId: string) =>
    apiClient.delete(`/ocr/${jobId}/staging/${rowId}`),
  commit: (jobId: string, defaultAccountId: string) =>
    apiClient.post<{ committed_count: number; job_id: string }>(`/ocr/${jobId}/commit`, {
      default_account_id: defaultAccountId,
    }),
}
