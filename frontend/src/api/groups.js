// TODO: 그룹/워크스페이스 API
import client from "./client";

// POST   /api/groups 그룹 생성
export async function createGroup({ name, description }) {
    const { data } = await client.post("/groups", { name, description })
    return data
}


// GET   /api/groups 내가 속한 그룹 목록 조회
export async function getMyGroups() {
    const { data } = await client.get("/groups")
    return {
        groups: data.groups ?? [],
        has_blocked_owned_group: Boolean(data.has_blocked_owned_group),
        blocked_owned_group_reason: data.blocked_owned_group_reason ?? null,
    }
}


// GET /groups/invitations — 내 초대 목록
export async function getMyInvitations() {
    const { data } = await client.get('/groups/invitations')
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


// GET    /api/groups/:group_id/members 멤버 목록
export async function getMembers(groupId) {
    const { data } = await client.get(`/groups/${groupId}/members`)
    return data
}


// POST   /api/groups/:group_id/members 멤버 초대(OWNER, ADMIN)
export async function inviteMember(groupId, { username, role }) {
    const { data } = await client.post(`/groups/${groupId}/members`, { username, role })
    return data
}


// POST /api/groups/:group_id/members/accept 초대 수락
export async function acceptInvite(groupId) {
    await client.post(`/groups/${groupId}/members/accept`)
}


// POST /api/groups/:group_id/members/decline 초대 거절
export async function declineInvite(groupId) {
    await client.post(`/groups/${groupId}/members/decline`)
}


// DELETE /api/groups/:group_id/members/:user_id 멤버 추방
export async function removeMember(groupId, targetId) {
    await client.delete(`/groups/${groupId}/members/${targetId}`)
}


// PATCH  /api/groups/:group_id/members/:user_id 권한 변경
export async function changeMemberRole(groupId, targetId, role) {
    await client.patch(`/groups/${groupId}/members/${targetId}`, { role })
}

// POST /api/groups/:group_id/members/:target_id/transfer — 오너 양도
export async function transferOwner(groupId, targetId) {
    await client.post(`/groups/${groupId}/members/${targetId}/transfer`)
}

// GET /groups/{group_id}/documents 그룹 기반 문서 목록 조회
export async function getGroupDocuments(groupId, {
    skip = 0,
    limit = 5,
    keyword = "",
    status = "",
    viewType = "all",
    category = "전체",
}) {
    const { data } = await client.get(`/groups/${groupId}/documents`, {
        params: {
            skip,
            limit,
            keyword,
            status,
            view_type: viewType,
            category,
        },
    })
    return data
}


// GET /groups/{group_id}/documents/deleted — 휴지통 목록
export async function getDeletedGroupDocuments(groupId, {
    skip = 0,
    limit = 5,
}) {
    const { data } = await client.get(`/groups/${groupId}/documents/deleted`, {
        params: {
            skip,
            limit,
        },
    })
    return data
}


// GET /groups/{group_id}/documents/{doc_id} — 그룹 문서 상세
export async function getGroupDocumentDetail(groupId, docId) {
    const { data } = await client.get(`/groups/${groupId}/documents/${docId}`)
    return data
}


export function getGroupDocumentOriginalUrl(groupId, docId) {
    return `/api/groups/${groupId}/documents/${docId}/original`
}


// DELETE /groups/{group_id}/documents/{doc_id} — 문서 삭제
export async function deleteGroupDocument(groupId, docId) {
    await client.delete(`/groups/${groupId}/documents/${docId}`)
}

export async function getPendingDocuments(
    groupId,
    {
        skip = 0,
        limit = 20,
        keyword = '',
        uploader = '',
        assigneeType = 'all',
    } = {}
) {
    const { data } = await client.get(`/groups/${groupId}/documents/pending`, {
        params: {
            skip,
            limit,
            keyword,
            uploader,
            assignee_type: assigneeType,
        },
    })
    return data
}


/**
 * 문서 댓글 목록을 조회
 */
export async function getDocumentComments(groupId, docId) {
    const { data } = await client.get(`/groups/${groupId}/documents/${docId}/comments`)
    return data
}

/**
 * 문서 댓글 또는 대댓글을 생성
 * 루트 댓글일 때는 PDF 위치 좌표를 함께 전달
 */
export async function createDocumentComment(groupId, docId, payload) {
    const { data } = await client.post(`/groups/${groupId}/documents/${docId}/comments`, payload)
    return data
}

/**
 * 문서 댓글을 삭제
 */
export async function deleteDocumentComment(groupId, commentId) {
    const { data } = await client.delete(`/groups/${groupId}/comments/${commentId}`)
    return data
}


export async function restoreGroupDocument(groupId, docId) {
  await client.post(`/groups/${groupId}/documents/${docId}/restore`)
}

export async function getPendingUploaders(groupId) {
  const { data } = await client.get(`/groups/${groupId}/documents/pending/uploaders`)
  return data
}


export async function getApprovedDocuments(
    groupId,
    {
        skip = 0,
        limit = 10,
        keyword = '',
        uploader = '',
    } = {}
) {
    const { data } = await client.get(`/groups/${groupId}/documents/approved`, {
        params: {
            skip,
            limit,
            keyword,
            uploader,
        },
    })
    return data
}


export async function getApprovedUploaders(groupId) {
  const { data } = await client.get(`/groups/${groupId}/documents/approved/uploaders`)
  return data
}


export async function getRejectedDocuments(
    groupId,
    {
        skip = 0,
        limit = 10,
        keyword = '',
        uploader = '',
    } = {}
) {
    const { data } = await client.get(`/groups/${groupId}/documents/rejected`, {
        params: {
            skip,
            limit,
            keyword,
            uploader,
        },
    })
    return data
}


export async function getRejectedUploaders(groupId) {
  const { data } = await client.get(`/groups/${groupId}/documents/rejected/uploaders`)
  return data
}

export async function approveDocument(groupId, docId) {
    const { data } = await client.post(`/groups/${groupId}/documents/${docId}/approve`)
    return data
}

export async function rejectDocument(groupId, docId, feedback) {
    const { data } = await client.post(`/groups/${groupId}/documents/${docId}/reject`, {
        feedback,
    })
    return data
}


export async function leaveGroup(groupId) {
    await client.post(`/groups/${groupId}/leave`)
}


