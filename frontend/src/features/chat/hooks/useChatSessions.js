import { useState, useEffect, useCallback } from 'react';
import { chatApi } from '../api/chatApi.js';
import { useAuth } from '../../auth/context/AuthContext.jsx';

export function useChatSessions() {
    const auth = useAuth();
    const user = auth?.user;

    const [sessions, setRooms] = useState([]);

    const fetchRooms = useCallback(async () => {
        if (!user) return;
        try {
            const data = await chatApi.getRooms();
            setRooms(data);
        } catch (error) {
            console.error("Failed to fetch sessions:", error);
        }
    }, [user]);

    useEffect(() => {
        fetchRooms();
    }, [fetchRooms]);

    const createRoom = async (title) => {
        if (!user) return;
        const newRoom = await chatApi.createRoom({ title });
        setRooms(prev => [newRoom, ...prev]);
        return newRoom;
    };

    const updateRoom = async (sessionId, title) => {
        if (!user) return;
        const updatedRoom = await chatApi.updateRoom(sessionId, { title });
        setRooms(prev => prev.map(r => r.id === sessionId ? updatedRoom : r));
        return updatedRoom;
    };

    const deleteRoom = async (sessionId) => {
        if (!user) return;
        await chatApi.deleteRoom(sessionId);
        setRooms(prev => prev.filter(r => r.id !== sessionId));
    };

    return { sessions, createRoom, updateRoom, deleteRoom, refreshRooms: fetchRooms };
}