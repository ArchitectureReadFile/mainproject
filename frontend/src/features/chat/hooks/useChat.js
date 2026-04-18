import { useState, useEffect, useRef, useCallback } from 'react';
import { chatApi } from '../api/chatApi.js';
import { useAuth } from '@/features/auth/context/AuthContext';

const toKSTTime = (date) =>
    date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul' });


export const useChat = (sessionId, initialReferenceTitle, initialReferenceGroup, initialReferenceStatus = null) => {
    const { user } = useAuth();
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingHistory, setIsFetchingHistory] = useState(false);
    const [referenceTitle, setReferenceTitle] = useState(initialReferenceTitle || null);
    const [referenceGroup, setReferenceGroup] = useState(initialReferenceGroup || null);
    const [referenceStatus, setReferenceStatus] = useState(initialReferenceStatus || null);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const ws = useRef(null);
    const intentionalClose = useRef(false);
    const reconnectTimer = useRef(null);

    useEffect(() => {
        setReferenceTitle(initialReferenceTitle || null);
        setReferenceGroup(initialReferenceGroup || null);
        setReferenceStatus(initialReferenceStatus || null);
    }, [sessionId, initialReferenceTitle, initialReferenceGroup, initialReferenceStatus]);

    useEffect(() => {
        if (!sessionId || referenceStatus !== 'PROCESSING') return;

        let cancelled = false;
        const timer = setInterval(async () => {
            try {
                const reference = await chatApi.getReferenceDocument(sessionId);
                if (cancelled) return;

                if (!reference) {
                    setReferenceTitle(null);
                    setReferenceStatus(null);
                    return;
                }

                setReferenceTitle(reference.title || null);
                setReferenceStatus(reference.status || null);
            } catch (error) {
                console.error('Failed to refresh reference status:', error);
            }
        }, 2000);

        return () => {
            cancelled = true;
            clearInterval(timer);
        };
    }, [sessionId, referenceStatus]);

    const connectWebSocket = useCallback(() => {
        if (!sessionId || !user?.id) return;
        if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
            return;
        }

        intentionalClose.current = false;

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const wsUrl = `${protocol}://${window.location.host}/api/ws/chat/${sessionId}/${user.id}`
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
                        newMessages[prev.length - 1] = {
                            ...lastMsg,
                            text: data.message,
                            references: lastMsg.references || [],
                        };
                        return newMessages;
                    } else {
                        const aiMsg = {
                            id: Date.now(),
                            text: data.message,
                            sender: 'ai',
                            timestamp: toKSTTime(new Date()),
                            isError: false,
                            isStreaming: true,
                            references: [],
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
                            isError: data.status === 'error',
                            references: Array.isArray(data.references) ? data.references : (lastMsg.references || []),
                        };
                        return newMessages;
                    } else {
                        const aiMsg = {
                            id: Date.now(),
                            text: data.message,
                            sender: 'ai',
                            timestamp: toKSTTime(new Date()),
                            isError: data.status === 'error',
                            isStreaming: false,
                            references: Array.isArray(data.references) ? data.references : [],
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
            if (intentionalClose.current) return;
            reconnectTimer.current = setTimeout(() => {
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
                const { messages: apiMessages, is_processing } = data;

                const formattedMessages = apiMessages.map(m => ({
                    id: m.id,
                    text: m.content,
                    sender: m.role === 'USER' ? 'user' : 'ai',
                    timestamp: toKSTTime(new Date(m.created_at + 'Z')),
                    isError: false,
                    isStreaming: false,
                    references: Array.isArray(m.references) ? m.references : [],
                }));

                setMessages(formattedMessages || []);
                setIsLoading(is_processing);
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
            intentionalClose.current = true;
            clearTimeout(reconnectTimer.current);
            if (ws.current) {
                ws.current.close();
                ws.current = null;
            }
        };
    }, [sessionId, user, connectWebSocket]);

    const stopMessage = useCallback(async () => {
        if (!sessionId) return;
        try {
            await chatApi.stopMessage(sessionId);
            setIsLoading(false);
        } catch (error) {
            console.error("Failed to stop message:", error);
        }
    }, [sessionId]);

    const uploadReferenceDocument = useCallback(async (file) => {
        if (!sessionId || !file) return;

        const previousReferenceTitle = referenceTitle;
        const previousReferenceStatus = referenceStatus;

        setReferenceTitle(file.name);
        setReferenceStatus('PROCESSING');

        try {
            const reference = await chatApi.uploadReferenceDocument(sessionId, file);
            setReferenceTitle(reference?.title || file.name);
            setReferenceStatus(reference?.status || 'PROCESSING');
        } catch (error) {
            console.error('Failed to upload reference document:', error);
            setReferenceTitle(previousReferenceTitle);
            setReferenceStatus(previousReferenceStatus);
            throw error;
        }
    }, [sessionId, referenceTitle, referenceStatus]);

    const sendMessage = useCallback(async (text, group, workspaceSelection) => {
        if (!user) return;
        if (referenceStatus === 'PROCESSING') return;

        const effectiveDoc = referenceTitle ? { title: referenceTitle } : null;
        const effectiveGroup = group || referenceGroup;
        const previousReferenceTitle = referenceTitle;
        const previousReferenceGroup = referenceGroup ? { ...referenceGroup } : null;

        const userText = text || '';
        if (!userText.trim() && !group && !referenceTitle && !referenceGroup) return;

        const userMsg = {
            id: Date.now(),
            text: userText,
            sender: 'user',
            timestamp: toKSTTime(new Date()),
            referenceDoc: effectiveDoc,
            referenceGroup: effectiveGroup
        };

        setMessages((prev) => [...prev, userMsg]);
        setIsLoading(true);

        if (group) {
            setReferenceGroup({ id: group.id, name: group.name });
        }

        const effectiveGroupId = effectiveGroup?.id;
        const effectiveWorkspaceSelection = workspaceSelection || (effectiveGroupId ? { mode: "all", document_ids: [] } : null);

        try {
            await chatApi.sendMessage(sessionId, userText, effectiveGroupId, effectiveWorkspaceSelection);
        } catch (error) {
            console.error("Failed to send message via HTTP:", error);
            setMessages((prev) => prev.filter((msg) => msg.id !== userMsg.id));
            setReferenceTitle(previousReferenceTitle);
            setReferenceGroup(previousReferenceGroup);
            setIsLoading(false);
        }
    }, [sessionId, user, referenceTitle, referenceGroup, referenceStatus]);

    const removeReferenceDocument = useCallback(async () => {
        try {
            await chatApi.deleteReferenceDocument(sessionId);
            setReferenceTitle(null);
            setReferenceStatus(null);
        } catch (error) {
            console.error("Failed to delete reference document:", error);
        }
    }, [sessionId]);

    const removeReferenceGroup = useCallback(async () => {
        try {
            await chatApi.deleteReferenceGroup(sessionId);
            setReferenceGroup(null);
        } catch (error) {
            console.error("Failed to delete reference group:", error);
        }
    }, [sessionId]);

    return { 
        messages, 
        isLoading, 
        isFetchingHistory, 
        sendMessage, 
        stopMessage,
        uploadReferenceDocument,
        referenceTitle, 
        referenceStatus,
        referenceGroup,
        removeReferenceDocument, 
        removeReferenceGroup,
        currentSessionId 
    };
};
