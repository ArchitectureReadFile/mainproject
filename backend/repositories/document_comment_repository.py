from sqlalchemy.orm import Session, joinedload, selectinload

from models.model import DocumentComment, utc_now_naive


class DocumentCommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_root_comments_by_document_id(
        self, document_id: int
    ) -> list[DocumentComment]:
        """
        문서의 루트 댓글 목록을 생성일 오름차순으로 조회
        replies와 작성자 정보까지 함께 로드
        """
        return (
            self.db.query(DocumentComment)
            .options(
                joinedload(DocumentComment.author),
                joinedload(DocumentComment.deleted_by),
                selectinload(DocumentComment.replies).joinedload(
                    DocumentComment.author
                ),
                selectinload(DocumentComment.replies).joinedload(
                    DocumentComment.deleted_by
                ),
            )
            .filter(
                DocumentComment.document_id == document_id,
                DocumentComment.parent_id.is_(None),
            )
            .order_by(DocumentComment.created_at.asc(), DocumentComment.id.asc())
            .all()
        )

    def get_comment_by_id(self, comment_id: int) -> DocumentComment | None:
        """
        댓글 ID로 단건 조회
        """
        return (
            self.db.query(DocumentComment)
            .options(
                joinedload(DocumentComment.author),
                joinedload(DocumentComment.parent),
                joinedload(DocumentComment.document),
            )
            .filter(DocumentComment.id == comment_id)
            .first()
        )

    def create_comment(
        self,
        *,
        document_id: int,
        author_user_id: int,
        content: str,
        parent_id: int | None = None,
    ) -> DocumentComment:
        """
        댓글 또는 대댓글을 생성
        """
        comment = DocumentComment(
            document_id=document_id,
            author_user_id=author_user_id,
            content=content,
            parent_id=parent_id,
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def soft_delete_comment(
        self,
        comment: DocumentComment,
        *,
        deleted_by_user_id: int,
    ) -> DocumentComment:
        """
        댓글을 soft delete 처리
        """
        comment.deleted_at = utc_now_naive()
        comment.deleted_by_user_id = deleted_by_user_id
        comment.updated_at = utc_now_naive()
        self.db.commit()
        self.db.refresh(comment)
        return comment
