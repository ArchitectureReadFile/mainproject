import { createPrecedent, reindexPrecedents, retryPrecedent } from "@/api/admin";
import { ERROR_CODE, getErrorMessageByCode } from "@/lib/errors";
import { useState } from "react";

export default function AdminRagDbSection({ precedents, onRefetch }) {
  const { summary, failed_items, pending_items, recent_items } = precedents;
  const [newUrl, setNewUrl] = useState("");
  const [actionError, setActionError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const withAction = async (fn) => {
    setActionError(null);
    setActionLoading(true);
    try {
      await fn();
      onRefetch();
    } catch (e) {
      // 409 중복 / 422 도메인·URL 오류는 메시지로 표시
      const knownCodes = [
        ERROR_CODE.PRECEDENT_DUPLICATE_URL,
        ERROR_CODE.PRECEDENT_INVALID_URL,
        ERROR_CODE.PRECEDENT_DOMAIN_NOT_ALLOWED,
        ERROR_CODE.PRECEDENT_NOT_FOUND,
      ];
      if (knownCodes.includes(e.code)) {
        setActionError(getErrorMessageByCode(e.code));
      } else {
        setActionError(e.message ?? "요청에 실패했습니다.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddUrl = () => {
    if (!newUrl.trim()) return;
    withAction(async () => {
      await createPrecedent(newUrl.trim());
      setNewUrl("");
    });
  };

  const handleReindex = () => withAction(reindexPrecedents);
  const handleRetry = (id) => withAction(() => retryPrecedent(id));

  return (
    <div className="space-y-6">
      {/* 액션 바 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={newUrl}
          onChange={(e) => setNewUrl(e.target.value)}
          placeholder="판례 URL 입력 (예: https://www.law.go.kr/...)"
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          disabled={actionLoading}
        />
        <button
          onClick={handleAddUrl}
          disabled={actionLoading}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          URL 추가
        </button>
        <button
          onClick={handleReindex}
          disabled={actionLoading}
          className="px-4 py-2 bg-gray-700 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-50"
        >
          인덱스 재생성
        </button>
      </div>

      {/* 액션 에러 메시지 */}
      {actionError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          <p className="text-sm text-red-600">{actionError}</p>
        </div>
      )}

      {/* 요약 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <SummaryCard label="전체" value={summary.total.toLocaleString()} />
        <SummaryCard label="인덱싱 완료" value={summary.indexed.toLocaleString()} />
        <SummaryCard label="대기/처리 중" value={summary.pending.toLocaleString()} color="yellow" />
        <SummaryCard label="실패" value={summary.failed.toLocaleString()} color="red" />
      </div>

      {/* 패널 3개 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel title="실패 항목">
          {failed_items.length === 0 && <EmptyRow />}
          {failed_items.map((item) => (
            <div key={item.id} className="flex justify-between items-start py-2 border-b text-sm gap-2">
              <div className="min-w-0">
                <p className="text-gray-700 truncate" title={item.title ?? item.source_url}>
                  {item.title ?? item.source_url}
                </p>
                <p className="text-xs text-red-400">{item.error_message}</p>
                <p className="text-xs text-gray-400">{item.updated_at?.slice(0, 10)}</p>
              </div>
              <button
                onClick={() => handleRetry(item.id)}
                disabled={actionLoading}
                className="shrink-0 text-xs text-blue-600 hover:underline disabled:opacity-50"
              >
                재처리
              </button>
            </div>
          ))}
        </Panel>

        <Panel title="대기 / 처리 중">
          {pending_items.length === 0 && <EmptyRow />}
          {pending_items.map((item) => (
            <div key={item.id} className="py-2 border-b text-sm">
              <p className="text-gray-700 truncate" title={item.title ?? item.source_url}>
                {item.title ?? item.source_url}
              </p>
              <p className="text-xs text-gray-400">{item.created_at?.slice(0, 10)}</p>
            </div>
          ))}
        </Panel>

        <Panel title="최근 등록">
          {recent_items.length === 0 && <EmptyRow />}
          {recent_items.map((item) => (
            <div key={item.id} className="py-2 border-b text-sm">
              <p className="text-gray-700 truncate" title={item.title ?? item.source_url}>
                {item.title ?? item.source_url}
              </p>
              <p className="text-xs text-gray-400">{item.updated_at?.slice(0, 10)}</p>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, color }) {
  const colorMap = { red: "text-red-500", yellow: "text-yellow-500" };
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colorMap[color] ?? "text-gray-800"}`}>{value}</p>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <p className="text-sm font-semibold text-gray-700 mb-3">{title}</p>
      {children}
    </div>
  );
}

function EmptyRow() {
  return <p className="text-xs text-gray-400 py-2">항목 없음</p>;
}
