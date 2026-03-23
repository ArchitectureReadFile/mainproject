import { useEffect, useState } from 'react';
import nongdamgom from '../../../assets/nongdamgom.png';
import { Card } from "@/components/ui/Card.jsx";
import ChatList from './ChatList';
import ChatSession from './ChatSession';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [footerOffset, setFooterOffset] = useState(0);

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
        <Card className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[10000] w-[calc(100%-32px)] min-w-[400px] max-w-[800px] h-[600px] flex flex-col overflow-hidden shadow-2xl border-slate-200 animate-in fade-in zoom-in duration-200">
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            {activeSessionId ? (
              <ChatSession
                sessionId={activeSessionId}
                onBack={() => setActiveSessionId(null)}
                onClose={() => setIsOpen(false)}
              />
            ) : (
              <ChatList
                onSelectRoom={(id) => setActiveSessionId(id)}
                onClose={() => setIsOpen(false)}
              />
            )}
          </div>
        </Card>
      )}

      {!isOpen && (
        <div
          className="fixed right-[15px] z-[9999] transition-all duration-300 ease-out"
          style={{
            bottom: `${30 + footerOffset}px`,
            transform: `translateY(${scrollOffset}px)`
          }}
        >
          <button
            onClick={() => setIsOpen(true)}
            className={`w-[90px] h-[90px] rounded-full transition-all duration-300 hover:scale-110 active:scale-90 flex items-center justify-center overflow-hidden }`}
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