import client from '@/shared/api/client'

// ── 개요 ──────────────────────────────────────────────────────────────────────

export async function fetchAdminStats() {
  const res = await client.get('/admin/stats')
  return res.data
}

// ── 사용량 ────────────────────────────────────────────────────────────────────

export async function fetchAdminUsage() {
  const res = await client.get('/admin/usage')
  return res.data
}

// ── platform sync ────────────────────────────────────────────────────────────

export async function fetchAdminPlatformSummary() {
  const res = await client.get('/admin/platform/summary')
  return res.data
}

export async function syncAdminPlatform({ source_type }) {
  const res = await client.post('/admin/platform/sync', { source_type })
  return res.data
}

export async function stopAdminPlatform({ source_type }) {
  const res = await client.post('/admin/platform/sync/stop', { source_type })
  return res.data
}

export async function fetchAdminPlatformFailures({ source_type, run_id, limit = 20 } = {}) {
  const params = { limit }
  if (source_type) params.source_type = source_type
  if (run_id != null) params.run_id = run_id
  const res = await client.get('/admin/platform/failures', { params })
  return res.data
}

// ── 회원 ──────────────────────────────────────────────────────────────────────

export async function fetchAdminUsers({ search = '', plan = '', skip = 0, limit = 20 } = {}) {
  const res = await client.get('/admin/users', { params: { search, plan, skip, limit } })
  return res.data
}

export async function updateAdminUser(user_id, payload) {
  const res = await client.patch(`/admin/users/${user_id}`, payload)
  return res.data
}
