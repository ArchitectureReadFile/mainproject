import json
import os

import requests
from redis import Redis
from sqlalchemy.orm import Session

from models.model import ChatMessage, ChatMessageRole, Document, GroupMember
from prompts.chat_prompt import CHAT_SUMMARY_PROMPT, CHAT_SYSTEM_PROMPT
from services.summary.process_service import ProcessService

OLLAMA_HOST = os.getenv("OLLAMA_HOST")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")


class ChatService:
    def __init__(self, db: Session, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client

    def process_chat(
        self, user_id: int, session_id: int, message: str, context_options: dict
    ):
        temp_doc_text = context_options.get("temp_doc_text")
        doc_id = context_options.get("doc_id")

        self._publish_status(
            session_id, user_id, "processing", "답변을 생성중입니다..."
        )

        doc_context = ""
        if temp_doc_text:
            doc_context = temp_doc_text
        elif doc_id:
            if not self._check_document_permission(user_id, doc_id):
                self._publish_status(
                    session_id,
                    user_id,
                    "error",
                    "해당 문서를 찾을 수 없거나 접근 권한이 없습니다.",
                )
                return

            document = self.db.query(Document).filter(Document.id == doc_id).first()
            doc_context = self._get_document_full_text(document)

        summary_key = f"chat_summary:{session_id}"
        last_msg_key = f"chat_last_summarized_id:{session_id}"

        existing_summary = self.redis_client.get(summary_key) or ""
        if isinstance(existing_summary, bytes):
            existing_summary = existing_summary.decode("utf-8")

        last_id_str = self.redis_client.get(last_msg_key)
        last_id = int(last_id_str) if last_id_str else 0

        unsummarized_msgs = (
            self.db.query(ChatMessage)
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

            self.redis_client.set(summary_key, new_summary)
            self.redis_client.set(last_msg_key, msgs_to_summarize[-1].id)

            existing_summary = new_summary
        else:
            recent_msgs = unsummarized_msgs

        system_content = CHAT_SYSTEM_PROMPT

        if doc_context:
            system_content += f"\n\n[참고 문서 원문]\n{doc_context}"

        if existing_summary:
            system_content += f"\n\n[이전 대화 핵심 요약]\n{existing_summary}"

        chat_messages = [{"role": "system", "content": system_content.strip()}]

        for msg in recent_msgs:
            role_str = "user" if msg.role == ChatMessageRole.USER else "assistant"
            chat_messages.append({"role": role_str, "content": msg.content})

        full_answer = self._generate_llm_response(session_id, user_id, chat_messages)

        if full_answer:
            ai_msg = ChatMessage(
                session_id=session_id,
                role=ChatMessageRole.ASSISTANT,
                content=full_answer,
            )
            self.db.add(ai_msg)
            self.db.commit()

    def _summarize_dialogue(self, existing_summary: str, new_dialogue: str) -> str:
        prompt = CHAT_SUMMARY_PROMPT.format(
            existing_summary=existing_summary or "기존 요약 없음",
            new_dialogue=new_dialogue,
        )
        payload_data = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            with requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload_data,
                timeout=60,
            ) as r:
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception:
            return existing_summary

    def _check_document_permission(self, user_id: int, doc_id: int) -> bool:
        document = self.db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            return False
        if document.group_id:
            member = (
                self.db.query(GroupMember)
                .filter(
                    GroupMember.user_id == user_id,
                    GroupMember.group_id == document.group_id,
                )
                .first()
            )
            return bool(member)
        return True

    def _get_document_full_text(self, document: Document) -> str:
        file_path = getattr(document, "stored_path", None) or getattr(
            document, "url", None
        )

        if not file_path or not os.path.exists(file_path):
            return "시스템 메시지: 실제 파일을 찾을 수 없습니다."

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            process_service = ProcessService()
            pages = process_service.extract_pages_from_bytes(file_bytes)

            if process_service.is_text_too_short("\n".join(pages)):
                pages = process_service.extract_pages_from_bytes_ocr(file_bytes)

            return "\n".join(pages).strip()
        except Exception as e:
            return f"시스템 메시지: 문서 텍스트 추출 중 오류가 발생했습니다. ({str(e)})"

    def _publish_status(self, session_id: int, user_id: int, status: str, message: str):
        payload = {"status": status, "message": message}
        self.redis_client.publish(f"chat:{session_id}:{user_id}", json.dumps(payload))

    def _generate_llm_response(
        self, session_id: int, user_id: int, messages: list
    ) -> str:
        payload_data = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.1},
        }

        full_answer = ""
        try:
            with requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload_data,
                stream=True,
                timeout=120,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        word = chunk.get("message", {}).get("content", "")
                        if word:
                            full_answer += word
                            self._publish_status(
                                session_id, user_id, "streaming", full_answer
                            )
        except Exception as e:
            self._publish_status(
                session_id,
                user_id,
                "error",
                f"LLM 모델 서버와 통신 중 오류가 발생했습니다. ({str(e)})",
            )
            return ""

        self._publish_status(session_id, user_id, "complete", full_answer)
        return full_answer
