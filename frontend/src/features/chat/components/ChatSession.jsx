import { Avatar, AvatarFallback } from "@/components/ui/Avatar.jsx";
import { Button } from "@/components/ui/Button.jsx";
import { Input } from "@/components/ui/Input.jsx";
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  IoAdd,
  IoArrowBack,
  IoClose,
  IoCloseCircle,
  IoCloudUploadOutline,
  IoDocumentTextOutline,
  IoFolderOpenOutline,
  IoPeopleOutline,
  IoSend,
  IoStop
} from 'react-icons/io5';
import { getMyGroups } from '../../../api/groups';
import { useChat } from '../hooks/useChat.js';

export default function ChatSession({ session, onBack, onClose, onUpdateSession }) {
  const initialGroup = session.reference_group_id ? { id: session.reference_group_id, name: session.reference_group_name } : null;
  const { 
    messages, 
    isLoading, 
    sendMessage, 
    stopMessage,
    referenceTitle, 
    referenceGroup,
    removeReferenceDocument,
    removeReferenceGroup
  } = useChat(session.id, session.reference_document_title, initialGroup);
  
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  useEffect(() => {
    if (onUpdateSession) {
      const hasTitleChanged = referenceTitle !== (session.reference_document_title || null);
      const hasGroupChanged = referenceGroup?.id !== (session.reference_group_id || null);

      if (hasTitleChanged || hasGroupChanged) {
        onUpdateSession({ 
          reference_document_title: referenceTitle,
          reference_group_id: referenceGroup?.id,
          reference_group_name: referenceGroup?.name
        });
      }
    }
  }, [referenceTitle, referenceGroup, session.reference_document_title, session.reference_group_id, onUpdateSession]);

  const fileInputRef = useRef(null);

  const [showDocSelect, setShowDocSelect] = useState(false);
  const [showGroupSelect, setShowGroupSelect] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [groups, setGroups] = useState([]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const { groups } = await getMyGroups()
        setGroups(groups)
      } catch (error) {
        console.error('Failed to fetch groups:', error)
      }
    }
    fetchGroups();
  }, []);

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
    if (!input.trim() && !selectedDoc && !selectedGroup && !referenceTitle && !referenceGroup) return;

    let workspaceSelection = null;
    const groupToUse = selectedGroup || referenceGroup;
    if (groupToUse) {
      workspaceSelection = {
        mode: "all",
        document_ids: []
      };
    }

    sendMessage(input, selectedDoc, selectedGroup, workspaceSelection);

    setInput('');
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

  const MarkdownComponents = {
    p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap break-words">{children}</p>,
    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
    li: ({ children }) => <li className="mb-0 break-all break-words">{children}</li>,
    code: ({ inline, children }) => (
      inline
        ? <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded text-pink-600 dark:text-pink-400 font-mono text-xs">{children}</code>
        : <code className="block bg-slate-100 dark:bg-slate-800 p-2 rounded-lg font-mono text-xs overflow-x-auto my-2 border border-slate-200 dark:border-slate-700">{children}</code>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-slate-200 dark:border-slate-700 pl-3 italic my-2 text-slate-600 dark:text-slate-400">
        {children}
      </blockquote>
    ),
    h1: ({ children }) => <h1 className="text-lg font-bold mb-2 border-b pb-1">{children}</h1>,
    h2: ({ children }) => <h2 className="text-base font-bold mb-1.5">{children}</h2>,
    h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
    table: ({ children }) => (
      <div className="overflow-x-auto my-3">
        <table className="min-w-full border-collapse border border-slate-200 dark:border-slate-700 text-xs">
          {children}
        </table>
      </div>
    ),
    th: ({ children }) => <th className="border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-2 font-bold">{children}</th>,
    td: ({ children }) => <td className="border border-slate-200 dark:border-slate-700 p-2">{children}</td>,
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
            </div>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full w-9 h-9">
          <IoClose size={22} />
        </Button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-4 sm:space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            <div className={`max-w-[88%] sm:max-w-[85%] px-3 py-2 sm:px-4 sm:py-3 rounded-2xl shadow-sm text-[13.5px] sm:text-[14px] leading-relaxed flex flex-col ${msg.sender === 'user'
              ? 'bg-blue-600 text-white rounded-br-sm'
              : msg.isError
                ? 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/50 rounded-bl-sm'
                : 'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-bl-sm'
              }`}>

              {(msg.referenceDoc || msg.referenceGroup) && (
                <div className="flex flex-col gap-1 mb-2.5">
                  {msg.referenceDoc && (
                    <div className="flex items-center gap-1.5 bg-blue-50/20 dark:bg-blue-900/20 text-blue-50 dark:text-blue-200 px-2 py-1 rounded-md text-[11px] w-fit border border-blue-400/30">
                      <IoDocumentTextOutline size={13} /> {msg.referenceDoc.title}
                    </div>
                  )}
                  {msg.referenceGroup && (
                    <div className="flex items-center gap-1.5 bg-blue-50/20 dark:bg-blue-900/20 text-blue-50 dark:text-blue-200 px-2 py-1 rounded-md text-[11px] w-fit border border-blue-400/30">
                      <IoPeopleOutline size={13} /> {msg.referenceGroup.name}
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

              <p className={`text-[10px] mt-2 text-right opacity-70 ${msg.sender === 'user' ? 'text-blue-50' : 'text-slate-400 dark:text-slate-500'}`}>
                {msg.timestamp}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start animate-in fade-in duration-300">
            <div className="px-4 py-3 rounded-2xl shadow-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-bl-sm flex items-center gap-2">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"></span>
              </span>
              <span className="text-xs text-slate-400 font-medium">AI 분석 중...</span>
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
                </>
              )}

              {showGroupSelect && groups.map(group => (
                <button
                  key={group.id}
                  onClick={() => { setSelectedGroup(group); setShowGroupSelect(false); }}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg flex items-center gap-2 transition-colors"
                >
                  <IoPeopleOutline className="text-slate-400 dark:text-slate-500" size={16} /> {group.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col bg-slate-100/50 dark:bg-slate-900/50 rounded-[2rem] border border-slate-200 dark:border-slate-800 focus-within:bg-white dark:focus-within:bg-slate-900 focus-within:border-blue-400 dark:focus-within:border-blue-500 transition-all duration-500 shadow-sm">
          {(referenceTitle || referenceGroup || selectedDoc || selectedGroup) && (
            <div className="flex flex-wrap gap-2 px-3 pt-3 pb-1">
              {referenceTitle && !selectedDoc && (
                <span className="flex items-center gap-1.5 text-xs bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 px-2 py-1 rounded-md border border-indigo-200 dark:border-indigo-800 animate-in fade-in" title="이 문서를 기반으로 답변합니다">
                  <IoDocumentTextOutline size={14} />
                  <span className="max-w-[150px] truncate font-medium">{referenceTitle}</span>
                  <span className="text-[10px] opacity-70 ml-1">(참조 중)</span>
                  <button onClick={removeReferenceDocument} className="hover:text-indigo-900 dark:hover:text-indigo-100 ml-0.5"><IoCloseCircle size={15} /></button>
                </span>
              )}
              {selectedDoc && (
                <span className="flex items-center gap-1.5 text-xs bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-md border border-blue-200 dark:border-blue-800 animate-in fade-in">
                  <IoDocumentTextOutline size={14} />
                  <span className="max-w-[150px] truncate">{selectedDoc.title}</span>
                  <button onClick={() => setSelectedDoc(null)} className="hover:text-blue-900 dark:hover:text-blue-100"><IoCloseCircle size={15} /></button>
                </span>
              )}
              {(referenceGroup || selectedGroup) && (
                <span className="flex items-center gap-1.5 text-xs bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 px-2 py-1 rounded-md border border-emerald-200 dark:border-emerald-800 animate-in fade-in">
                  <IoPeopleOutline size={14} />
                  <span className="max-w-[150px] truncate">{selectedGroup?.name || referenceGroup?.name}</span>
                  {!selectedGroup && referenceGroup && <span className="text-[10px] opacity-70 ml-1">(참조 중)</span>}
                  <button onClick={() => { selectedGroup ? setSelectedGroup(null) : removeReferenceGroup(); }} className="hover:text-emerald-900 dark:hover:text-emerald-100"><IoCloseCircle size={15} /></button>
                </span>
              )}
            </div>
          )}

          <div className="flex gap-2 items-center p-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder={referenceTitle || referenceGroup || selectedDoc || selectedGroup ? "내용을 입력하거나 바로 전송하세요" : "메시지를 입력하세요..."}
              className="flex-1 border-0 bg-transparent shadow-none focus:ring-0 focus:outline-none focus:border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 h-10 text-foreground"
            />
            {isLoading ? (
              <Button size="icon" onClick={stopMessage} className="shrink-0 bg-slate-500 hover:bg-slate-600 rounded-full w-10 h-10 shadow-sm">
                <IoStop size={18} />
              </Button>
            ) : (
              <Button size="icon" onClick={handleSend} className="shrink-0 bg-blue-600 hover:bg-blue-700 rounded-full w-10 h-10 shadow-sm">
                <IoSend size={18} className="ml-1" />
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2 px-3 pb-2">
            <Button
              variant="outline" size="sm"
              onClick={toggleDocSelect}
              className={`h-7 text-[11px] rounded-full gap-1.5 shadow-sm px-3 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showDocSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}
            >
              <IoAdd size={14} /> 문서 검토
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={toggleGroupSelect}
              className={`h-7 text-[11px] rounded-full gap-1.5 shadow-sm px-3 border-slate-200 dark:border-slate-700 transition-all duration-200 font-bold cursor-pointer ${showGroupSelect ? 'bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-white hover:text-white dark:text-slate-800 dark:hover:text-slate-800 border-slate-800 dark:border-slate-200' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}`}
            >
              <IoFolderOpenOutline size={14} /> 그룹 참조
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
