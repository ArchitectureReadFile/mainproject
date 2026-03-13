// src/components/menu/profile/PersonalProfile.jsx
import { Calendar, LogOut, Mail } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "../components/ui/Card";

import { meApi } from "../features/auth/api/authApi";
import axiosInstance from "../lib/axios";

import "../styles/ProfileCustom.css";

const FILES_PER_PAGE = 5;

export default function PersonalProfile() {
    const navigate = useNavigate();

    const [user, setUser] = useState(null);
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);

    const [editing, setEditing] = useState(false);
    const [username, setUsername] = useState("");
    const [inputWidth, setInputWidth] = useState(0);

    const inputRef = useRef(null);
    const nameRef = useRef(null);
    const spanRef = useRef(null);

    useEffect(() => {
        fetchUser();
        fetchMyFiles();
    }, [fetchUser]);

    useEffect(() => {
        if (nameRef.current) {
            const width = nameRef.current.offsetWidth;
            setInputWidth(width);
        }
    }, [username, editing, user]);

    useEffect(() => {
        if (spanRef.current) {
            const width = spanRef.current.offsetWidth;
            setInputWidth(width);
        }
    }, [username]);

    // 사용자 정보 가져오기
    const fetchUser = useCallback(async () => {
        try {
            const data = await meApi();
            setUser(data);
            setUsername(data.username);
        } catch (e) {
            console.error(e);
            toast.error(e.message || "사용자 정보를 불러오지 못했습니다.");
            navigate("/");
        } finally {
            setLoading(false);
        }
    }, [navigate]);

    //사용자명 변경
    const handleUpdateUsername = async () => {
        try {
            const res = await axiosInstance.patch("/auth/username", {
                username: username,
            });

            setUser((prev) => ({
                ...prev,
                username: res.data.username,
            }));

            setEditing(false);
            toast.success("이름이 변경되었습니다.");
        } catch (e) {
            console.error(e);
            toast.error("이름 변경 실패");
        }
    };

    // 업로드 파일 목록 가져오기 (전체 페이지 순차 fetch)
    const fetchMyFiles = async () => {
        try {
            const PAGE_SIZE = 50;
            let skip = 0;
            let allItems = [];
            let total = Infinity;

            while (allItems.length < total) {
                const res = await axiosInstance.get("/documents/", {
                    params: { skip, limit: PAGE_SIZE, view_type: 'my' },
                });
                const { items, total: t } = res.data;
                total = t;
                allItems = [...allItems, ...(items || [])];
                if (items.length < PAGE_SIZE) break;
                skip += PAGE_SIZE;
            }

            setUploadedFiles(allItems);
        } catch (e) {
            console.error(e);
            toast.error("파일 목록을 불러오지 못히습니다.");
        } finally {
            setLoading(false);
        }
    };

    // 페이지네이션 계산
    const startIndex = (page - 1) * FILES_PER_PAGE;
    const paginatedFiles = uploadedFiles.slice(
        startIndex,
        startIndex + FILES_PER_PAGE
    );
    const totalPages = Math.ceil(uploadedFiles.length / FILES_PER_PAGE);

    const handleDeleteAccount = async () => {
        if (!window.confirm("정말로 회원탈퇴를 하시겠습니까?")) return;

        try {
            await axiosInstance.delete("/auth/delete");
            toast.success("회원탈퇴가 완료되었습니다.");
            localStorage.clear();
            navigate("/");
            window.location.reload();
        } catch {
            toast.error("회원탈퇴 실패");
        }
    };

    if (loading || !user) return <div>Loading...</div>;
    if (!user) return <div>사용자 정보를 불러올 수 없습니다.</div>;

    return (
        <div className="cards">
            <div>
                <h1>프로필</h1>
                <p>계정 정보를 확인하고 관리하세요</p>
            </div>

            <div>
                {/* 기본 정보 */}
                <Card>
                    <CardContent className="card-basic-info">
                        <div>
                            <div>
                                {editing ? (
                                    <div className="username-edit">
                                        {/* 숨겨진 span: 글자 길이 계산용 */}
                                        <span className="username-sizer" ref={spanRef}>
                                            {username || "이름"}
                                        </span>
                                        <input
                                            ref={inputRef}
                                            value={username}
                                            onChange={(e) => setUsername(e.target.value)}
                                            className="username-input"
                                            style={{ width: inputWidth + "px" }}
                                        />

                                        <button
                                            className="edit-btn"
                                            onClick={handleUpdateUsername}>
                                            저장
                                        </button>

                                        <button
                                            className="edit-btn"
                                            onClick={() => {
                                                setUsername(user.username);
                                                setEditing(false);
                                            }}>
                                            취소
                                        </button>
                                    </div>
                                ) : (
                                    <div className="username-display">
                                        <h2 ref={nameRef} className="profile-name">{user.username}</h2>
                                        <button
                                            className="edit-btn"
                                            onClick={() => {
                                                setEditing(true);
                                                // input이 렌더링된 다음 focus
                                                setTimeout(() => {
                                                    if (inputRef.current) inputRef.current.focus();
                                                }, 0);
                                            }}
                                        >
                                            이름 수정
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div>
                            <div className="info-row">
                                <Mail />
                                <div>
                                    <p>이메일</p>
                                    <p>{user.email}</p>
                                </div>
                            </div>

                            <div className="info-row">
                                <Calendar />
                                <div>
                                    <p>가입일</p>
                                    <p>
                                        {new Date(user.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* 업로드 파일 목록 */}
                <Card className='Card'>
                    <CardHeader>
                        <CardTitle className="card-title">업로드 파일</CardTitle>
                        <CardDescription className="card-description">
                            업로드한 판례 파일 목록
                        </CardDescription>
                    </CardHeader>

                    <CardContent>
                        {paginatedFiles.length === 0 ? (
                            <p>업로드된 파일이 없습니다.</p>
                        ) : (
                            <ul className="upload-file-list">
                                {paginatedFiles.map((file) => (
                                    <li key={file.id} className="upload-file-item">
                                        {file.summary_id ? (
                                            <a
                                                href={`/api/summaries/${file.summary_id}/download`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                            >
                                                {file.title}
                                            </a>
                                        ) : (
                                            <span>{file.title}</span>
                                        )}
                                        <span>
                                            {new Date(file.created_at).toLocaleDateString()}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}

                        {/* 페이지네이션 */}
                        {totalPages > 1 && (
                            <div className="pagination">
                                <button
                                    className="edit-btn"
                                    disabled={page === 1}
                                    onClick={() => setPage(page - 1)}
                                >
                                    이전
                                </button>

                                <span>
                                    {page} / {totalPages}
                                </span>

                                <button
                                    className="edit-btn"
                                    disabled={page === totalPages}
                                    onClick={() => setPage(page + 1)}
                                >
                                    다음
                                </button>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* 계정 설정 */}
                <Card className='Card'>
                    <CardHeader>
                        <CardTitle className="card-title">계정 설정</CardTitle>
                        <CardDescription className="card-description">
                            계정 및 보안 관리
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="card-content-settings">
                        <button
                            className="btn-full-width btn-destructive"
                            onClick={handleDeleteAccount}
                        >
                            <LogOut className="btn-icon" />
                            회원탈퇴
                        </button>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
