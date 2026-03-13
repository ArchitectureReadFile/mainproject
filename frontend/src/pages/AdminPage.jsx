import { BarChart3, CheckCircle, FileText, Search, Settings, Shield, Trash2, Users, XCircle } from "lucide-react";
import { useState } from "react";
import Button from "../components/ui/Button.jsx";
import { Card } from "../components/ui/Card.jsx";
import { useAuth } from "../features/auth/index.js";
import styles from "../styles/AdminPage.module.css";

/* ── 탭 정의 ── */
const TABS = [
  { key: "dashboard", label: "대시보드",   Icon: BarChart3 },
  { key: "users",     label: "사용자 관리", Icon: Users },
  { key: "cases",     label: "판례 관리",   Icon: FileText },
  { key: "settings",  label: "시스템 설정", Icon: Settings },
];

/* ── 공통 서브컴포넌트 ── */
function SectionHeader({ title, sub }) {
  return (
    <>
      <h3 className={styles.sectionTitle}>{title}</h3>
      {sub && <p className={styles.sectionSub}>{sub}</p>}
    </>
  );
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className={styles.searchWrap}>
      <Search size={14} className={styles.searchIcon} />
      <input
        className={styles.searchInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function Badge({ variant, children }) {
  return <span className={`${styles.badge} ${styles[`badge--${variant}`]}`}>{children}</span>;
}

function EmptyRow({ colSpan }) {
  return <tr><td colSpan={colSpan} className={styles.empty}>데이터가 없습니다.</td></tr>;
}

/* ── 대시보드 ── */
const STAT_CARDS = [
  { label: "총 사용자",   sub: "활성 사용자" },
  { label: "총 판례",     sub: "전체 판례 데이터" },
  { label: "오늘 업로드", sub: "신규 판례 업로드" },
  { label: "활성 사용자", sub: "전체 대비 비율" },
];

function DashboardTab() {
  return (
    <div>
      <div className={styles.statGrid}>
        {STAT_CARDS.map(({ label, sub }) => (
          <Card key={label} className={styles.statCard}>
            <p className={styles.statLabel}>{label}</p>
            <p className={styles.statValue}>—</p>
            <p className={styles.statSub}>{sub}</p>
          </Card>
        ))}
      </div>
      <Card className={styles.section}>
        <SectionHeader title="최근 활동" />
        {/* TODO: GET /api/admin/activity */}
        <p className={styles.empty}>API 연동 후 표시됩니다.</p>
      </Card>
    </div>
  );
}

/* ── 사용자 관리 ── */
function UsersTab() {
  const [search, setSearch] = useState("");
  // TODO: GET /api/admin/users → setUsers(data)
  const users = [];

  const filtered = users.filter(
    ({ name, email }) =>
      name.toLowerCase().includes(search.toLowerCase()) ||
      email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Card className={styles.section}>
      <SectionHeader title="사용자 관리" sub="등록된 모든 사용자를 관리합니다" />
      <SearchInput value={search} onChange={setSearch} placeholder="이름 또는 이메일로 검색..." />
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>사용자</th><th>역할</th><th>상태</th>
              <th>가입일</th><th>업로드 수</th><th>작업</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? <EmptyRow colSpan={6} /> : filtered.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className={styles.userCell}>
                    <span className={styles.avatar}>{u.name[0]}</span>
                    <div>
                      <p className={styles.userName}>{u.name}</p>
                      <p className={styles.userEmail}>{u.email}</p>
                    </div>
                  </div>
                </td>
                <td><Badge variant={u.role === "ADMIN" ? "admin" : "user"}>{u.role === "ADMIN" ? "관리자" : "일반"}</Badge></td>
                <td><Badge variant={u.status === "active" ? "active" : "inactive"}>{u.status === "active" ? "활성" : "비활성"}</Badge></td>
                <td>{u.joinDate}</td>
                <td>{u.uploadCount}건</td>
                <td>
                  <div className={styles.actions}>
                    {/* TODO: PATCH /api/admin/users/:id/status */}
                    <Button variant="outline" className={styles.actionBtn}>
                      {u.status === "active" ? "비활성화" : "활성화"}
                    </Button>
                    {/* TODO: DELETE /api/admin/users/:id */}
                    <Button variant="danger" className={styles.actionBtn}><Trash2 size={14} /></Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ── 판례 관리 ── */
const CASE_STATUS_META = {
  approved: { label: "승인됨", variant: "active" },
  pending:  { label: "대기중", variant: "user" },
  rejected: { label: "거부됨", variant: "danger" },
};

function CasesTab() {
  const [search, setSearch] = useState("");
  // TODO: GET /api/admin/cases → setCases(data)
  const cases = [];

  const filtered = cases.filter(({ title }) =>
    title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Card className={styles.section}>
      <SectionHeader title="판례 관리" sub="업로드된 모든 판례를 관리합니다" />
      <SearchInput value={search} onChange={setSearch} placeholder="판례 제목으로 검색..." />
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>제목</th><th>업로더</th><th>업로드일</th>
              <th>상태</th><th>조회수</th><th>작업</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? <EmptyRow colSpan={6} /> : filtered.map((c) => {
              const meta = CASE_STATUS_META[c.status] ?? { label: c.status, variant: "user" };
              return (
                <tr key={c.id}>
                  <td className={styles.caseTitle}>{c.title}</td>
                  <td>{c.uploader}</td>
                  <td>{c.uploadDate}</td>
                  <td><Badge variant={meta.variant}>{meta.label}</Badge></td>
                  <td>{c.views}회</td>
                  <td>
                    <div className={styles.actions}>
                      {c.status === "pending" && (
                        <>
                          {/* TODO: PATCH /api/admin/cases/:id/approve */}
                          <Button variant="outline" className={styles.actionBtn}><CheckCircle size={14} /></Button>
                          {/* TODO: PATCH /api/admin/cases/:id/reject */}
                          <Button variant="outline" className={styles.actionBtn}><XCircle size={14} /></Button>
                        </>
                      )}
                      {/* TODO: DELETE /api/admin/cases/:id */}
                      <Button variant="danger" className={styles.actionBtn}><Trash2 size={14} /></Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ── 시스템 설정 ── */
const SETTINGS_GROUPS = [
  { title: "AI 설정",     items: ["Ollama 모델 설정", "ChromaDB 연결 설정", "요약 파라미터 조정"] },
  { title: "데이터베이스", items: ["MariaDB 연결 상태", "데이터 백업", "데이터 정리"] },
  { title: "시스템",       items: ["로그 확인", "캐시 관리"], danger: ["시스템 초기화"] },
];

function SettingsTab() {
  return (
    <div className={styles.settingsGrid}>
      {SETTINGS_GROUPS.map(({ title, items, danger }) => (
        <Card key={title} className={styles.section}>
          <SectionHeader title={title} />
          <div className={styles.settingsBtns}>
            {items.map((label) => (
              <Button key={label} variant="outline" className={styles.settingsBtn}>{label}</Button>
            ))}
            {danger?.map((label) => (
              <Button key={label} variant="danger" className={styles.settingsBtn}>{label}</Button>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── 메인 ── */
const TAB_CONTENT = { dashboard: DashboardTab, users: UsersTab, cases: CasesTab, settings: SettingsTab };

export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("dashboard");

  if (user?.role !== "ADMIN") {
    return (
      <div className={styles.forbidden}>
        <Shield size={48} className={styles.forbiddenIcon} />
        <p>접근 권한이 없습니다.</p>
      </div>
    );
  }

  const TabContent = TAB_CONTENT[tab];

  return (
    <div className={styles.page}>
      <div className={styles.titleRow}>
        <Shield size={28} className={styles.titleIcon} />
        <div>
          <h1 className={styles.title}>관리자 페이지</h1>
          <p className={styles.sub}>시스템 전체를 관리하고 모니터링합니다</p>
        </div>
      </div>

      <div className={styles.tabBar}>
        {TABS.map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            className={`${styles.tabBtn} ${tab === key ? styles.tabBtnActive : ""}`}
            onClick={() => setTab(key)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      <TabContent />
    </div>
  );
}
