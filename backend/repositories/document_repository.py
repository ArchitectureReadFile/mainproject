import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from models.model import (
    Document,
    DocumentApproval,
    DocumentComment,
    DocumentCommentScope,
    DocumentLifecycleStatus,
    DocumentPreviewStatus,
    DocumentStatus,
    GroupMember,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    Summary,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_member_status_map(
        self,
        *,
        group_id: int,
        user_ids: list[int],
    ) -> dict[int, MembershipStatus]:
        """
        그룹 내 사용자별 멤버십 상태 맵을 반환
        문서 목록/상세 표시명 가공에 사용
        """
        if not user_ids:
            return {}

        rows = (
            self.db.query(GroupMember.user_id, GroupMember.status)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id.in_(user_ids),
            )
            .all()
        )

        return {user_id: status for user_id, status in rows}

    def is_group_admin(self, user_id: int, group_id: int) -> bool:
        """
        사용자가 그룹 OWNER/ADMIN 권한인지 확인
        """
        return (
            self.db.query(GroupMember.id)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.ACTIVE,
                GroupMember.role.in_([MembershipRole.OWNER, MembershipRole.ADMIN]),
            )
            .first()
            is not None
        )

    def create_document_approval(
        self,
        *,
        document_id: int,
        assignee_user_id: Optional[int] = None,
        reviewer_user_id: Optional[int] = None,
        status: ReviewStatus,
        feedback: Optional[str] = None,
        reviewed_at=None,
    ) -> DocumentApproval:
        """
        업로드 직후 문서 승인 레코드를 생성
        """
        approval = DocumentApproval(
            document_id=document_id,
            status=status,
            assignee_user_id=assignee_user_id,
            reviewer_user_id=reviewer_user_id,
            feedback=feedback,
            reviewed_at=reviewed_at,
        )
        self.db.add(approval)
        self.db.flush()
        return approval

    def create_pending_document(
        self,
        *,
        group_id: int,
        uploader_user_id: int,
        original_filename: str,
        stored_path: str,
        original_content_type: str | None = None,
    ) -> Document:
        """
        원본 업로드 직후 PENDING 상태 문서를 생성
        """
        document = Document(
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=original_filename,
            stored_path=stored_path,
            original_content_type=original_content_type,
            preview_pdf_path=None,
            preview_status=DocumentPreviewStatus.PENDING,
            processing_status=DocumentStatus.PENDING,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def update_status(self, document_id: int, status: DocumentStatus):
        """
        문서 요약/처리 상태를 갱신
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.processing_status = status
            return
        logger.warning(
            "[Document 상태 변경 누락] document_id=%s, status=%s", document_id, status
        )

    def update_classification(
        self,
        document_id: int,
        *,
        document_type: str,
        category: str,
    ) -> None:
        """분류 결과를 Document에 저장한다. 수동 수정도 이 메서드를 경유한다."""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.document_type = document_type
            document.category = category
            return
        logger.warning("[Document 분류 저장 누락] document_id=%s", document_id)

    def update_preview_status(
        self,
        document_id: int,
        status: DocumentPreviewStatus,
        preview_pdf_path: str | None = None,
    ) -> None:
        """
        preview PDF 준비 상태와 경로를 갱신
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.warning(
                "[Document preview 상태 변경 누락] document_id=%s, status=%s",
                document_id,
                status,
            )
            return

        document.preview_status = status
        if preview_pdf_path is not None:
            document.preview_pdf_path = preview_pdf_path

    def claim_next_pending_document(self) -> Document | None:
        """
        처리 대기 중인 다음 문서를 점유하고 PROCESSING 으로 전환
        """
        document = (
            self.db.query(Document)
            .filter(
                Document.processing_status == DocumentStatus.PENDING,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
            )
            .order_by(Document.created_at.asc(), Document.id.asc())
            .first()
        )
        if not document:
            return None

        document.processing_status = DocumentStatus.PROCESSING
        self.db.flush()
        return document

    def get_list(
        self,
        skip,
        limit,
        keyword,
        status,
        user_id,
        view_type,
        category,
        group_id=None,
    ):
        """
        문서 목록을 조회하고 카드 표시용 일반 댓글 수를 함께 집계.
        삭제된 댓글과 REVIEW 범위 댓글은 제외.
        category 필터는 Document.category 컬럼 직접 비교.
        """
        comment_count_subquery = (
            self.db.query(
                DocumentComment.document_id.label("document_id"),
                func.count(DocumentComment.id).label("comment_count"),
            )
            .filter(
                DocumentComment.comment_scope == DocumentCommentScope.GENERAL.value,
                DocumentComment.deleted_at.is_(None),
            )
            .group_by(DocumentComment.document_id)
            .subquery()
        )

        query = (
            self.db.query(
                Document,
                func.coalesce(comment_count_subquery.c.comment_count, 0).label(
                    "comment_count"
                ),
            )
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
            )
            .outerjoin(Document.summary)
            .outerjoin(
                comment_count_subquery,
                comment_count_subquery.c.document_id == Document.id,
            )
            .filter(Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE)
        )

        if group_id is not None:
            query = query.filter(Document.group_id == group_id)

        if view_type == "my":
            query = query.filter(Document.uploader_user_id == user_id)
        else:
            query = query.join(Document.approval).filter(
                DocumentApproval.status == ReviewStatus.APPROVED
            )

        if category and category != "전체":
            query = query.filter(Document.category == category)

        if keyword:
            query = query.filter(
                or_(
                    Document.original_filename.contains(keyword),
                    Summary.summary_text.contains(keyword),
                )
            )

        if status:
            query = query.filter(Document.processing_status == status)

        total = query.count()

        if view_type == "my":
            documents = (
                query.order_by(Document.created_at.desc(), Document.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
        else:
            documents = (
                query.order_by(
                    DocumentApproval.reviewed_at.desc(),
                    Document.created_at.desc(),
                    Document.id.desc(),
                )
                .offset(skip)
                .limit(limit)
                .all()
            )

        return documents, total

    def get_unclassified_list(
        self,
        group_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """
        미분류 문서 목록 반환.
        document_type 또는 category 중 하나라도 미분류/NULL인 문서를 반환한다.
        운영에서 재처리 대상을 식별하는 용도로 사용한다.
        """
        query = (
            self.db.query(Document)
            .filter(
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                Document.group_id == group_id,
                or_(
                    Document.document_type.is_(None),
                    Document.document_type == "미분류",
                    Document.category.is_(None),
                    Document.category == "미분류",
                ),
            )
            .order_by(Document.created_at.desc(), Document.id.desc())
        )

        total = query.count()
        documents = query.offset(skip).limit(limit).all()
        return documents, total

    def get_detail(self, doc_id: int):
        """
        문서 상세 조회에 필요한 연관 데이터를 함께 불러옴
        """
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.summary),
                joinedload(Document.owner),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.deleted_by),
            )
            .filter(Document.id == doc_id)
            .first()
        )

    def get_by_id(self, document_id: int) -> Document | None:
        """
        문서 ID로 단건 조회
        """
        return self.db.query(Document).filter(Document.id == document_id).first()

    def delete_document(self, document: Document, user_id: int) -> None:
        """
        문서를 삭제 대기 상태로 전환
        """
        now = utc_now_naive()
        document.lifecycle_status = DocumentLifecycleStatus.DELETE_PENDING
        document.delete_requested_at = now
        document.delete_scheduled_at = now + timedelta(days=7)
        document.deleted_by_user_id = user_id
        self.db.commit()

    def restore_document(self, document: Document) -> None:
        """
        삭제 대기 문서를 복구
        """
        document.lifecycle_status = DocumentLifecycleStatus.ACTIVE
        document.delete_requested_at = None
        document.delete_scheduled_at = None
        document.deleted_by_user_id = None
        self.db.commit()

    def get_deleted_list(
        self,
        skip,
        limit,
        user_id,
        group_id=None,
    ) -> tuple[list[Document], int]:
        query = (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
            )
            .filter(Document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING)
        )

        if group_id is not None:
            query = query.filter(Document.group_id == group_id)

        query = query.filter(
            or_(
                Document.uploader_user_id == user_id,
                self.db.query(GroupMember.id)
                .filter(
                    GroupMember.group_id == Document.group_id,
                    GroupMember.user_id == user_id,
                    GroupMember.status == MembershipStatus.ACTIVE,
                    GroupMember.role.in_([MembershipRole.OWNER, MembershipRole.ADMIN]),
                )
                .exists(),
            )
        )

        total = query.count()

        documents = (
            query.order_by(Document.delete_requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return documents, total
