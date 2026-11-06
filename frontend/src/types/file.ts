export interface AdminFile {
  id: number
  name: string
  size: number
  sha256: string
  published: number
  expires: number
  first_sent: number | null
  status: string
  cleanup_error: string
}
