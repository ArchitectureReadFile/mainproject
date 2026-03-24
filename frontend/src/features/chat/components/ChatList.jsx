import React, { useState, useEffect } from 'react';
import { IoAdd, IoTrashOutline, IoPencilOutline, IoCheckmarkOutline, IoClose } from 'react-icons/io5';
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useChatSessions } from '../hooks/useChatSessions';

export default function ChatList({ onSelectRoom, onClose, refreshTrigger }) {
  const { sessions, createRoom, updateRoom, deleteRoom, refreshRooms } = useChatSessions();
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');

  useEffect(() => {
    if (refreshTrigger > 0) {
        refreshRooms();
    }
  }, [refreshTrigger, refreshRooms]);

  const handleCreateRoom = async () => {
    const newName = `새로운 상담 ${sessions.length + 1}`;
    await createRoom(newName);
  };

  const handleDeleteRoom = async (e, id) => {
    e.stopPropagation();
    await deleteRoom(id);
  };

  const startEdit = (e, session) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditName(session.title);
  };

  const saveEdit = async (e, id) => {
    e.stopPropagation();
    if (editName.trim()) {
      await updateRoom(id, editName.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950">
      <div className="flex items-center justify-between p-4 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800 shadow-sm z-10">
        <h3 className="font-bold text-slate-800 dark:text-foreground text-lg tracking-tight">법률 상담 챗봇</h3>
        <div className="flex items-center gap-1">
          <Button size="icon" variant="ghost" className="text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full w-9 h-9" onClick={handleCreateRoom}>
            <IoAdd size={22} />
          </Button>
          <Button size="icon" variant="ghost" className="text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full w-9 h-9" onClick={onClose}>
            <IoClose size={22} />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 px-1 uppercase tracking-wider">이전 대화 목록</span>
        <div className="space-y-2 mt-2">
          {sessions.map(session => (
            <div
              key={session.id}
              className="flex items-center justify-between p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-blue-400 dark:hover:border-blue-700 hover:shadow-md cursor-pointer transition-all duration-200 group"
              onClick={() => onSelectRoom(session)}
            >
              <div className="flex-1 mr-2">
                {editingId === session.id ? (
                  <Input
                    className="h-8 py-1 text-sm focus-visible:ring-0 focus-visible:ring-offset-0 dark:bg-slate-800 dark:border-slate-700"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.key === 'Enter' && saveEdit(e, session.id)}
                    autoFocus
                  />
                ) : (
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{session.title}</span>
                )}
              </div>

              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  variant="ghost" size="icon" className="h-8 w-8 text-slate-400 dark:text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-full"
                  onClick={(e) => editingId === session.id ? saveEdit(e, session.id) : startEdit(e, session)}
                >
                  {editingId === session.id ? <IoCheckmarkOutline size={16} /> : <IoPencilOutline size={16} />}
                </Button>
                <Button
                  variant="ghost" size="icon" className="h-8 w-8 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-full"
                  onClick={(e) => handleDeleteRoom(e, session.id)}
                >
                  <IoTrashOutline size={16} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}