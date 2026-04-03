from sqlalchemy.orm import Session, joinedload, selectinload

from models.model import (
    DocumentComment,
    DocumentCommentMention,
    utc_now_naive,
)


class DocumentCommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_root_comments_by_document_id(
        self, document_id: int
    ) -> list[DocumentComment]:
        """
        문서의 루트 댓글 목록을 생성일 오름차순으로 조회
        replies, 작성자, 멘션 정보까지 함께 로드
        """
        return (
            self.db.query(DocumentComment)
            .options(
                joinedload(DocumentComment.author),
                joinedload(DocumentComment.deleted_by),
                selectinload(DocumentComment.mentions).joinedload(
                    DocumentCommentMention.mentioned_user
                ),
                selectinload(DocumentComment.replies).joinedload(
                    DocumentComment.author
                ),
                selectinload(DocumentComment.replies).joinedload(
                    DocumentComment.deleted_by
                ),
                selectinload(DocumentComment.replies)
                .selectinload(DocumentComment.mentions)
                .joinedload(DocumentCommentMention.mentioned_user),
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
                selectinload(DocumentComment.mentions).joinedload(
                    DocumentCommentMention.mentioned_user
                ),
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
        self.db.flush()
        return comment

    def create_comment_mentions(
        self,
        *,
        comment_id: int,
        mentions: list[dict],
    ) -> list[DocumentCommentMention]:
        """
        댓글 멘션 목록을 생성
        """
        rows: list[DocumentCommentMention] = []

        for mention in mentions:
            row = DocumentCommentMention(
                comment_id=comment_id,
                mentioned_user_id=mention["mentioned_user_id"],
                snapshot_username=mention["snapshot_username"],
                start_index=mention["start_index"],
                end_index=mention["end_index"],
            )
            self.db.add(row)
            rows.append(row)

        self.db.flush()
        return rows

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
        self.db.flush()
        return comment
