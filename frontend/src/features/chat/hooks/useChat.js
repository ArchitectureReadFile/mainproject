import { useState, useEffect, useRef, useCallback } from 'react';
import { chatApi } from '../api/chatApi.js';
import { useAuth } from '@/features/auth/context/AuthContext';

const toKSTTime = (date) =>
    date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul' });


export const useChat = (sessionId, initialReferenceTitle) => {
    const { user } = useAuth();
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingHistory, setIsFetchingHistory] = useState(false);
    const [referenceTitle, setReferenceTitle] = useState(initialReferenceTitle || null);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const ws = useRef(null);

    useEffect(() => {
        if (initialReferenceTitle !== undefined) {
            setReferenceTitle(initialReferenceTitle || null);
        }
    }, [sessionId, initialReferenceTitle]);

    const connectWebSocket = useCallback(() => {
        if (!sessionId || !user?.id) return;
        if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const wsUrl = `ws://localhost:8000/api/ws/chat/${sessionId}/${user.id}`;
        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
            console.log('Chat WebSocket Connected');
        };

        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status === 'processing') {
                setIsLoading(true);
            } else if (data.status === 'streaming') {
                setIsLoading(false);
                setMessages((prev) => {
                    const lastMsg = prev[prev.length - 1];
                    if (lastMsg && lastMsg.sender === 'ai' && lastMsg.isStreaming) {
                        const newMessages = [...prev];
                        newMessages[prev.length - 1] = { ...lastMsg, text: data.message };
                        return newMessages;
                    } else {
                        const aiMsg = {
                            id: Date.now(),
                            text: data.message,
                            sender: 'ai',
                            timestamp: toKSTTime(new Date()),
                            isError: false,
                            isStreaming: true
                        };
                        return [...prev, aiMsg];
                    }
                });
            } else if (data.status === 'complete' || data.status === 'error') {
                setIsLoading(false);
                setMessages((prev) => {
                    const lastMsg = prev[prev.length - 1];
                    if (lastMsg && lastMsg.sender === 'ai' && lastMsg.isStreaming) {
                        const newMessages = [...prev];
                        newMessages[prev.length - 1] = {
                            ...lastMsg,
                            text: data.message,
                            isStreaming: false,
                            isError: data.status === 'error'
                        };
                        return newMessages;
                    } else {
                        const aiMsg = {
                            id: Date.now(),
                            text: data.message,
                            sender: 'ai',
                            timestamp: toKSTTime(new Date()),
                            isError: data.status === 'error',
                            isStreaming: false
                        };
                        return [...prev, aiMsg];
                    }
                });
            }
        };

        ws.current.onerror = (error) => {
            console.error('WebSocket Error:', error);
            setIsLoading(false);
        };

        ws.current.onclose = () => {
            setTimeout(() => {
                connectWebSocket();
            }, 3000);
        };
    }, [sessionId, user?.id]);

    useEffect(() => {
        if (!sessionId || !user) return;

        const fetchMessages = async () => {
            setIsFetchingHistory(true);
            try {
                const data = await chatApi.getMessages(sessionId);
                const formattedMessages = data.map(m => ({
                    id: m.id,
                    text: m.content,
                    sender: m.role === 'USER' ? 'user' : 'ai',
                    timestamp: toKSTTime(new Date(m.created_at + 'Z')),
                    isError: false,
                    isStreaming: false
                }));

                const isLastMsgUser = formattedMessages.length > 0 && 
                                    formattedMessages[formattedMessages.length - 1].sender === 'user';

                setMessages(formattedMessages || []);
                setIsLoading(isLastMsgUser);
                setCurrentSessionId(sessionId);
            } catch (error) {
                console.error("Failed to load chat history:", error);
                setIsLoading(false);
            } finally {
                setIsFetchingHistory(false);
            }
        };

        setMessages([]);
        setIsLoading(false);
        setIsFetchingHistory(true);
        setCurrentSessionId(null);
        fetchMessages();
        connectWebSocket();

        return () => {
            setIsLoading(false);
            if (ws.current) {
                ws.current.close();
            }
        };
    }, [sessionId, user, connectWebSocket]);

    const sendMessage = useCallback(async (text, doc, group) => {
        if (!user) return;

        const userText = text || (doc ? `${doc.title || doc.file?.name} 검토 부탁드립니다.` : '');
        if (!userText.trim() && !doc) return;

        const userMsg = {
            id: Date.now(),
            text: userText,
            sender: 'user',
            timestamp: toKSTTime(new Date()),
            referenceDoc: doc,
            referenceGroup: group 
        };

        setMessages((prev) => [...prev, userMsg]);
        setIsLoading(true);

        if (doc) {
            const newTitle = doc.title || doc.file?.name;
            setReferenceTitle(newTitle);
        }

        try {
            await chatApi.sendMessage(sessionId, userText, doc);
        } catch (error) {
            console.error("Failed to send message via HTTP:", error);
            setIsLoading(false);
        }
    }, [sessionId, user]);

    const removeReference = useCallback(async () => {
        try {
            await chatApi.deleteReference(sessionId);
            setReferenceTitle(null);
        } catch (error) {
            console.error("Failed to delete reference:", error);
        }
    }, [sessionId]);

    return { messages, isLoading, isFetchingHistory, sendMessage, referenceTitle, removeReference, currentSessionId };
};
