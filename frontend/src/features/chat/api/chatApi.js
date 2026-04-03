import client from '../../../api/client.js';

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

    sendMessage: async (sessionId, text, doc, groupId, workspaceSelection) => {
        const formData = new FormData();

        if (text) {
            formData.append('text', text);
        }

        if (doc?.file) {
            formData.append('file', doc.file);
        } else if (doc?.id) {
            formData.append('document_id', doc.id);
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

    deleteReferenceDocument: async (sessionId) => {
        const response = await client.delete(`/chat/sessions/${sessionId}/reference`);
        return response.data;
    },

    deleteReferenceGroup: async (sessionId) => {
        const response = await client.delete(`/chat/sessions/${sessionId}/reference-group`);
        return response.data;
    }
};