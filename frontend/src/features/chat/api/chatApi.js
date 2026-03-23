import client from '../../../api/client.js';

export const chatApi = {
    getRooms: async () => {
        const response = await client.get('/chat/rooms');
        return response.data;
    },

    createRoom: async (data) => {
        const response = await client.post('/chat/rooms', data);
        return response.data;
    },

    updateRoom: async (sessionId, data) => {
        const response = await client.put(`/chat/rooms/${sessionId}`, data);
        return response.data;
    },

    deleteRoom: async (sessionId) => {
        const response = await client.delete(`/chat/rooms/${sessionId}`);
        return response.data;
    },

    getMessages: async (sessionId) => {
        const response = await client.get(`/chat/rooms/${sessionId}/messages`);
        return response.data;
    },

    sendMessage: async (sessionId, text, doc) => {
        const formData = new FormData();

        if (text) {
            formData.append('text', text);
        }

        if (doc?.file) {
            formData.append('file', doc.file);
        } else if (doc?.id) {
            formData.append('document_id', doc.id);
        }

        const response = await client.post(`/chat/rooms/${sessionId}/messages`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        return response.data;
    }
};