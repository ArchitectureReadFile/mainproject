import json
import os

import requests
from redis import Redis
from sqlalchemy.orm import Session
from models.model import (
    ChatSession,
    ChatMessage,
    ChatMessageRole,
    Document,
    GroupMember,
)
from prompts.chat_prompt import CHAT_SYSTEM_PROMPT, CHAT_SUMMARY_PROMPT
from services.summary.process_service import ProcessService
from errors.error_codes import ErrorCode
from errors.exceptions import AppException

OLLAMA_HOST = os.getenv("OLLAMA_HOST")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")


class ChatService:
    def get_sessions(self, db: Session, user_id: int):
        return (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def create_session(self, db: Session, user_id: int, title: str):
        new_session = ChatSession(user_id=user_id, title=title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    def update_session(self, db: Session, user_id: int, session_id: int, title: str):
        session = self._get_session_with_permission(db, user_id, session_id)
        session.title = title
        db.commit()
        db.refresh(session)
        return session

    def delete_session(self, db: Session, user_id: int, session_id: int):
        session = self._get_session_with_permission(db, user_id, session_id)
        db.delete(session)
        db.commit()

    def get_messages(self, db: Session, user_id: int, session_id: int):
        self._get_session_with_permission(db, user_id, session_id)
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def upload_reference_document(
        self,
        db: Session,
        user_id: int,
        session_id: int,
        file_name: str,
        file_bytes: bytes,
    ):
        session = self._get_session_with_permission(db, user_id, session_id)

        extracted_text = self._extract_text_from_bytes(file_bytes)

        session.reference_document_title = file_name
        session.reference_document_text = extracted_text
        db.commit()
        db.refresh(session)
        return session

    def delete_reference_document(self, db: Session, user_id: int, session_id: int):
        session = self._get_session_with_permission(db, user_id, session_id)

        session.reference_document_title = None
        session.reference_document_text = None
        db.commit()
        db.refresh(session)
        return session

    def send_message(
        self,
        db: Session,
        user_id: int,
        session_id: int,
        text: str,
        document_id: int = None,
        file_name: str = None,
        file_bytes: bytes = None,
    ):
        session = self._get_session_with_permission(db, user_id, session_id)

        user_msg = ChatMessage(
            session_id=session_id, role=ChatMessageRole.USER, content=text
        )
        db.add(user_msg)

        if file_bytes:
            extracted_text = self._extract_text_from_bytes(file_bytes)
            session.reference_document_title = file_name
            session.reference_document_text = extracted_text
        elif document_id:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document and self._check_document_permission(db, user_id, document_id):
                doc_text = self._get_document_full_text(document)
                session.reference_document_title = (
                    document.title or document.original_filename
                )
                session.reference_document_text = doc_text

        db.commit()

        from tasks.chat_task import process_chat_message

        payload = {
            "user_id": user_id,
            "session_id": session_id,
        }
        process_chat_message.delay(payload)

        return {"status": "success", "message": "Task queued"}

    def process_chat(
        self, db: Session, redis_client: Redis, user_id: int, session_id: int
    ):
        self._publish_status(
            redis_client, session_id, user_id, "processing", "답변을 생성중입니다..."
        )

        try:
            session = self._get_session_with_permission(db, user_id, session_id)
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
        except Exception:
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.CHAT_HISTORY_LOAD_FAILED
            )

    def _get_session_with_permission(
        self, db: Session, user_id: int, session_id: int
    ) -> ChatSession:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise AppException(ErrorCode.CHAT_ROOM_NOT_FOUND)
        if session.user_id != user_id:
            raise AppException(ErrorCode.CHAT_UNAUTHORIZED)
        return session

    def _extract_text_from_bytes(self, file_bytes: bytes) -> str:
        try:
            process_service = ProcessService()
            pages = process_service.extract_pages_from_bytes(file_bytes)
            if process_service.is_text_too_short("\n".join(pages)):
                pages = process_service.extract_pages_from_bytes_ocr(file_bytes)

            extracted_text = "\n".join(pages).strip()
            if not extracted_text:
                raise AppException(ErrorCode.LLM_EMPTY_PAGES)
            return extracted_text
        except AppException:
            raise
        except Exception:
            raise AppException(ErrorCode.CHAT_FILE_PARSE_FAILED)

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

    def _check_document_permission(
        self, db: Session, user_id: int, doc_id: int
    ) -> bool:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            return False
        if document.group_id:
            member = (
                db.query(GroupMember)
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
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            return self._extract_text_from_bytes(file_bytes)
        except AppException:
            raise
        except Exception:
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR)

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

    def _generate_llm_response(
        self, redis_client: Redis, session_id: int, user_id: int, messages: list
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
                                redis_client,
                                session_id,
                                user_id,
                                "streaming",
                                full_answer,
                            )
        except requests.exceptions.Timeout:
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.LLM_PROCESS_TIMEOUT
            )
            return ""
        except requests.exceptions.ConnectionError:
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.LLM_CONNECT_FAILED
            )
            return ""
        except Exception:
            self._publish_error(
                redis_client, session_id, user_id, ErrorCode.LLM_ALL_PROFILES_FAILED
            )
            return ""

        self._publish_status(redis_client, session_id, user_id, "complete", full_answer)
        return full_answer
