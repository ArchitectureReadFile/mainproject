import { Card } from "../../../components/ui/Card.jsx";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../auth/context/AuthContext.jsx";

export default function DocumentCard({ item, onClick, viewType, onDelete }) {
  const { user } = useAuth();
  const [hovered, setHovered] = useState(false);

  const isAdmin = user?.role === "ADMIN";
  const isOwner = user?.username == item.uploader;
  const canDelete = isOwner || isAdmin;

  return (
    <div style={{ position: "relative" }} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      {canDelete && hovered && (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(item.id);
        }}
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "#ef4444",
          padding: 4,
          zIndex: 1,
        }}
      >
        <Trash2 size={18} />
      </button>
    )}
    <Card onClick={onClick}>
      <div style={{ padding: "20px 24px" }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
          {item.title}
        </h3>

        <div style={{ fontSize: 13, display: "flex", gap: 16, color: "#64748b", marginBottom: 10 }}>
          <span>법원: {item.court_name || "-"}</span>
          <span>판결일: {item.judgment_date || "-"}</span>
          {viewType === "all" && (
            <span>업로드: {item.uploader || "-"}</span>
          )}
        </div>

        {item.preview && (
          <p style={{
            fontSize: 13,
            color: "#475569",
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
          }}>
            {item.preview}
          </p>
        )}
      </div>
    </Card>
    </div>
  );
}
