/** TypeScript interfaces for the document/OCR domain. */

export type OcrJobStatus = 'pending' | 'processing' | 'review' | 'committed' | 'failed'
export type StagingReviewStatus = 'pending' | 'edited' | 'confirmed' | 'discarded'

export interface OcrJob {
  id: string
  original_name: string
  file_size_bytes: number
  status: OcrJobStatus
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  committed_at: string | null
  created_at: string
}

export interface StagingRow {
  id: string
  ocr_job_id: string
  sort_order: number
  review_status: StagingReviewStatus
  account_id: string | null
  category_id: string | null
  amount_thb: number | null
  original_amount: number | null
  original_currency: string | null
  payment_method: string | null
  transaction_type: string | null
  description: string | null
  transaction_date: string | null
  tags: string[]
  /** Per-field confidence 0.0–1.0 */
  confidence: Record<string, number>
  raw_text: string | null
}
