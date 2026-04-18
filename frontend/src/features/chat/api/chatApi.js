import client from '@/shared/api/client';

export const chatApi = {
    getRooms: async () => {
        const response = await client.get('/chat/sessions');
        return response.data;
    },

    createRoom: async (data) => {
        const response = await client.post('/chat/sessions', data);
        return response.data;
    },

    updateRoom: async (sessionId, data) => {
        const response = await client.put(`/chat/sessions/${sessionId}`, data);
        return response.data;
    },

    deleteRoom: async (sessionId) => {
        const response = await client.delete(`/chat/sessions/${sessionId}`);
        return response.data;
    },

    getMessages: async (sessionId) => {
        const response = await client.get(`/chat/sessions/${sessionId}/messages`);
        return response.data;
    },

    sendMessage: async (sessionId, text, groupId, workspaceSelection) => {
        const formData = new FormData();

        if (text) {
            formData.append('text', text);
        }

        if (groupId) {
            formData.append('group_id', groupId);
        }

        if (workspaceSelection) {
            formData.append('workspace_selection_json', JSON.stringify(workspaceSelection));
        }

        const response = await client.post(`/chat/sessions/${sessionId}/messages`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        return response.data;
    },

    uploadReferenceDocument: async (sessionId, file) => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await client.post(`/chat/sessions/${sessionId}/reference-upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        return response.data;
    },

    getReferenceDocument: async (sessionId) => {
        const response = await client.get(`/chat/sessions/${sessionId}/reference`);
        return response.data;
    },

    deleteReferenceDocument: async (sessionId) => {
        const response = await client.delete(`/chat/sessions/${sessionId}/reference`);
        return response.data;
    },

    deleteReferenceGroup: async (sessionId) => {
        const response = await client.delete(`/chat/sessions/${sessionId}/reference-group`);
        return response.data;
    },

    stopMessage: async (sessionId) => {
        const response = await client.post(`/chat/sessions/${sessionId}/stop`);
        return response.data;
    }
};
