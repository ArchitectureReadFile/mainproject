export default function SideNavigation({ sections, currentSection, onSectionClick }) {
  return (
    <div className="fixed left-3 top-1/2 -translate-y-1/2 z-50 flex flex-col items-start gap-4">
      {sections.map((section, idx) => (
        <button
          key={section.id}
          onClick={() => onSectionClick(idx)}
          className="group flex flex-row items-center gap-3 transition-all duration-300 py-2 cursor-pointer"
          title={section.label}
        >
          <div 
            className={`w-[6px] rounded-full transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] ${
              currentSection === idx 
                ? 'bg-blue-600 h-16 shadow-[0_0_20px_rgba(37,99,235,0.5)]' 
                : 'bg-slate-200 dark:bg-slate-800 h-8 group-hover:bg-slate-400 dark:group-hover:bg-slate-600 group-hover:h-10'
            }`} 
          />
          <span 
            className={`text-sm font-bold transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] ${
              currentSection === idx 
                ? 'opacity-100 translate-x-0 text-black dark:text-white' 
                : 'opacity-0 -translate-x-2 pointer-events-none'
            }`}
          >
            {section.label}
          </span>
        </button>
      ))}
    </div>
  );
}
