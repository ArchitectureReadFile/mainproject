import json
import logging

from redis import Redis

from domains.chat.reference_payload import build_chat_reference_payloads
from domains.chat.repository import ChatRepository
from domains.knowledge.answer_context_builder import AnswerContextBuilder
from domains.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from domains.knowledge.schemas import KnowledgeRetrievalRequest, WorkspaceSelection
from domains.notification.repository import NotificationRepository
from domains.notification.service import NotificationService
from errors import (
    AppException,
    ErrorCode,
    FailureStage,
    build_exception_failure_payload,
    build_failure_payload,
)
from infra.llm.client import LLMClient
from models.model import ChatMessage, ChatMessageRole, NotificationType
from prompts.chat_prompt import CHAT_SUMMARY_PROMPT, CHAT_SYSTEM_PROMPT
from settings.knowledge import DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K

logger = logging.getLogger(__name__)


class ChatProcessor:
    """대화 기록, retrieval, LLM 생성, 알림 저장을 하나의 처리 흐름으로 묶는다."""

    def __init__(
        self, chat_repo: ChatRepository, notification_repo: NotificationRepository
    ):
        self.chat_repo = chat_repo
        self.notification_repo = notification_repo
        self.llm_client = LLMClient()
        self.knowledge_retrieval = KnowledgeRetrievalService()
        self.answer_context_builder = AnswerContextBuilder()
        self.notification_service = NotificationService(notification_repo)

    def process_chat(
        self,
        redis_client: Redis,
        user_id: int,
        session_id: int,
        group_id: int | None = None,
        workspace_selection: WorkspaceSelection | None = None,
    ):
        """단일 세션 질문을 처리하고 진행 상태를 Redis pub/sub로 전파한다."""
        self._publish_status(
            redis_client, session_id, user_id, "processing", "답변을 생성중입니다..."
        )

        try:
            session = self.chat_repo.get_session_by_id_and_user(session_id, user_id)

            if not session:
                raise AppException(ErrorCode.CHAT_ROOM_NOT_FOUND)

            reference = getattr(session, "reference", None)
            reference_status = getattr(reference, "status", None)
            if (
                reference is not None
                and getattr(reference_status, "value", reference_status) == "READY"
                and reference.extracted_text
            ):
                doc_context = reference.extracted_text
                doc_title = reference.title or None
                doc_chunks = list(getattr(reference, "chunks", []) or [])
            else:
                doc_context = ""
                doc_title = None
                doc_chunks = []

            summary_key = f"chat_summary:{session_id}"
            last_msg_key = f"chat_last_summarized_id:{session_id}"

            existing_summary = redis_client.get(summary_key) or ""
            if isinstance(existing_summary, bytes):
                existing_summary = existing_summary.decode("utf-8")

            last_id_str = redis_client.get(last_msg_key)
            last_id = int(last_id_str) if last_id_str else 0

            unsummarized_msgs = self.chat_repo.get_unsummarized_messages(
                session_id, last_id
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

            system_content = CHAT_SYSTEM_PROMPT

            if existing_summary:
                system_content += f"\n\n[이전 대화 핵심 요약]\n{existing_summary}"

            if recent_msgs:
                user_query = recent_msgs[-1].content
                logger.info("[RETRIEVAL_START] query=%s", user_query[:100])
                references: list[dict[str, object]] = []
                # 사용자 응답은 계속 진행하되, source별 retrieval 실패는 metadata에 남긴다.
                retrieval_failures: list[dict[str, object]] = []

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
                        session_reference_text=doc_context,
                        session_reference_chunks=doc_chunks,
                        session_title=doc_title,
                        failure_metadata=retrieval_failures,
                    )
                    logger.info("[RETRIEVAL_DONE] items=%d", len(items))
                    references = build_chat_reference_payloads(items)

                    rag_context = self.answer_context_builder.build(items)
                    if rag_context:
                        logger.info("[CONTEXT_BUILT] chars=%d", len(rag_context))
                        system_content += f"\n\n{rag_context}"
                except Exception as e:
                    failure = build_exception_failure_payload(
                        stage=FailureStage.RETRIEVE,
                        exc=e,
                        fallback_error_code=ErrorCode.CHAT_RETRIEVAL_FAILED,
                        status="error",
                    )
                    logger.warning(
                        "[CHAT_FAILURE] stage=%s code=%s message=%s raw_error=%s",
                        failure["failure_stage"],
                        failure["failure_code"],
                        failure["error_message"],
                        e,
                    )
                    references = []
                    retrieval_failures = [failure]
            else:
                references = []
                retrieval_failures = []

            chat_messages = [{"role": "system", "content": system_content.strip()}]

            for msg in recent_msgs:
                role_str = "user" if msg.role == ChatMessageRole.USER else "assistant"
                chat_messages.append({"role": role_str, "content": msg.content})

            full_answer = self._generate_llm_response(
                redis_client, session_id, user_id, chat_messages, references
            )

            if full_answer:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role=ChatMessageRole.ASSISTANT,
                    content=full_answer,
                    metadata_json=(
                        json.dumps(
                            {
                                **({"references": references} if references else {}),
                                **(
                                    {"retrieval_failures": retrieval_failures}
                                    if retrieval_failures
                                    else {}
                                ),
                            },
                            ensure_ascii=False,
                        )
                        if references or retrieval_failures
                        else None
                    ),
                )
                self.chat_repo.add_message(ai_msg)
                self.chat_repo.commit()

                preview = full_answer.strip()
                if len(preview) > 150:
                    preview = preview[:150] + "..."

                self.notification_service.create_notification_sync(
                    user_id=user_id,
                    type=NotificationType.AI_ANSWER_COMPLETE,
                    title="AI 답변이 완료되었습니다.",
                    body=preview,
                    group_id=group_id,
                    target_type="chat",
                    target_id=session_id,
                )

        except AppException as ae:
            self._publish_error(
                redis_client,
                session_id,
                user_id,
                stage=FailureStage.PROCESS,
                error_code=ae.error_code,
            )
        except Exception as e:
            logger.error(
                "[PROCESS_CHAT_FAILED] stage=%s error=%s",
                FailureStage.PROCESS.value,
                e,
                exc_info=True,
            )
            self._publish_error(
                redis_client,
                session_id,
                user_id,
                stage=FailureStage.PROCESS,
                error_code=ErrorCode.CHAT_HISTORY_LOAD_FAILED,
            )

    def _summarize_dialogue(self, existing_summary: str, new_dialogue: str) -> str:
        """대화 일부를 축약 요약으로 치환한다."""
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
        self,
        redis_client: Redis,
        session_id: int,
        user_id: int,
        messages: list,
        references: list[dict[str, object]] | None = None,
    ) -> str:
        """LLM 스트림을 누적하고 중간 상태를 pub/sub로 브로드캐스트한다."""
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
            self._publish_error(
                redis_client,
                session_id,
                user_id,
                stage=FailureStage.GENERATE,
                error_code=ae.error_code,
            )
            return ""
        except Exception as e:
            logger.error(
                "[CHAT_GENERATE_FAILED] stage=%s error=%s",
                FailureStage.GENERATE.value,
                e,
                exc_info=True,
            )
            self._publish_error(
                redis_client,
                session_id,
                user_id,
                stage=FailureStage.GENERATE,
                error_code=ErrorCode.LLM_ALL_PROFILES_FAILED,
            )
            return ""

        self._publish_status(
            redis_client,
            session_id,
            user_id,
            "complete",
            full_answer,
            references=references or [],
        )
        return full_answer

    def _publish_status(
        self,
        redis_client: Redis,
        session_id: int,
        user_id: int,
        status: str,
        message: str,
        *,
        references: list[dict[str, object]] | None = None,
    ):
        """채팅 상태 이벤트를 Redis pub/sub 채널로 발행한다."""
        payload = {"status": status, "message": message}
        if references:
            payload["references"] = references
        redis_client.publish(f"chat:{session_id}:{user_id}", json.dumps(payload))

    def _publish_error(
        self,
        redis_client: Redis,
        session_id: int,
        user_id: int,
        *,
        stage: FailureStage,
        error_code: ErrorCode,
    ):
        """실패 payload를 표준 형식으로 발행한다."""
        payload = build_failure_payload(
            stage=stage,
            error_code=error_code,
            status="error",
            include_legacy_error_fields=True,
        )
        redis_client.publish(f"chat:{session_id}:{user_id}", json.dumps(payload))
