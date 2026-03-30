import { Button } from "@/components/ui/Button.jsx";
import { Input } from "@/components/ui/Input.jsx";
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  IoAdd,
  IoChatbubbleEllipsesOutline,
  IoCheckmarkOutline,
  IoClose,
  IoCloseCircle,
  IoCloudUploadOutline,
  IoDocumentTextOutline,
  IoFolderOpenOutline,
  IoPencilOutline,
  IoPeopleOutline,
  IoSend,
  IoTimeOutline,
  IoTrashOutline
} from 'react-icons/io5';
import { getMyGroups } from '../../../api/groups';
import { useAuth } from '../../../features/auth';
import { useChat } from '../../../features/chat/hooks/useChat';
import { useChatSessions } from '../../../features/chat/hooks/useChatSessions';
import { useSearchParams } from 'react-router-dom';

export default function ChatSection() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const { sessions, createRoom, updateRoom, deleteRoom, refreshRooms } = useChatSessions();
  const [activeSessionId, setActiveSessionId] = useState(null);

  useEffect(() => {
    const sessionId = searchParams.get('sessionId');
    if (sessionId && sessions.length > 0) {
      const targetId = parseInt(sessionId, 10);
      if (sessions.some(s => s.id === targetId)) {
        setActiveSessionId(targetId);
        
        const height = window.innerHeight - 72;
        window.scrollTo({
          top: height, 
          behavior: 'smooth'
        });

        searchParams.delete('sessionId');
        setSearchParams(searchParams, { replace: true });
      }
    }
  }, [searchParams, sessions, setSearchParams]);

  const activeSession = sessions.find(s => s.id === activeSessionId) || null;

  const { messages, sendMessage, isLoading, referenceTitle, removeReference, currentSessionId } = useChat(
    activeSessionId,
    activeSession?.reference_document_title
  );

  useEffect(() => {
    if (activeSessionId && currentSessionId === activeSessionId && referenceTitle !== activeSession?.reference_document_title) {
      refreshRooms();
    }
  }, [referenceTitle, activeSessionId, currentSessionId, activeSession?.reference_document_title, refreshRooms]);
  const [inputText, setInputText] = useState('');
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');

  const [showDocSelect, setShowDocSelect] = useState(false);
  const [showGroupSelect, setShowGroupSelect] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [groups, setGroups] = useState([]);
  const [pendingMessage, setPendingMessage] = useState(null);

  useEffect(() => {
    if (activeSessionId && pendingMessage && currentSessionId === activeSessionId) {
      sendMessage(pendingMessage.text, pendingMessage.doc, pendingMessage.group);
      setPendingMessage(null);
    }
  }, [activeSessionId, pendingMessage, currentSessionId, sendMessage]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    if (!user) return;
    const fetchGroups = async () => {
      try {
        const data = await getMyGroups();
        setGroups(data);
      } catch (error) {
        console.error("Failed to fetch groups:", error);
      }
    };
    fetchGroups();
  }, [user]);

  const handleCreateAndStart = async () => {
     const maxNumber = sessions.reduce((max, session) => {
      const match = session.title.match(/새로운 상담 (\d+)/);
      if (match) {
        const num = parseInt(match[1], 10);
        return num > max ? num : max;
      }
      return max;
    }, 0);

    const newName = `새로운 상담 ${maxNumber + 1}`;
    const newRoom = await createRoom(newName);
    if (newRoom) setActiveSessionId(newRoom.id);
  };

  const handleDeleteRoom = async (e, id) => {
    e.stopPropagation();
    if (window.confirm('상담 내역을 삭제하시겠습니까?')) {
      await deleteRoom(id);
      if (activeSessionId === id) setActiveSessionId(null);
    }
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

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedDoc({ id: Date.now(), title: file.name, file: file });
    setShowDocSelect(false);
    e.target.value = '';
  };

  const handleSend = () => {
    if (!inputText.trim() && !selectedDoc && !selectedGroup) return;
    sendMessage(inputText, selectedDoc, selectedGroup);
    setInputText('');
    setSelectedDoc(null);
    setSelectedGroup(null);
  };

  const handleInitialSend = async () => {
    const textToSend = inputText.trim();
    if (!textToSend && !selectedDoc && !selectedGroup) return;

    const msg = { text: textToSend, doc: selectedDoc, group: selectedGroup };

    setInputText('');
    setSelectedDoc(null);
    setSelectedGroup(null);
    setPendingMessage(msg);

    try {
      const newRoom = await createRoom(`새로운 상담 ${sessions.length + 1}`);
      if (newRoom) {
        setActiveSessionId(newRoom.id);
      }
    } catch (error) {
      console.error("Failed to start initial chat:", error);
    }
  };

  const toggleDocSelect = () => {
    setShowDocSelect(!showDocSelect);
    setShowGroupSelect(false);
  };

  const toggleGroupSelect = () => {
    setShowGroupSelect(!showGroupSelect);
    setShowDocSelect(false);
  };

  const MarkdownComponents = {
    p: ({ children }) => <p className="mb-3 last:mb-0 whitespace-pre-wrap">{children}</p>,
    ul: ({ children }) => <ul className="list-disc pl-6 mb-3 space-y-1.5">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-6 mb-3 space-y-1.5">{children}</ol>,
    li: ({ children }) => <li className="mb-0">{children}</li>,
    code: ({ inline, children }) => (
      inline 
        ? <code className="bg-slate-100 dark:bg-slate-700/50 px-1.5 py-0.5 rounded text-pink-600 dark:text-pink-400 font-mono text-sm">{children}</code>
        : <code className="block bg-slate-100 dark:bg-slate-800 p-4 rounded-2xl font-mono text-sm overflow-x-auto my-4 border border-slate-200 dark:border-slate-700">{children}</code>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-blue-200 dark:border-blue-800 pl-4 italic my-4 text-slate-600 dark:text-slate-400 bg-blue-50/30 dark:bg-blue-900/10 py-2 rounded-r-xl">
        {children}
      </blockquote>
    ),
    h1: ({ children }) => <h1 className="text-2xl font-black mb-4 border-b pb-2">{children}</h1>,
    h2: ({ children }) => <h2 className="text-xl font-bold mb-3">{children}</h2>,
    h3: ({ children }) => <h3 className="text-lg font-bold mb-2">{children}</h3>,
    table: ({ children }) => (
      <div className="overflow-x-auto my-4 rounded-xl border border-slate-200 dark:border-slate-700">
        <table className="min-w-full border-collapse text-sm">
          {children}
        </table>
      </div>
    ),
    th: ({ children }) => <th className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-3 font-bold text-left">{children}</th>,
    td: ({ children }) => <td className="border-b border-slate-100 dark:border-slate-800 p-3">{children}</td>,
  };

  return (
    <section className="h-[calc(100vh-72px)] w-full snap-start snap-always flex bg-slate-50/30 dark:bg-slate-950/30 relative overflow-hidden box-border p-8">
      <div className="max-w-7xl mx-auto w-full h-full flex overflow-hidden bg-white dark:bg-slate-900 rounded-[3rem] shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)] dark:shadow-[0_32px_64px_-16px_rgba(0,0,0,0.3)] border border-slate-200/50 dark:border-slate-800/50">
        <aside className="w-[300px] h-full bg-slate-50/50 dark:bg-slate-900/50 border-r border-slate-100 dark:border-slate-800 flex flex-col shrink-0 overflow-hidden">
          <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
            <h1 className="text-2xl font-black text-foreground flex items-center gap-4">
              <div className="w-2.5 h-8 bg-blue-600 rounded-full" />
              최근 상담
            </h1>
            <Button
              onClick={handleCreateAndStart}
              className="w-full mt-8 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl py-7 shadow-xl shadow-blue-100 dark:shadow-none flex gap-2 font-bold text-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <IoAdd size={24} /> 새 상담 시작
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-6 space-y-3 custom-scrollbar">
            {sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => setActiveSessionId(session.id)}
                className={`group flex items-center justify-between p-5 rounded-2xl cursor-pointer transition-all border ${activeSessionId === session.id ? 'bg-white dark:bg-slate-800 border-blue-200 dark:border-blue-900 shadow-md translate-x-2' : 'border-transparent hover:bg-white/80 dark:hover:bg-slate-800/80 hover:translate-x-1'}`}
              >
                <div className="flex items-center gap-4 flex-1 overflow-hidden">
                  <IoTimeOutline size={18} className={activeSessionId === session.id ? 'text-blue-600' : 'text-slate-400'} />
                  {editingId === session.id ? (
                    <Input
                      className="h-8 py-1 text-sm focus-visible:ring-0 focus-visible:ring-offset-0 bg-slate-50 dark:bg-slate-700 dark:border-slate-600"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.key === 'Enter' && saveEdit(e, session.id)}
                      autoFocus
                    />
                  ) : (
                    <p className={`text-base font-bold truncate ${activeSessionId === session.id ? 'text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-slate-400'}`}>
                      {session.title}
                    </p>
                  )}
                </div>

                <div className={`flex gap-1 transition-opacity ${editingId === session.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                  <button
                    onClick={(e) => editingId === session.id ? saveEdit(e, session.id) : startEdit(e, session)}
                    className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                  >
                    {editingId === session.id ? <IoCheckmarkOutline size={18} /> : <IoPencilOutline size={18} />}
                  </button>
                  <button
                    onClick={(e) => handleDeleteRoom(e, session.id)}
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                  >
                    <IoTrashOutline size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="flex-1 h-full flex flex-col bg-white dark:bg-slate-900 overflow-hidden relative">
          {activeSessionId ? (
            <>
              <div ref={scrollRef} className="flex-1 overflow-y-auto bg-slate-50/30 dark:bg-slate-950/30 p-10 space-y-8 custom-scrollbar">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
                    <div className={`max-w-[85%] p-6 rounded-3xl shadow-sm text-[16px] leading-relaxed flex flex-col ${msg.sender === 'user' ? 'bg-blue-600 text-white shadow-xl shadow-blue-100/50 dark:shadow-none' : 'bg-white dark:bg-slate-800 text-foreground border border-slate-100 dark:border-slate-700'}`}>
                      {(msg.referenceDoc || msg.referenceGroup) && (
                        <div className={`flex flex-col gap-1.5 mb-4`}>
                          {msg.referenceDoc && (
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs w-fit border ${msg.sender === 'user' ? 'bg-white/20 border-white/30 text-white' : 'bg-blue-50 dark:bg-blue-900/30 border-blue-100 dark:border-blue-800 text-blue-700 dark:text-blue-300'}`}>
                              <IoDocumentTextOutline size={14} /> {msg.referenceDoc.title}
                            </div>
                          )}
                          {msg.referenceGroup && (
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs w-fit border ${msg.sender === 'user' ? 'bg-white/20 border-white/30 text-white' : 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-100 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300'}`}>
                              <IoPeopleOutline size={14} /> {msg.referenceGroup.name}
                            </div>
                          )}
                        </div>
                      )}
                      
                      <div className={`markdown-content ${msg.sender === 'user' ? 'text-white' : ''}`}>
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={MarkdownComponents}
                        >
                          {msg.text}
                        </ReactMarkdown>
                      </div>

                      <p className={`text-[10px] mt-4 opacity-50 font-medium ${msg.sender === 'user' ? 'text-right text-blue-50' : 'text-left text-slate-400'}`}>
                        {msg.timestamp}
                      </p>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start animate-in fade-in duration-300">
                    <div className="px-6 py-4 rounded-[2rem] shadow-sm bg-white dark:bg-slate-800 text-foreground border border-slate-100 dark:border-slate-700 flex items-center gap-3">
                      <span className="flex gap-1.5">
                        <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                        <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                        <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></span>
                      </span>
                      <span className="text-sm font-bold text-slate-400">AI 분석 중...</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="p-10 border-t border-slate-100 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl relative">
                {(showDocSelect || showGroupSelect) && (
                  <div className="absolute bottom-full left-10 right-10 mb-6 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-[2rem] shadow-2xl p-4 z-30 animate-in slide-in-from-bottom-4 fade-in duration-300">
                    <div className="flex justify-between items-center mb-4 px-4 pt-2">
                      <span className="text-lg font-black text-foreground">
                        {showDocSelect ? '검토할 문서 선택' : '참조할 그룹 선택'}
                      </span>
                      <button onClick={() => { setShowDocSelect(false); setShowGroupSelect(false); }} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors">
                        <IoClose size={24} className="text-slate-400" />
                      </button>
                    </div>
                    <div className="max-h-64 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                      {showDocSelect && (
                        <>
                          <button onClick={() => fileInputRef.current?.click()} className="w-full text-left p-5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 bg-blue-50/30 dark:bg-blue-900/10 rounded-2xl flex items-center gap-4 transition-all border border-dashed border-blue-200 dark:border-blue-800 font-bold mb-4">
                            <div className="w-12 h-12 bg-white dark:bg-slate-700 rounded-xl flex items-center justify-center shadow-sm"><IoCloudUploadOutline size={24} /></div>
                            내 PC에서 파일 업로드
                          </button>
                        </>
                      )}
                      {showGroupSelect && groups.map(group => (
                        <button key={group.id} onClick={() => { setSelectedGroup(group); setShowGroupSelect(false); }} className="w-full text-left p-4 text-foreground hover:bg-slate-50 dark:hover:bg-slate-700 rounded-xl flex items-center gap-4 transition-colors">
                          <IoPeopleOutline className="text-slate-400" size={20} /> {group.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="max-w-5xl mx-auto space-y-4">
                  {(referenceTitle || selectedDoc || selectedGroup) && (
                    <div className="flex flex-wrap gap-3 px-2">
                      {referenceTitle && !selectedDoc && (
                        <span className="flex items-center gap-2 bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 px-4 py-2 rounded-full border border-indigo-200 dark:border-indigo-800 font-bold text-sm">
                          <IoDocumentTextOutline size={18} /> {referenceTitle}
                          <span className="text-xs opacity-70 ml-1">(참조 중)</span>
                          <button onClick={removeReference} className="hover:text-indigo-900 dark:hover:text-indigo-100"><IoCloseCircle size={20} /></button>
                        </span>
                      )}
                      {selectedDoc && (
                        <span className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-4 py-2 rounded-full border border-blue-200 dark:border-blue-800 font-bold text-sm">
                          <IoDocumentTextOutline size={18} /> {selectedDoc.title}
                          <button onClick={() => setSelectedDoc(null)} className="hover:text-blue-900 dark:hover:text-blue-100"><IoCloseCircle size={20} /></button>
                        </span>
                      )}
                      {selectedGroup && (
                        <span className="flex items-center gap-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 px-4 py-2 rounded-full border border-emerald-200 dark:border-emerald-800 font-bold text-sm">
                          <IoPeopleOutline size={18} /> {selectedGroup.name}
                          <button onClick={() => setSelectedGroup(null)} className="hover:text-emerald-900 dark:hover:text-emerald-100"><IoCloseCircle size={20} /></button>
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex flex-col bg-slate-100/50 dark:bg-slate-800/50 rounded-[2.5rem] border border-slate-200 dark:border-slate-700 focus-within:bg-white dark:focus-within:bg-slate-800 focus-within:border-blue-400 dark:focus-within:border-blue-500 transition-all duration-500 p-2">
                    <div className="flex gap-4 items-center p-2">
                      <input
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder={referenceTitle || selectedDoc || selectedGroup ? "내용을 입력하거나 바로 전송하세요" : "궁금한 법률 내용을 입력하세요..."}
                        className="flex-1 bg-transparent border-none outline-none shadow-none text-xl px-6 h-14 focus:ring-0 text-foreground"
                      />
                      <Button onClick={handleSend} size="icon" className="bg-blue-600 hover:bg-blue-700 rounded-full w-14 h-14 shadow-2xl transition-all active:scale-90 shrink-0">
                        <IoSend size={24} />
                      </Button>
                    </div>
                    <div className="flex items-center gap-3 px-4 pb-3">
                      <Button variant="outline" size="sm"
                        onClick={toggleDocSelect}
                        className={`h-10 text-sm rounded-full gap-2 px-5 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showDocSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}
                      >
                        <IoAdd size={18} /> 문서 검토
                      </Button>
                      <Button variant="outline" size="sm"
                        onClick={toggleGroupSelect}
                        className={`h-10 text-sm rounded-full gap-2 px-5 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showGroupSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}
                      >
                        <IoFolderOpenOutline size={18} /> 그룹 참조
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-20 text-center bg-white dark:bg-slate-900 relative">
              <div className="max-w-2xl w-full space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                <div className="flex flex-col items-center">
                  <div className="w-24 h-24 bg-blue-50 dark:bg-blue-900/20 rounded-[2.5rem] flex items-center justify-center mb-8">
                    <IoChatbubbleEllipsesOutline size={48} className="text-blue-600 dark:text-blue-400" />
                  </div>
                  <h3 className="text-4xl font-black text-foreground mb-4">무엇을 도와드릴까요?</h3>
                  <p className="text-muted-foreground font-medium text-xl">새로운 상담을 시작하여 법률 분석을 받아보세요.</p>
                </div>

                <div className="flex flex-col bg-slate-100/50 dark:bg-slate-800/50 rounded-[2.5rem] border border-slate-200 dark:border-slate-700 focus-within:bg-white dark:focus-within:bg-slate-800 focus-within:border-blue-400 dark:focus-within:border-blue-500 focus-within:shadow-2xl focus-within:shadow-blue-100/50 dark:focus-within:shadow-none transition-all duration-500 p-3 relative">

                  {(showDocSelect || showGroupSelect) && (
                    <div className="absolute bottom-full left-0 right-0 mb-6 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-[2rem] shadow-2xl p-4 z-30 animate-in slide-in-from-bottom-4 fade-in duration-300 text-left">
                      <div className="flex justify-between items-center mb-4 px-4 pt-2">
                        <span className="text-lg font-black text-foreground">
                          {showDocSelect ? '검토할 문서 선택' : '참조할 그룹 선택'}
                        </span>
                        <button onClick={() => { setShowDocSelect(false); setShowGroupSelect(false); }} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors">
                          <IoClose size={24} className="text-slate-400" />
                        </button>
                      </div>
                      <div className="max-h-64 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                        {showDocSelect && (
                          <>
                            <button onClick={() => fileInputRef.current?.click()} className="w-full text-left p-5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 bg-blue-50/30 dark:bg-blue-900/10 rounded-2xl flex items-center gap-4 transition-all border border-dashed border-blue-200 dark:border-blue-800 font-bold mb-4">
                              <div className="w-12 h-12 bg-white dark:bg-slate-700 rounded-xl flex items-center justify-center shadow-sm"><IoCloudUploadOutline size={24} /></div>
                              내 PC에서 파일 업로드
                            </button>
                          </>
                        )}
                        {showGroupSelect && groups.map(group => (
                          <button key={group.id} onClick={() => { setSelectedGroup(group); setShowGroupSelect(false); }} className="w-full text-left p-4 text-foreground hover:bg-slate-50 dark:hover:bg-slate-700 rounded-xl flex items-center gap-4 transition-colors">
                            <IoPeopleOutline className="text-slate-400" size={20} /> {group.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {(selectedDoc || selectedGroup) && (
                    <div className="flex flex-wrap gap-3 px-4 pt-2 pb-1 text-left">
                      {selectedDoc && (
                        <span className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-4 py-1.5 rounded-full border border-blue-200 dark:border-blue-800 font-bold text-xs">
                          <IoDocumentTextOutline size={14} /> {selectedDoc.title}
                          <button onClick={() => setSelectedDoc(null)} className="hover:text-blue-900 dark:hover:text-blue-100"><IoCloseCircle size={16} /></button>
                        </span>
                      )}
                      {selectedGroup && (
                        <span className="flex items-center gap-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 px-4 py-1.5 rounded-full border border-emerald-200 dark:border-emerald-800 font-bold text-xs">
                          <IoPeopleOutline size={14} /> {selectedGroup.name}
                          <button onClick={() => setSelectedGroup(null)} className="hover:text-emerald-900 dark:hover:text-emerald-100"><IoCloseCircle size={16} /></button>
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex gap-4 items-center p-2">
                    <input
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleInitialSend()}
                      placeholder={selectedDoc || selectedGroup ? "내용을 입력하거나 바로 전송하세요" : "궁금한 법률 내용을 입력하고 상담을 시작하세요..."}
                      className="flex-1 bg-transparent border-none outline-none shadow-none text-xl px-6 h-16 focus:ring-0 text-foreground"
                    />
                    <Button
                      onClick={handleInitialSend}
                      className="bg-blue-600 hover:bg-blue-700 rounded-full w-16 h-16 shadow-2xl transition-all active:scale-90 shrink-0"
                    >
                      <IoSend size={28} />
                    </Button>
                  </div>
                  <div className="flex items-center gap-3 px-4 pb-3">
                    <Button variant="outline" size="sm" onClick={() => { setShowDocSelect(!showDocSelect); setShowGroupSelect(false); }} className={`h-11 text-sm rounded-full gap-2 px-6 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showDocSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}>
                      <IoAdd size={20} /> 문서 검토
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => { setShowGroupSelect(!showGroupSelect); setShowDocSelect(false); }} className={`h-11 text-sm rounded-full gap-2 px-6 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showGroupSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}>
                      <IoFolderOpenOutline size={20} /> 그룹 참조
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-left">
                  <div className="p-6 rounded-3xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 hover:border-blue-200 dark:hover:border-blue-900 transition-colors cursor-pointer group" onClick={() => setInputText('근로계약서 작성 시 유의사항을 알려줘')}>
                    <p className="text-sm font-bold text-blue-600 dark:text-blue-400 mb-2">추천 질문</p>
                    <p className="text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-slate-200 transition-colors">"근로계약서 작성 시 유의사항을 알려줘"</p>
                  </div>
                  <div className="p-6 rounded-3xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 hover:border-blue-200 dark:hover:border-blue-900 transition-colors cursor-pointer group" onClick={() => setInputText('개인정보 처리방침 필수 포함 항목이 뭐야?')}>
                    <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mb-2">추천 질문</p>
                    <p className="text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-slate-200 transition-colors">"개인정보 처리방침 필수 포함 항목이 뭐야?"</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".pdf,.doc,.docx,.hwp,.txt" />
    </section>
  );
}
