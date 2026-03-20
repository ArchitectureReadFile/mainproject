// TODO: 그룹/워크스페이스 API
import client from "./client";


// GET    /api/groups/:group_id/members 멤버 목록
// POST   /api/groups/:group_id/members 멤버 초대(OWNER, ADMIN)
// PATCH  /api/groups/:group_id/members/:user_id 권한 변경
// DELETE /api/groups/:group_id/members/:user_id 멤버 추방


// POST   /api/groups 그룹 생성
export async function createGroup({ name, description }) {
    const { data } = await client.post("/groups", { name, description })
    return data
}


// GET   /api/groups 내가 속한 그룹 목록 조회
export async function getMyGroups() {
    const { data } = await client.get("/groups")
    return data
}


// GET    /api/groups/:group_id 그룹 상세
export async function getGroupDetail(groupId) {
    const { data } = await client.get(`/groups/${groupId}`)
    return data
}


// DELETE /api/groups/:group_id 그룹 삭제 요청
export async function requestDeleteGroup(groupId) {
    const { data } = await client.delete(`/groups/${groupId}`)
    return data
}


// POST   /api/groups/:group_id/cancel-delete 그룹 삭제 취소
export async function cancelDeleteGroup(groupId) {
    const { data } = await client.post(`/groups/${groupId}/cancel-delete`)
    return data
}