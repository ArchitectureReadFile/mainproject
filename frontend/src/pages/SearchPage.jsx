import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import DocumentCard from "../features/upload/components/DocumentCard.jsx";
import Button from "../components/ui/Button.jsx";
import Card from "../components/ui/Card.jsx";
import ConfirmModal from "../components/ui/ConfirmModal.jsx";
import axiosInstance from "../lib/axios.js";
import { toast } from "sonner";

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get("page") || "1");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const searchKeyword = searchParams.get("keyword") || "";
  const viewType = searchParams.get("view_type") || "my";
  const category = searchParams.get("category") || "전체";
  const [keyword, setKeyword] = useState(searchKeyword);
  const [deleteTargetId, setDeleteTargetId] = useState(null);
  const [loadError, setLoadError] = useState("");
  const location = useLocation();

  const limit = 5;

  const loadData = useCallback(async () => {
    try {
      setLoadError("");
      const skip = (page - 1) * limit;
      const params = new URLSearchParams({ skip, limit, keyword: searchKeyword, view_type: viewType, category });
      const { data } = await axiosInstance.get(`/documents?${params}`);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setItems([]);
      setTotal(0);
      setLoadError("판례 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.");
      toast.error("판례 목록을 불러오지 못했습니다.");
    }
  }, [page, searchKeyword, viewType, category]);

  useEffect(() => {
    loadData();
  }, [loadData, page, searchKeyword, viewType, category]);

  const handleSearch = () => {
    setSearchParams({ page: 1, keyword, view_type: viewType, category });
  };

  const setPage = (p) => setSearchParams({ page: p, keyword: searchKeyword, view_type: viewType, category });

  const totalPages = Math.ceil(total / limit);

  const handleDeleteConfirm = async () => {
    try {
      await axiosInstance.delete(`/documents/${deleteTargetId}`)
      setDeleteTargetId(null);
      await loadData();
      toast.success("판례가 삭제되었습니다.")
    } catch {
      toast.error("삭제에 실패했습니다.");
    }
  };


  useEffect(() => {
    if (location.state?.deleted) {
      toast.success("판례가 삭제되었습니다.");
      navigate(".", { replace: true, state: {} });
    }
  }, [location.state?.deleted, navigate]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px" }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 32, fontWeight: "bold", marginBottom: 8 }}>판례 목록</h1>
        <p style={{ color: "#64748b" }}>업로드된 판례를 검색하고 확인할 수 있습니다. 총 {total}건의 판례가 있습니다.</p>
      </div>

      {/* 검색 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="판례 제목, 내용으로 검색"
          style={{
            flex: 1,
            padding: "8px 12px",
            border: "1px solid #dbdee2",
            backgroundColor: "#eef0f3",
            borderRadius: 8,
            fontSize: 14,
          }}
        />
        <Button onClick={handleSearch}>검색</Button>
      </div>


      {/* 보기 필터 */}
      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 15, color: "#64748b", alignSelf: "center", fontWeight: "bold", display: "block", marginBottom: 5 }}>보기</span>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { value: "my", label: "내 업로드" },
            { value: "all", label: "전체 판례" },
          ].map((v) => (
            <Button
              key={v.value}
              variant={viewType === v.value ? "primary" : "outline"}
              onClick={() => setSearchParams({ page: 1, keyword: searchKeyword, view_type: v.value, category })}
            >
              {v.label}
            </Button>
          ))}
        </div>
      </div>

      {/* 카테고리 필터 */}
      <div style={{ marginBottom: 24 }}>
        <span style={{ fontSize: 15, color: "#64748b", alignSelf: "center", fontWeight: "bold", display: "block", marginBottom: 5 }}>카테고리</span>
        <div style={{ display: "flex", gap: 8 }}>
          {["전체", "민사", "형사", "노동", "행정", "가사"].map((c) => (
            <Button
              key={c}
              variant={category === c ? "primary" : "outline"}
              onClick={() => setSearchParams({ page: 1, keyword: searchKeyword, view_type: viewType, category: c })}
            >
              {c}
            </Button>
          ))}
        </div>
      </div>


      {/* 목록 */}
      {loadError ? (
        <Card>
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#ef4444" }}>
            {loadError}
          </div>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#94a3b8" }}>
            판례가 없습니다.
          </div>
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((item) => (
            <DocumentCard
              key={item.id}
              item={item}
              onClick={() => navigate(`/documents/${item.id}`, { state: { from: searchParams.toString() } })}
              viewType={viewType}
              onDelete={(id) => setDeleteTargetId(id)}
            />
          ))}
        </div>
      )}

      {/* 확인 모달 */}
      <ConfirmModal
        open={Boolean(deleteTargetId)}
        message={"정말 삭제하시겠습니까?\n삭제된 문서는 복구할 수 없습니다."}
        confirmLabel="삭제"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTargetId(null)}
      />

      {/* 페이지네이션 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 3, marginTop: 24 }}>
        <Button variant="outline" disabled={page === 1} onClick={() => setPage(1)}>«</Button>
        <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>‹</Button>
        <div style={{ display: "flex", gap: "2px" }}>
          {Array.from({ length: totalPages || 1 }, (_, i) => i + 1)
            .filter((p) => p >= Math.max(1, page - 2) && p <= Math.min(totalPages, page + 2))
            .map((p) => (
              <Button
                key={p}
                variant={p === page ? "primary" : "outline"}
                onClick={() => setPage(p)}
              >
                {p}
              </Button>
            ))}
        </div>
        <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>›</Button>
        <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage(totalPages)}>»</Button>
      </div>
    </div>
  );
}
