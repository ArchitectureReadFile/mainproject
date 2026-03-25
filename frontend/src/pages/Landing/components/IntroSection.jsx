import { Button } from "@/components/ui/Button.jsx";
import { Scale, ChevronDown } from 'lucide-react';

export default function IntroSection({ onStartClick }) {
  return (
    <section className="h-[calc(100vh-72px)] w-full snap-start snap-always flex flex-col items-center justify-center p-20 bg-background relative overflow-hidden box-border">
      <div className="absolute top-0 left-0 w-full h-full opacity-[0.03] dark:opacity-[0.07] pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-blue-600 rounded-full blur-[150px]" />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-indigo-600 rounded-full blur-[120px]" />
      </div>
      <div className="max-w-4xl text-center z-10 flex flex-col items-center">
        <Scale className="w-20 h-20 text-blue-600 mb-8 opacity-90" />
        <h2 className="text-8xl font-black text-foreground mb-10 tracking-tighter leading-[1.05]">
          복잡한 법률 상담,<br />
          <span className="text-blue-600">인공지능</span>이 답하다.
        </h2>
        <p className="text-2xl text-muted-foreground mb-16 max-w-2xl mx-auto leading-relaxed font-medium">
          계약서 분석부터 실시간 법률 조언까지 도와드립니다.
        </p>
        <Button
          onClick={onStartClick}
          className="bg-blue-600 hover:bg-blue-700 text-white px-14 py-9 text-2xl rounded-2xl shadow-2xl font-bold transition-all hover:scale-105 active:scale-95"
        >
          상담 시작하기
        </Button>
        <ChevronDown 
          className="w-12 h-12 text-slate-300 dark:text-slate-600 mt-12 animate-bounce cursor-pointer hover:text-blue-400 transition-colors" 
          onClick={onStartClick}
        />
      </div>
    </section>
  );
}
