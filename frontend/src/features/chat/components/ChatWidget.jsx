import { useEffect, useState, useCallback } from 'react';
import nongdamgom from '@/shared/assets/nongdamgom.png';
import { Card } from "@/shared/ui/card.jsx";
import ChatList from './ChatList';
import ChatSession from './ChatSession';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeSession, setActiveSession] = useState(null);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [footerOffset, setFooterOffset] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleSessionUpdate = useCallback((updatedSession) => {
    setActiveSession(prev => {
      if (!prev) return prev;
      const isChanged = Object.keys(updatedSession).some(key => prev[key] !== updatedSession[key]);
      return isChanged ? { ...prev, ...updatedSession } : prev;
    });
    setRefreshTrigger(prev => prev + 1);
  }, []);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      document.body.style.touchAction = 'none';
    } else {
      document.body.style.overflow = '';
      document.body.style.touchAction = '';
    }
    return () => {
      document.body.style.overflow = '';
      document.body.style.touchAction = '';
    };
  }, [isOpen]);

  useEffect(() => {
    let lastScrollY = window.scrollY;
    let ticking = false;
    let timeoutId = null;

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const currentScrollY = window.scrollY;
          if (currentScrollY > lastScrollY) setScrollOffset(15);
          else if (currentScrollY < lastScrollY) setScrollOffset(-15);
          lastScrollY = currentScrollY;
          
          const footer = document.querySelector('footer');
          if (footer) {
            const footerRect = footer.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            if (footerRect.top < viewportHeight) {
              setFooterOffset(viewportHeight - footerRect.top);
            } else {
              setFooterOffset(0);
            }
          }

          ticking = false;
          clearTimeout(timeoutId);
          timeoutId = setTimeout(() => setScrollOffset(0), 200);
        });
        ticking = true;
      }
    };

    handleScroll();

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll);
    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
      clearTimeout(timeoutId);
    };
  }, []);

  return (
    <>
      {isOpen && (
        <Card 
          className="fixed inset-0 sm:inset-auto sm:right-[20px] z-[10000] w-full h-full sm:w-[360px] sm:h-[550px] flex flex-col overflow-hidden shadow-2xl border-none sm:border sm:border-slate-200 sm:dark:border-slate-800 animate-in slide-in-from-bottom sm:zoom-in duration-300 sm:duration-200 origin-bottom sm:origin-bottom-right sm:rounded-3xl"
          style={{
            bottom: window.innerWidth >= 640 ? `${20 + footerOffset}px` : '0'
          }}
        >
          <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-slate-900">
            {activeSession ? (
              <ChatSession
                session={activeSession}
                onBack={() => setActiveSession(null)}
                onClose={() => setIsOpen(false)}
                onUpdateSession={handleSessionUpdate}
              />
            ) : (
              <ChatList
                onSelectRoom={(session) => setActiveSession(session)}
                onClose={() => setIsOpen(false)}
                refreshTrigger={refreshTrigger}
              />
            )}
          </div>
        </Card>
      )}

      {!isOpen && (
        <div
          className="fixed right-2 sm:right-[15px] z-[9999] transition-all duration-300 ease-out"
          style={{
            bottom: `${20 + footerOffset}px`,
            transform: `translateY(${scrollOffset}px)`
          }}
        >
          <button
            onClick={() => setIsOpen(true)}
            className="w-[70px] h-[70px] sm:w-[90px] sm:h-[90px] rounded-full transition-all duration-300 hover:scale-110 active:scale-90 flex items-center justify-center overflow-hidden"
          >
            <img
              src={nongdamgom}
              alt="캐릭터"
              className="w-full h-full object-cover rounded-full p-1"
            />
          </button>
        </div>
      )}
    </>
  );
}
