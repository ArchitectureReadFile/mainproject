import { IoCloudUploadOutline, IoDocumentTextOutline, IoCheckmarkOutline } from 'react-icons/io5';

export default function GuideSection() {
  const guideItems = [
    { title: '문서 업로드', desc: '분석이 필요한 계약서나 서류를 업로드하세요.', icon: <IoCloudUploadOutline size={32} /> },
    { title: '실시간 분석', desc: 'AI가 법률 데이터베이스를 바탕으로 내용을 분석합니다.', icon: <IoDocumentTextOutline size={32} /> },
    { title: '결과 확인', desc: '상세한 분석 결과와 전문적인 조언을 확인하세요.', icon: <IoCheckmarkOutline size={32} /> }
  ];

  return (
    <section className="min-h-[calc(100vh-72px)] w-full snap-start snap-always flex flex-col items-center justify-center p-6 md:p-20 bg-background overflow-hidden box-border py-16 md:py-20">
      <h2 className="text-3xl md:text-6xl font-black text-foreground mb-4">이용 가이드</h2>
      <p className="text-base md:text-xl text-muted-foreground mb-10 md:mb-16 font-medium text-center px-4">세 단계로 이루어지는 스마트한 법률 조언 서비스</p>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-10 max-w-6xl w-full px-4 md:px-0">
        {guideItems.map((item, i) => (
          <div key={i} className="group p-8 md:p-12 rounded-3xl md:rounded-[3rem] bg-slate-50 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800 text-center hover:bg-white dark:hover:bg-slate-900 hover:shadow-[0_32px_64px_-16px_rgba(0,0,0,0.08)] transition-all duration-500">
            <div className="w-16 h-16 md:w-20 md:h-20 bg-white dark:bg-slate-800 rounded-2xl md:rounded-3xl shadow-sm mx-auto mb-6 md:mb-8 flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform duration-500">
              {item.icon}
            </div>
            <h4 className="text-xl md:text-2xl font-bold text-foreground mb-3 md:mb-4">{item.title}</h4>
            <p className="text-sm md:text-base text-slate-500 dark:text-slate-400 leading-relaxed font-medium">{item.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
