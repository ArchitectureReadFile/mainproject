import { useState, useEffect, useMemo } from 'react';
import { IoHomeOutline, IoChatbubbleEllipsesOutline, IoInformationCircleOutline } from 'react-icons/io5';
import { useAuth } from '@/features/auth/context/AuthContext';
import IntroSection from './components/IntroSection';
import ChatSection from './components/ChatSection';
import GuideSection from './components/GuideSection';
import SideNavigation from './components/SideNavigation';

export default function LandingPage() {
  const { isAuthenticated, openAuthModal } = useAuth();
  const [currentSection, setCurrentSection] = useState(0);

  const activeSections = useMemo(() => [
    { id: 'home', label: '메인', icon: <IoHomeOutline size={22} /> },
    ...(isAuthenticated ? [{ id: 'chat', label: '채팅', icon: <IoChatbubbleEllipsesOutline size={22} /> }] : []),
    { id: 'guide', label: '가이드', icon: <IoInformationCircleOutline size={22} /> },
  ], [isAuthenticated]);

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      const height = window.innerHeight - 72; 
      const index = Math.min(Math.round(scrollY / height), activeSections.length - 1);
      setCurrentSection(index);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [activeSections.length]);

  const scrollToSection = (index) => {
    const height = window.innerHeight - 72;
    window.scrollTo({
      top: index * height,
      behavior: 'smooth'
    });
    setCurrentSection(index);
  };

  const handleStartClick = () => {
    if (isAuthenticated) {
      scrollToSection(1);
    } else {
      openAuthModal('login');
    }
  };

  return (
    <div className="relative w-full bg-background text-foreground selection:bg-blue-100 selection:text-blue-700 dark:selection:bg-blue-900 dark:selection:text-blue-200">
      
      <SideNavigation 
        sections={activeSections} 
        currentSection={currentSection} 
        onSectionClick={scrollToSection} 
      />

      <main className="w-full bg-background">
        <IntroSection onStartClick={handleStartClick} />
        {isAuthenticated && <ChatSection />}
        <GuideSection />
      </main>

      <style>{`
        html {
          scroll-snap-type: y mandatory;
          scroll-padding-top: 72px;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        html::-webkit-scrollbar {
          display: none;
        }
        body {
          margin: 0;
          padding: 0;
          overflow-x: hidden;
        }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #cbd5e1; }
        .snap-always {
          snap-stop: always;
        }
      `}</style>
    </div>
  );
}
