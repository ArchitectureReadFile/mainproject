import json
import logging
from redis import Redis
from sqlalchemy.orm import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import ChatMessage, ChatMessageRole, ChatSession
from prompts.chat_prompt import CHAT_SUMMARY_PROMPT, CHAT_SYSTEM_PROMPT
from schemas.search import SearchMode
from services.rag.retrieval_service import retrieve_precedents
from services.summary.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ChatProcessor:
    def __init__(self):
        self.llm_client = LLMClient()

    def process_chat(
        self, db: Session, redis_client: Redis, user_id: int, session_id: int
    ):
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

            system_content = CHAT_SYSTEM_PROMPT

            if doc_context:
                system_content += f"\n\n[참고 문서 원문]\n{doc_context}"

            if existing_summary:
                system_content += f"\n\n[이전 대화 핵심 요약]\n{existing_summary}"

            if recent_msgs:
                user_query = recent_msgs[-1].content
                logger.info(f"[RAG_START] query: {user_query}")
                try:
                    rag_hits = retrieve_precedents(
                        query=user_query, top_k=3, search_mode=SearchMode.dense
                    )
                    if rag_hits:
                        logger.info(f"[RAG_HITS] {len(rag_hits)} precedents found.")
                        for i, h in enumerate(rag_hits):
                            title = h.get("title") or "제목 없음"
                            url = h.get("source_url") or "출처 없음"

                        rag_context_parts = []
                        for h in rag_hits:
                            title = h.get("title") or "제목 없음"
                            url = h.get("source_url") or "출처 없음"
                            chunks = h.get("chunks") or []
                            full_text = "\n".join(
                                [(c.get("text") or "").strip() for c in chunks]
                            )
                            rag_context_parts.append(
                                f"판례: {title}\n출처: {url}\n내용: {full_text}"
                            )

                        rag_context = "\n\n".join(rag_context_parts)
                        system_content += f"\n\n[관련 판례 참고]\n{rag_context}"
                    else:
                        logger.info(
                            "[RAG_NO_HITS] No relevant precedents found for the query."
                        )
                except Exception as e:
                    logger.warning(f"[RAG_SEARCH_FAILED] {e}")

            logger.info(f"[FINAL_SYSTEM_PROMPT] {system_content[:2000]}...")
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

        except AppException as ae:
            self._publish_error(redis_client, session_id, user_id, ae.error_code)
        except Exception as e:
            logger.error(f"[PROCESS_CHAT_FAILED] {e}", exc_info=True)
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
