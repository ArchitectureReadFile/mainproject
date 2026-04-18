import {
  IoDocumentTextOutline,
  IoFolderOpenOutline,
  IoScaleOutline,
  IoLinkOutline,
} from 'react-icons/io5';

const TYPE_META = {
  platform: {
    icon: IoScaleOutline,
    label: '플랫폼',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  },
  workspace: {
    icon: IoFolderOpenOutline,
    label: '그룹',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  },
  session: {
    icon: IoDocumentTextOutline,
    label: '첨부',
    badge: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
  },
};

function buildMetaLine(reference) {
  const parts = [];
  if (reference.case_number) parts.push(reference.case_number);
  if (reference.file_name) parts.push(reference.file_name);
  if (typeof reference.chunk_order === 'number') parts.push(`청크 ${reference.chunk_order + 1}`);
  if (reference.chunk_id) parts.push(reference.chunk_id);
  return parts.join(' · ');
}

export default function MessageReferences({ references }) {
  if (!Array.isArray(references) || references.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2 border-t border-slate-200/70 pt-3 dark:border-slate-700/80">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
        참고 근거
      </p>
      <div className="space-y-2">
        {references.map((reference, index) => {
          const typeMeta = TYPE_META[reference.knowledge_type] || TYPE_META.session;
          const Icon = typeMeta.icon;
          const metaLine = buildMetaLine(reference);

          return (
            <div
              key={`${reference.chunk_id || reference.title}-${index}`}
              className="rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/60"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${typeMeta.badge}`}
                    >
                      <Icon size={12} />
                      {typeMeta.label}
                    </span>
                    {reference.source_type && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        {reference.source_type}
                      </span>
                    )}
                  </div>
                  <p className="break-words text-xs font-semibold text-slate-700 dark:text-slate-200">
                    {reference.title}
                  </p>
                  {metaLine && (
                    <p className="break-all text-[11px] text-slate-500 dark:text-slate-400">
                      {metaLine}
                    </p>
                  )}
                </div>
                {reference.source_url && (
                  <a
                    href={reference.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    <IoLinkOutline size={13} />
                    원문
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
