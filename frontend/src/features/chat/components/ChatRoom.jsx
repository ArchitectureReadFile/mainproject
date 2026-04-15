import { useState, useEffect, useRef } from 'react';
import {
  IoArrowBack,
  IoSend,
  IoClose,
  IoAdd,
  IoFolderOpenOutline,
  IoDocumentTextOutline,
  IoPeopleOutline,
  IoCloseCircle,
  IoCloudUploadOutline,
  IoEllipsisHorizontal
} from 'react-icons/io5';
import { Button } from "@/components/ui/Button.jsx";
import { Input } from "@/components/ui/Input.jsx";
import { Avatar, AvatarFallback } from "@/components/ui/Avatar.jsx";
import { useChat } from '../hooks/useChat.js';

export default function ChatRoom({ sessionId, onBack, onClose }) {
  const { messages, isLoading, sendMessage } = useChat(sessionId);
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  const fileInputRef = useRef(null);

  const [showDocSelect, setShowDocSelect] = useState(false);
  const [showGroupSelect, setShowGroupSelect] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);

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
    if (!input.trim() && !selectedDoc && !selectedGroup) return;

    sendMessage(input, selectedDoc, selectedGroup);

    setInput('');
    setSelectedDoc(null);
  };

  const toggleDocSelect = () => {
    setShowDocSelect(!showDocSelect);
    setShowGroupSelect(false);
  };

  const toggleGroupSelect = () => {
    setShowGroupSelect(!showGroupSelect);
    setShowDocSelect(false);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 relative">
      <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800 shadow-sm z-10">
        <div className="flex items-center gap-2 sm:gap-3">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={(e) => {
              e.stopPropagation();
              if (onBack) onBack();
            }} 
            className="text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full w-10 h-10 flex items-center justify-center transition-colors"
          >
            <IoArrowBack size={22} />
          </Button>
          <div className="flex items-center gap-2 sm:gap-2.5">
            <Avatar className="h-8 w-8 sm:h-9 sm:w-9 border border-slate-100 dark:border-slate-800 shadow-sm">
              <AvatarFallback className="bg-blue-600 text-white text-[10px] sm:text-xs font-bold">AI</AvatarFallback>
            </Avatar>
            <div className="flex flex-col justify-center">
              <p className="text-sm font-bold text-slate-800 dark:text-foreground leading-tight">법률 어시스턴트</p>
              <div className="flex items-center gap-1 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span className="text-[10px] sm:text-[11px] text-slate-500 dark:text-slate-400 font-medium leading-none">Online</span>
              </div>
            </div>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full w-9 h-9">
          <IoClose size={22} />
        </Button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-4 sm:space-y-5">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] sm:max-w-[75%] px-3 py-2 sm:px-4 sm:py-2.5 rounded-2xl shadow-sm text-[14px] sm:text-[14.5px] leading-relaxed flex flex-col ${msg.sender === 'user'
              ? 'bg-blue-600 text-white rounded-br-sm'
              : msg.isError
                ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/30 rounded-bl-sm'
                : 'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-bl-sm'
              }`}>

              {(msg.referenceDoc || msg.referenceGroup) && (
                <div className="flex flex-col gap-1 mb-2">
                  {msg.referenceDoc && (
                    <div className="flex items-center gap-1.5 bg-white/20 text-blue-50 px-2 py-1 rounded-md text-[11px] w-fit border border-blue-400/30">
                      <IoDocumentTextOutline size={14} /> {msg.referenceDoc.title}
                    </div>
                  )}
                  {msg.referenceGroup && (
                    <div className="flex items-center gap-1.5 bg-white/20 text-blue-50 px-2 py-1 rounded-md text-[11px] w-fit border border-blue-400/30">
                      <IoPeopleOutline size={14} /> {msg.referenceGroup.name}
                    </div>
                  )}
                </div>
              )}

              <p>{msg.text}</p>
              <p className={`text-[10px] mt-1.5 text-right ${msg.sender === 'user' ? 'text-blue-200' : 'text-slate-400 dark:text-slate-500'}`}>
                {msg.timestamp}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="px-4 py-3 rounded-2xl shadow-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-bl-sm flex items-center gap-2">
              <IoEllipsisHorizontal className="text-slate-400 animate-pulse" size={20} />
            </div>
          </div>
        )}
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".pdf,.doc,.docx,.hwp,.txt"
      />

      <div className="p-3 bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 relative z-20">
        {(showDocSelect || showGroupSelect) && (
          <div className="absolute bottom-full left-3 right-3 mb-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg p-2 z-30 animate-in slide-in-from-bottom-2 fade-in duration-200">
            <div className="flex justify-between items-center mb-2 px-2 pt-1">
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">
                {showDocSelect ? '검토할 문서 선택' : '참조할 그룹 선택'}
              </span>
              <button
                onClick={() => { setShowDocSelect(false); setShowGroupSelect(false); }}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
              >
                <IoClose size={18} />
              </button>
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1">
              {showDocSelect && (
                <>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full text-left px-3 py-2.5 text-sm text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 bg-blue-50/50 dark:bg-blue-900/10 rounded-lg flex items-center gap-2 transition-colors border border-dashed border-blue-200 dark:border-blue-800 mb-2 font-medium"
                  >
                    <IoCloudUploadOutline size={18} /> 내 PC에서 새 파일 업로드
                  </button>

                  <div className="px-2 pt-1 pb-0.5 text-[10px] font-semibold text-slate-400 dark:text-slate-500">최근 문서</div>
                  {dummyDocuments.map(doc => (
                    <button
                      key={doc.id}
                      onClick={() => { setSelectedDoc(doc); setShowDocSelect(false); }}
                      className="w-full text-left px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg flex items-center gap-2 transition-colors"
                    >
                      <IoDocumentTextOutline className="text-slate-400 dark:text-slate-500" size={16} /> {doc.title}
                    </button>
                  ))}
                </>
              )}

              {showGroupSelect && dummyGroups.map(group => (
                <button
                  key={group.id}
                  onClick={() => { setSelectedGroup(group); setShowGroupSelect(false); }}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg flex items-center gap-2 transition-colors"
                >
                  <IoPeopleOutline className="text-slate-400 dark:text-slate-500" size={16} /> {group.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col bg-slate-100/50 dark:bg-slate-900/50 rounded-[2rem] border border-slate-200 dark:border-slate-800 focus-within:bg-white dark:focus-within:bg-slate-900 focus-within:border-blue-400 dark:focus-within:border-blue-500 transition-all duration-500 shadow-sm">
          {(selectedDoc || selectedGroup) && (
            <div className="flex flex-wrap gap-2 px-3 pt-3 pb-1">
              {selectedDoc && (
                <span className="flex items-center gap-1.5 text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-md border border-blue-200 dark:border-blue-800 animate-in fade-in">
                  <IoDocumentTextOutline size={14} />
                  <span className="max-w-[150px] truncate">{selectedDoc.title}</span>
                  <button onClick={() => setSelectedDoc(null)} className="hover:text-blue-900 dark:hover:text-blue-100"><IoCloseCircle size={15} /></button>
                </span>
              )}
              {selectedGroup && (
                <span className="flex items-center gap-1.5 text-xs bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 px-2 py-1 rounded-md border border-emerald-200 dark:border-emerald-800 animate-in fade-in">
                  <IoPeopleOutline size={14} />
                  <span className="max-w-[150px] truncate">{selectedGroup.name}</span>
                  <button onClick={() => setSelectedGroup(null)} className="hover:text-emerald-900 dark:hover:text-emerald-100"><IoCloseCircle size={15} /></button>
                </span>
              )}
            </div>
          )}

          <div className="flex gap-2 items-center p-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder={selectedDoc || selectedGroup ? "내용을 입력하거나 바로 전송하세요" : "메시지를 입력하세요..."}
              className="flex-1 border-0 bg-transparent shadow-none focus:ring-0 focus:outline-none focus:border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 h-10 text-slate-800 dark:text-slate-200"
            />
            <Button size="icon" onClick={handleSend} disabled={isLoading} className="shrink-0 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-full w-10 h-10 shadow-sm">
              <IoSend size={18} className="ml-1" />
            </Button>
          </div>

          <div className="flex items-center gap-2 px-3 pb-2">
            <Button
              variant="outline" size="sm"
              onClick={toggleDocSelect}
              className={`h-7 text-[10px] sm:text-[11px] rounded-full gap-1.5 shadow-sm px-2.5 sm:px-3 border-slate-200 dark:border-slate-700 transition-colors ${showDocSelect ? 'bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
            >
              <IoAdd size={14} /> 문서 검토
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={toggleGroupSelect}
              className={`h-7 text-[10px] sm:text-[11px] rounded-full gap-1.5 shadow-sm px-2.5 sm:px-3 border-slate-200 dark:border-slate-700 transition-colors ${showGroupSelect ? 'bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
            >
              <IoFolderOpenOutline size={14} /> 그룹 참조
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}