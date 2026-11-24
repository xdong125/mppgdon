export interface Api {
  get(path: string, options?: Record<string, unknown>): Promise<unknown>
  post(path: string, data: unknown, options?: Record<string, unknown>): Promise<unknown>
}
export interface Envelope<T> {success: boolean; message: string; data: T | null}
export interface Status {
  enabled: boolean; version: string; pansou_url: string; token_set: boolean; config_error: string
  sync_mode?: 'unavailable' | 'dry_run' | 'live'; sync_error?: string
  transfer_mode?: 'unavailable' | 'dry_run' | 'live'; transfer_error?: string
}
export interface SyncResult {status: 'dry_run' | 'accepted' | 'unknown' | 'rejected' | 'not_sent'}
export interface TransferResult extends SyncResult {attempt_id: string | null; retryable: boolean}
export interface DuplicateRecord {
  title: string; source: string; published: string; quality: string; origin: 'grouped' | 'raw'
}
export interface Item {
  id: string; title: string; url: string; password: string; source: string; published: string
  quality: string; episode: string; collection: boolean; password_conflict: boolean
  duplicate_records?: DuplicateRecord[]
  sync_ticket?: string | null
  transfer_ticket?: string | null
  sync_target?: {mp_path: string; cms_path: string; kind: 'movie' | 'tv'; season: number | null; reason: string} | null
  sync_error?: string
}
export interface Results {keyword: string; items: Item[]; raw_115: number; duplicates: number; filtered: number; truncated: boolean}
