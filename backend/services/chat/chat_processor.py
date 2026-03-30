import json
import logging

from redis import Redis
from sqlalchemy.orm import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import ChatMessage, ChatMessageRole, ChatSession, NotificationType
from prompts.chat_prompt import CHAT_SUMMARY_PROMPT, CHAT_SYSTEM_PROMPT
from repositories.notification_repository import NotificationRepository
from services.summary.llm_client import LLMClient
from services.notification_service import NotificationService
from schemas.knowledge import KnowledgeRetrievalRequest, WorkspaceSelection
from services.knowledge.answer_context_builder import AnswerContextBuilder
from services.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from services.summary.llm_client import LLMClient
from settings.knowledge import DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K

logger = logging.getLogger(__name__)


class ChatProcessor:
    def __init__(self):
        self.llm_client = LLMClient()
        self.knowledge_retrieval = KnowledgeRetrievalService()
        self.answer_context_builder = AnswerContextBuilder()

    def process_chat(
        self,
        db: Session,
        redis_client: Redis,
        user_id: int,
        session_id: int,
        group_id: int | None = None,
        workspace_selection: WorkspaceSelection | None = None,
    ):
        """
        group_id / workspace_selection:
            - 미전달: include_workspace=False (기존 동작 유지)
            - 전달 시: include_workspace=True

        주의: WorkspaceKnowledgeRetriever의 mode="documents" 필터는
              현재 미구현(fail-closed → 빈 결과). 추후 지원 예정.
        """
        self._publish_status(
            redis_client, session_id, user_id, "processing", "답변을 생성중입니다..."
        )

        try:
            session = (
                db.query(ChatSession)
                .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
                .first()
            )

            if not session:
                raise AppException(ErrorCode.CHAT_ROOM_NOT_FOUND)

            doc_context = session.reference_document_text or ""
            doc_title = session.reference_document_title or None

            # ── 대화 요약 (redis) ─────────────────────────────────────────────
            summary_key = f"chat_summary:{session_id}"
            last_msg_key = f"chat_last_summarized_id:{session_id}"

            existing_summary = redis_client.get(summary_key) or ""
            if isinstance(existing_summary, bytes):
                existing_summary = existing_summary.decode("utf-8")

            last_id_str = redis_client.get(last_msg_key)
            last_id = int(last_id_str) if last_id_str else 0

            unsummarized_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id, ChatMessage.id > last_id)
                .order_by(ChatMessage.id.asc())
                .all()
            )

            if len(unsummarized_msgs) > 15:
                msgs_to_summarize = unsummarized_msgs[:10]
                recent_msgs = unsummarized_msgs[10:]

                dialogue_to_summarize = ""
                for msg in msgs_to_summarize:
                    role_str = "사용자" if msg.role == ChatMessageRole.USER else "AI"
                    dialogue_to_summarize += f"{role_str}: {msg.content}\n"

                new_summary = self._summarize_dialogue(
                    existing_summary, dialogue_to_summarize
                )

                redis_client.set(summary_key, new_summary)
                redis_client.set(last_msg_key, msgs_to_summarize[-1].id)

                existing_summary = new_summary
            else:
                recent_msgs = unsummarized_msgs

            # ── system prompt 기본 조립 ───────────────────────────────────────
            system_content = CHAT_SYSTEM_PROMPT

            if existing_summary:
                system_content += f"\n\n[이전 대화 핵심 요약]\n{existing_summary}"

            # ── retrieval ─────────────────────────────────────────────────────
            if recent_msgs:
                user_query = recent_msgs[-1].content
                logger.info("[RETRIEVAL_START] query=%s", user_query[:100])

                include_workspace = workspace_selection is not None
                request = KnowledgeRetrievalRequest(
                    query=user_query,
                    user_id=user_id,
                    session_id=session_id,
                    group_id=group_id,
                    include_platform=True,
                    include_workspace=include_workspace,
                    include_session=bool(doc_context.strip()),
                    workspace_selection=(
                        workspace_selection
                        if workspace_selection is not None
                        else WorkspaceSelection()
                    ),
                    top_k=DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K,
                )

                try:
                    items = self.knowledge_retrieval.retrieve(
                        request,
                        reference_document_text=doc_context,
                        session_title=doc_title,
                    )
                    logger.info("[RETRIEVAL_DONE] items=%d", len(items))

                    rag_context = self.answer_context_builder.build(items)
                    if rag_context:
                        logger.info("[CONTEXT_BUILT] chars=%d", len(rag_context))
                        system_content += f"\n\n{rag_context}"
                except Exception as e:
                    logger.warning("[RETRIEVAL_FAILED] %s", e)

            logger.info("[FINAL_SYSTEM_PROMPT] %s...", system_content[:2000])
            chat_messages = [{"role": "system", "content": system_content.strip()}]

            for msg in recent_msgs:
                role_str = "user" if msg.role == ChatMessageRole.USER else "assistant"
                chat_messages.append({"role": role_str, "content": msg.content})

            full_answer = self._generate_llm_response(
                redis_client, session_id, user_id, chat_messages
            )

            if full_answer:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role=ChatMessageRole.ASSISTANT,
                    content=full_answer,
                )
                db.add(ai_msg)
                db.commit()

                notification_repo = NotificationRepository(db)
                notification_service = NotificationService()
                preview = full_answer.strip()
                if len(preview) > 150:
                    preview = preview[:150] + "..."

                notification_service.create_notification_sync(
                    notification_repo,
                    user_id=user_id,
                    type=NotificationType.AI_ANSWER_COMPLETE,
                    title="AI 답변이 완료되었습니다.",
                    body=preview,
                    group_id=group_id,
                    target_type="chat",
                    target_id=session_id
                )

        except AppException as ae:
            self._publish_error(redis_client, session_id, user_id, ae.error_code)
        except Exception as e:
            logger.error("[PROCESS_CHAT_FAILED] %s", e, exc_info=True)
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.CHAT_HISTORY_LOAD_FAILED
            )

    def _summarize_dialogue(self, existing_summary: str, new_dialogue: str) -> str:
        prompt = CHAT_SUMMARY_PROMPT.format(
            existing_summary=existing_summary or "기존 요약 없음",
            new_dialogue=new_dialogue,
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            return self.llm_client.summarize_chat(messages, num_predict=512)
        except Exception:
            return existing_summary

    def _generate_llm_response(
        self, redis_client: Redis, session_id: int, user_id: int, messages: list
    ) -> str:
        full_answer = ""
        try:
            for chunk in self.llm_client.stream_chat(messages, num_predict=2048):
                word = chunk.get("message", {}).get("content", "")
                if word:
                    full_answer += word
                    self._publish_status(
                        redis_client,
                        session_id,
                        user_id,
                        "streaming",
                        full_answer,
                    )
        except AppException as ae:
            self._publish_error(redis_client, session_id, user_id, ae.error_code)
            return ""
        except Exception:
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.LLM_ALL_PROFILES_FAILED
            )
            return ""

        self._publish_status(redis_client, session_id, user_id, "complete", full_answer)
        return full_answer

    def _publish_status(
        self,
        redis_client: Redis,
        session_id: int,
        user_id: int,
        status: str,
        message: str,
    ):
        payload = {"status": status, "message": message}
        redis_client.publish(f"chat:{session_id}:{user_id}", json.dumps(payload))

    def _publish_error(
        self, redis_client: Redis, session_id: int, user_id: int, error_code: ErrorCode
    ):
        payload = {
            "status": "error",
            "code": error_code.code,
            "message": error_code.message,
        }
        redis_client.publish(f"chat:{session_id}:{user_id}", json.dumps(payload))
