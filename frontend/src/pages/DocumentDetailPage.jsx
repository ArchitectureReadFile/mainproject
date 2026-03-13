import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation  } from "react-router-dom";
import { fetchDocumentDetail, downloadSummaryPdf  } from "../lib/api";
import { useAuth } from "../features/auth/context/AuthContext";
import { toast } from "sonner";
import "../styles/DetailPage.css";
import Card from "../components/ui/Card";
import axiosInstance from "../lib/axios";
import ConfirmModal from "../components/ui/ConfirmModal.jsx";


export default function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const location = useLocation();
  const { user } = useAuth();
  const [showDeleteModal, setShowDeleteModal] = useState(false)


  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchDocumentDetail(id);
        setDoc(data);
      } catch {
        setError("문서를 불러오지 못했습니다.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="detail-page">
        <div className="detail-loading">불러오는 중...</div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="detail-page">
        <div className="detail-error">{error || "문서를 찾을 수 없습니다."}</div>
      </div>
    );
  }

  const s = doc;

  const isAdmin = user?.role === "ADMIN";
  const isOwner = user?.username === doc?.uploader;
  const canDelete = isAdmin || isOwner;


  const handleDownload = async () => {
    if (!s.summary_id) return;
    try {
      await downloadSummaryPdf(s.summary_id, s.case_number, s.summary_title);
    } catch {
      toast.error("다운로드에 실패했습니다.");
    }
  };
  
  const handleDeleteConfirm = async () => {
    try {
      await axiosInstance.delete(`/documents/${id}`);
      const from = location.state?.from;
      navigate(from ? `/documents?${from}` : "/documents", {
        state: { deleted: true }
      });
    } catch {
      toast.error("삭제에 실패했습니다.");
      setShowDeleteModal(false);
    }
  };

  return (
    <div className="detail-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      {/* 뒤로가기 */}
      <button className="detail-back-btn" onClick={() => navigate(-1)}>
        ← 판례 목록으로
      </button>
        <div style={{ display: "flex", gap: 8 }}>
        {doc.summary_id && (
          <button className="detail-download-btn" onClick={handleDownload}>
            PDF 다운로드
          </button>
        )}
        {canDelete && (
          <button
            className="detail-download-btn"
            onClick={() => setShowDeleteModal(true)}
            style={{ background: "#ef4444", color: "#fff", border: "none" }}
          >
            삭제
          </button>
        )}    
      </div>  
    </div>

      {/* 삭제 확인 모달 */}
      <ConfirmModal
        open={showDeleteModal}
        message={"정말 삭제하시겠습니까?\n삭제된 문서는 복구할 수 없습니다."}
        confirmLabel="삭제"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteModal(false)}
      />

      
      {/* 헤더 카드 */}
      <div style={{padding: "11px"}}>

        <h1 className="detail-title">
          {s.case_name || s.summary_title || "제목 없음"}
        </h1>

        <div className="detail-meta-row">
          <div className="detail-meta-item">
            <span className="detail-meta-label">법원</span>
            <span className="detail-meta-value">{s.court_name || "-"}</span>
          </div>
          <div className="detail-meta-divider" />
          <div className="detail-meta-item">
            <span className="detail-meta-label">사건번호</span>
            <span className="detail-meta-value">{s.case_number || "-"}</span>
          </div>
          <div className="detail-meta-divider" />
          <div className="detail-meta-item">
            <span className="detail-meta-label">판결일</span>
            <span className="detail-meta-value">{s.judgment_date || "-"}</span>
          </div>
        </div>
      </div>

      <Card className="detail-card">
        <h3>AI 요약</h3>
        <p className="detail-section-text">{s.summary_main}</p>
      </Card>

      <Card className="detail-card">
        <h3>당사자</h3>
        <div className="detail-parties-grid">
          <div className="detail-party-item">
            <p className="detail-section-label">원고</p>
            <p className="detail-party-text">{s.plaintiff}</p>
          </div>

          <div className="detail-party-item">
            <p className="detail-section-label">피고</p>
            <p className="detail-party-text">{s.defendant}</p>
          </div>
        </div>
      </Card>

      <Card className="detail-card">
        <h3>사실 관계</h3>
        <p className="detail-section-text">{s.facts}</p>
      </Card>

      <Card className="detail-card">
        <h3>판결 주문</h3>
        <p className="detail-section-text">{s.judgment_order}</p>
      </Card>

      <Card className="detail-card">
        <h3>판단 근거</h3>
        <p className="detail-section-text">{s.judgment_reason}</p>
      </Card>

      <Card className="detail-card">
          <h3>관련 법령</h3>
          <p className="detail-section-text">{s.related_laws}</p>
      </Card>        

    </div>
  );
}
