import client from "@/api/client";

// ── 개요 ──────────────────────────────────────────────────────────────────────

export async function fetchAdminStats() {
  const res = await client.get("/admin/stats");
  return res.data;
}

// ── 사용량 ────────────────────────────────────────────────────────────────────

export async function fetchAdminUsage() {
  const res = await client.get("/admin/usage");
  return res.data;
}

// ── 판례 ──────────────────────────────────────────────────────────────────────

export async function fetchAdminPrecedents({ skip = 0, limit = 20 } = {}) {
  const res = await client.get("/admin/precedents", { params: { skip, limit } });
  return res.data;
}

export async function createPrecedent(source_url) {
  const res = await client.post("/admin/precedents", { source_url });
  return res.data;
}

export async function retryPrecedent(precedent_id) {
  const res = await client.post(`/admin/precedents/${precedent_id}/retry`);
  return res.data;
}

export async function reindexPrecedents() {
  const res = await client.post("/admin/precedents/reindex");
  return res.data;
}

// ── 회원 ──────────────────────────────────────────────────────────────────────

export async function fetchAdminUsers({ search = "", plan = "", skip = 0, limit = 20 } = {}) {
  const res = await client.get("/admin/users", { params: { search, plan, skip, limit } });
  return res.data;
}

export async function updateAdminUserStatus(user_id, is_active) {
  const res = await client.patch(`/admin/users/${user_id}`, { is_active });
  return res.data;
}
