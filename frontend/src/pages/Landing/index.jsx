import React, { useState, useRef, useEffect } from 'react';
import {
  IoAdd,
  IoChatbubbleEllipsesOutline,
  IoTimeOutline,
  IoSend,
  IoDocumentTextOutline,
  IoPencilOutline,
  IoTrashOutline,
  IoCheckmarkOutline,
  IoMenuOutline,
  IoCloseCircle,
  IoFolderOpenOutline,
  IoPeopleOutline,
  IoCloudUploadOutline,
  IoClose
} from 'react-icons/io5';
import { Button } from "@/components/ui/Button.jsx";
import { Input } from "@/components/ui/Input.jsx";
import { Avatar, AvatarFallback } from "@/components/ui/Avatar.jsx";
import { useChatSessions } from '../../features/chat/hooks/useChatSessions';
import { useChat } from '../../features/chat/hooks/useChat';

export default function LandingPage() {
  const { sessions, createRoom, updateRoom, deleteRoom } = useChatSessions();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const { messages, sendMessage, isLoading } = useChat(activeSessionId);
  const [inputText, setInputText] = useState('');

  const fileInputRef = useRef(null);
  const [showDocSelect, setShowDocSelect] = useState(false);
  const [showGroupSelect, setShowGroupSelect] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);

  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const scrollRef = useRef(null);

  const dummyDocuments = [
    { id: 1, title: '표준 근로계약서.pdf' },
    { id: 2, title: '비밀유지 서약서(NDA).pdf' },
    { id: 3, title: '부동산 임대차 계약서.docx' },
  ];

  const dummyGroups = [
    { id: 1, name: '법무팀 워크스페이스' },
    { id: 2, name: '프론트엔드 그룹' },
    { id: 3, name: '개인 문서함' },
  ];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleCreateAndStart = async () => {
    const newName = `새로운 상담 ${sessions.length + 1}`;
    const newRoom = await createRoom(newName);
    if (newRoom) setActiveSessionId(newRoom.id);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const newDoc = {
      id: Date.now(),
      title: file.name,
      file: file
    };

    setSelectedDoc(newDoc);
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

  const toggleDocSelect = () => {
    setShowDocSelect(!showDocSelect);
    setShowGroupSelect(false);
  };

  const toggleGroupSelect = () => {
    setShowGroupSelect(!showGroupSelect);
    setShowDocSelect(false);
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

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (window.confirm("상담 내역을 삭제하시겠습니까?")) {
      await deleteRoom(id);
      if (activeSessionId === id) setActiveSessionId(null);
    }
  };

  return (
    <div className="flex h-screen w-full bg-white overflow-hidden text-slate-900">
      <aside
        className={`h-full bg-white border-r border-slate-200 flex flex-col shrink-0 transition-all duration-300 ease-in-out shadow-sm ${isSidebarOpen ? 'w-[340px]' : 'w-0 border-none opacity-0'
          }`}
      >
        <div className="p-6 border-b border-slate-100 shrink-0 min-w-[340px]">
          <h1 className="text-xl font-bold text-blue-600 flex items-center gap-2">
            <IoChatbubbleEllipsesOutline size={24} />
            Legal AI
          </h1>
          <Button
            onClick={handleCreateAndStart}
            className="w-full mt-6 bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-6 shadow-md transition-all flex gap-2"
          >
            <IoAdd size={20} /> 새 상담 시작하기
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 min-w-[340px]">
          <p className="text-[11px] font-bold text-slate-400 px-2 mb-3 uppercase tracking-widest">최근 상담 내역</p>
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => setActiveSessionId(session.id)}
              className={`group relative flex flex-col p-4 rounded-xl cursor-pointer transition-all border ${activeSessionId === session.id
                ? 'bg-blue-50 border-blue-200'
                : 'hover:bg-slate-50 border-transparent hover:border-slate-200'
                }`}
            >
              <div className="flex items-center gap-3 pr-8">
                <div className={`p-2 rounded-lg shrink-0 ${activeSessionId === session.id ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-400'}`}>
                  <IoTimeOutline size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  {editingId === session.id ? (
                    <Input
                      autoFocus
                      className="h-7 text-sm p-1"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.key === 'Enter' && saveEdit(e, session.id)}
                    />
                  ) : (
                    <p className={`text-sm font-semibold truncate ${activeSessionId === session.id ? 'text-blue-700' : 'text-slate-700'}`}>
                      {session.title}
                    </p>
                  )}
                </div>
              </div>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {editingId === session.id ? (
                  <button onClick={(e) => saveEdit(e, session.id)} className="p-1.5 text-blue-600"><IoCheckmarkOutline size={16} /></button>
                ) : (
                  <>
                    <button onClick={(e) => startEdit(e, session)} className="p-1.5 text-slate-400 hover:text-blue-600"><IoPencilOutline size={14} /></button>
                    <button onClick={(e) => handleDelete(e, session.id)} className="p-1.5 text-slate-400 hover:text-red-500"><IoTrashOutline size={14} /></button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="flex-1 h-full flex flex-col relative bg-white">
        <header className="h-20 shrink-0 bg-white border-b border-slate-200 px-6 flex items-center justify-between z-20">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="text-slate-500 hover:bg-slate-100 rounded-lg"
            >
              <IoMenuOutline size={26} />
            </Button>
            <div className="flex items-center gap-3 ml-2">
              <Avatar className="h-10 w-10 border border-blue-100">
                <AvatarFallback className="bg-blue-600 text-white font-bold">AI</AvatarFallback>
              </Avatar>
              <div>
                <h2 className="text-base font-bold text-slate-800">법률 어시스턴트</h2>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-[12px] text-slate-500 font-medium font-sans">Online</span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {activeSessionId ? (
          <>
            <div ref={scrollRef} className="flex-1 overflow-y-auto bg-slate-50/20 p-8">
              <div className="max-w-[900px] mx-auto space-y-6">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`flex gap-3 max-w-[80%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                      {msg.sender === 'ai' && (
                        <Avatar className="h-8 w-8 shrink-0 mt-1">
                          <AvatarFallback className="bg-white text-blue-600 font-bold text-[10px] border border-slate-200">AI</AvatarFallback>
                        </Avatar>
                      )}
                      <div className={`p-4 rounded-2xl shadow-sm text-[15px] leading-relaxed flex flex-col ${msg.sender === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white text-slate-800 border border-slate-200 rounded-tl-none'
                        }`}>
                        {(msg.referenceDoc || msg.referenceGroup) && (
                          <div className="flex flex-col gap-1 mb-2">
                            {msg.referenceDoc && (
                              <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs w-fit border ${msg.sender === 'user' ? 'bg-white/20 text-blue-50 border-blue-400/30' : 'bg-slate-100 text-slate-600 border-slate-200'
                                }`}>
                                <IoDocumentTextOutline size={14} /> {msg.referenceDoc.title}
                              </div>
                            )}
                            {msg.referenceGroup && (
                              <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs w-fit border ${msg.sender === 'user' ? 'bg-white/20 text-blue-50 border-blue-400/30' : 'bg-slate-100 text-slate-600 border-slate-200'
                                }`}>
                                <IoPeopleOutline size={14} /> {msg.referenceGroup.name}
                              </div>
                            )}
                          </div>
                        )}
                        <p className="whitespace-pre-wrap">{msg.text}</p>
                        <span className={`text-[10px] mt-2 block ${msg.sender === 'user' ? 'text-blue-200 text-right' : 'text-slate-400 text-left'}`}>
                          {msg.timestamp}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start items-center gap-3 ml-11">
                    <div className="px-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm flex gap-1.5">
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="shrink-0 p-6 bg-white border-t border-slate-100 relative">
              <div className="max-w-[900px] mx-auto relative">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  className="hidden"
                  accept=".pdf,.doc,.docx,.hwp,.txt"
                />

                {(showDocSelect || showGroupSelect) && (
                  <div className="absolute bottom-full left-0 right-0 mb-3 bg-white border border-slate-200 rounded-xl shadow-lg p-3 z-30 animate-in slide-in-from-bottom-2 fade-in duration-200">
                    <div className="flex justify-between items-center mb-3 px-2 pt-1">
                      <span className="text-sm font-bold text-slate-700">
                        {showDocSelect ? '검토할 문서 선택' : '참조할 그룹 선택'}
                      </span>
                      <button
                        onClick={() => { setShowDocSelect(false); setShowGroupSelect(false); }}
                        className="text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        <IoClose size={20} />
                      </button>
                    </div>

                    <div className="max-h-60 overflow-y-auto space-y-1.5">
                      {showDocSelect && (
                        <>
                          <button
                            onClick={() => fileInputRef.current?.click()}
                            className="w-full text-left px-3 py-3 text-sm text-blue-600 hover:bg-blue-50 bg-blue-50/50 rounded-xl flex items-center gap-2 transition-colors border border-dashed border-blue-200 mb-3 font-medium"
                          >
                            <IoCloudUploadOutline size={20} /> 내 PC에서 새 파일 업로드
                          </button>

                          <div className="px-2 pt-1 pb-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider">최근 문서</div>
                          {dummyDocuments.map(doc => (
                            <button
                              key={doc.id}
                              onClick={() => { setSelectedDoc(doc); setShowDocSelect(false); }}
                              className="w-full text-left px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-100 rounded-xl flex items-center gap-2 transition-colors"
                            >
                              <IoDocumentTextOutline className="text-slate-400" size={18} /> {doc.title}
                            </button>
                          ))}
                        </>
                      )}

                      {showGroupSelect && dummyGroups.map(group => (
                        <button
                          key={group.id}
                          onClick={() => { setSelectedGroup(group); setShowGroupSelect(false); }}
                          className="w-full text-left px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-100 rounded-xl flex items-center gap-2 transition-colors"
                        >
                          <IoPeopleOutline className="text-slate-400" size={18} /> {group.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex flex-col bg-slate-50/80 rounded-2xl border border-slate-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 focus-within:bg-white transition-all shadow-sm">
                  {(selectedDoc || selectedGroup) && (
                    <div className="flex flex-wrap gap-2 px-4 pt-4 pb-1">
                      {selectedDoc && (
                        <span className="flex items-center gap-1.5 text-sm bg-blue-100 text-blue-700 px-3 py-1.5 rounded-lg border border-blue-200 animate-in fade-in">
                          <IoDocumentTextOutline size={16} />
                          <span className="max-w-[200px] truncate">{selectedDoc.title}</span>
                          <button onClick={() => setSelectedDoc(null)} className="hover:text-blue-900 ml-0.5"><IoCloseCircle size={16} /></button>
                        </span>
                      )}
                      {selectedGroup && (
                        <span className="flex items-center gap-1.5 text-sm bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg border border-emerald-200 animate-in fade-in">
                          <IoPeopleOutline size={16} />
                          <span className="max-w-[200px] truncate">{selectedGroup.name}</span>
                          <button onClick={() => setSelectedGroup(null)} className="hover:text-emerald-900 ml-0.5"><IoCloseCircle size={16} /></button>
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex gap-2 items-center p-2">
                    <Input
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                      placeholder={selectedDoc || selectedGroup ? "내용을 입력하거나 바로 전송하세요" : "상담 내용을 입력하세요..."}
                      className="flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 px-3 h-12 text-base"
                    />
                    <Button
                      size="icon"
                      onClick={handleSend}
                      disabled={(!inputText.trim() && !selectedDoc && !selectedGroup) || isLoading}
                      className="shrink-0 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-xl w-12 h-12 shadow-md transition-all"
                    >
                      <IoSend size={20} className="ml-1" />
                    </Button>
                  </div>

                  <div className="flex items-center gap-2 px-4 pb-3">
                    <Button
                      variant="outline" size="sm"
                      onClick={toggleDocSelect}
                      className={`h-8 text-[12px] font-medium rounded-full gap-1.5 shadow-sm px-3.5 border-slate-200 transition-colors ${showDocSelect ? 'bg-slate-200 text-slate-900' : 'bg-white text-slate-600 hover:bg-slate-100'}`}
                    >
                      <IoAdd size={16} /> 문서 검토
                    </Button>
                    <Button
                      variant="outline" size="sm"
                      onClick={toggleGroupSelect}
                      className={`h-8 text-[12px] font-medium rounded-full gap-1.5 shadow-sm px-3.5 border-slate-200 transition-colors ${showGroupSelect ? 'bg-slate-200 text-slate-900' : 'bg-white text-slate-600 hover:bg-slate-100'}`}
                    >
                      <IoFolderOpenOutline size={16} /> 그룹 참조
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center bg-slate-50/10">
            <div className="w-24 h-24 bg-blue-50 text-blue-600 rounded-[2.5rem] flex items-center justify-center mb-8 border border-blue-100 shadow-inner">
              <IoChatbubbleEllipsesOutline size={48} />
            </div>
            <h2 className="text-3xl font-bold text-slate-800 mb-3">Legal AI Assistant</h2>
            <p className="text-slate-500 max-w-sm text-center font-medium">사이드바에서 상담을 선택하거나 새 상담을 시작하여 AI 분석을 받아보세요.</p>
          </div>
        )}
      </main>
    </div>
  );
}