import {
  FolderOpen,
  Scale,
  Search,
  Shield,
  Sparkles,
  Upload,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/index.js";
import styles from "../styles/MainPage.module.css";

export default function MainPage() {
  const { isAuthenticated, openAuthModal } = useAuth();
  const navigate = useNavigate();

  const handleUploadClick = () => {
    if (isAuthenticated) {
      navigate("/upload");
      return;
    }
    openAuthModal("login");
  };

  const handleSearchClick = () => {
    if (isAuthenticated) {
      navigate("/documents");
      return;
    }
    openAuthModal("login");
  };

  return (
    <div className={styles.container}>
      <section className={styles["hero-section"]}>
        <div className={styles["hero-icon-wrap"]}>
          <Scale className={styles["hero-icon"]} />
        </div>
        <h1 className={styles["hero-title"]}>판례 요약 시스템</h1>
        <p className={styles["hero-description"]}>
          AI 기술로 복잡한 법률 판례를 쉽게 이해하고,
          <br />
          유사 사례를 빠르게 검색할 수 있습니다
        </p>
        <div className={styles["hero-buttons"]}>
          <button type="button" className={styles["btn-primary"]} onClick={handleUploadClick}>
            <Upload className={styles["btn-icon"]} />
            판례 업로드하기
          </button>
          <button type="button" className={styles["btn-outline"]} onClick={handleSearchClick}>
            <FolderOpen className={styles["btn-icon"]} />
            판례 목록 보기
          </button>
        </div>
      </section>

      <section className={styles["feature-grid"]}>
        <div className={styles["feature-card"]}>
          <div
            className={styles["feature-icon-wrap"] + " " + styles["icon-blue"]}>
            <Upload className={styles["feature-icon"]} />
          </div>
          <h4 className={styles["feature-title"]}>간편한 업로드</h4>
          <p className={styles["feature-subtitle"]}>
            PDF 파일을 드래그 앤 드롭하여 쉽게 업로드
          </p>
          <p className={styles["feature-desc"]}>
            판례 문서를 선택하면 자동으로 텍스트를 추출하고 데이터베이스에
            저장합니다.
          </p>
        </div>

        <div className={styles["feature-card"]}>
          <div
            className={
              styles["feature-icon-wrap"] + " " + styles["icon-purple"]
            }>
            <Sparkles className={styles["feature-icon"]} />
          </div>
          <h4 className={styles["feature-title"]}>AI 자동 요약</h4>
          <p className={styles["feature-subtitle"]}>
            Ollama가 핵심 내용을 자동으로 추출
          </p>
          <p className={styles["feature-desc"]}>
            복잡한 법률 용어와 긴 판례 문서를 AI가 이해하기 쉽게 요약해드립니다.
          </p>
        </div>

        <div className={styles["feature-card"]}>
          <div
            className={
              styles["feature-icon-wrap"] + " " + styles["icon-green"]
            }>
            <Search className={styles["feature-icon"]} />
          </div>
          <h4 className={styles["feature-title"]}>빠른 검색</h4>
          <p className={styles["feature-subtitle"]}>
            유사 판례를 즉시 찾아보세요
          </p>
          <p className={styles["feature-desc"]}>
            키워드와 카테고리로 필요한 판례를 빠르게 검색하고 비교할 수
            있습니다.
          </p>
        </div>
      </section>

      <section className={styles["how-section"]}>
        <h2 className={styles["how-title"]}>어떻게 작동하나요?</h2>
        <div className={styles["how-grid"]}>
          {[
            {
              step: 1,
              title: "PDF 업로드",
              desc: "판례 문서를 시스템에 업로드합니다",
            },
            {
              step: 2,
              title: "텍스트 추출",
              desc: "PDF에서 텍스트를 자동으로 추출합니다",
            },
            {
              step: 3,
              title: "AI 요약",
              desc: "Ollama가 핵심 내용을 요약합니다",
            },
            {
              step: 4,
              title: "검색 가능",
              desc: "언제든 검색하여 확인할 수 있습니다",
            },
          ].map(({ step, title, desc }) => (
            <div key={step} className={styles["how-item"]}>
              <div className={styles["how-step"]}>{step}</div>
              <h3 className={styles["how-item-title"]}>{title}</h3>
              <p className={styles["how-item-desc"]}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles["notice-section"]}>
        <h3 className={styles["notice-title"]}>
          <Shield className={styles["notice-icon"]} />
          법률 자문 안내
        </h3>
        <p className={styles["notice-desc"]}>
          본 시스템은 판례 정보를 제공하는 참고 도구입니다. 실제 법률 문제에
          대해서는 반드시 변호사 등 전문가와 상담하시기 바랍니다. 판례는 개별
          사건의 특수성에 따라 다르게 적용될 수 있으며, 본 시스템의 정보는 법률
          자문을 대체할 수 없습니다.
        </p>
      </section>
    </div>
  );
}
