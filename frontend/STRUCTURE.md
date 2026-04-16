# Frontend 구조

## 파일 분류 기준

| 구분 | 설명 |
|---|---|
| **실제 파일 (source of truth)** | `src/shared/` 하위에 위치. 실제 구현 코드 |
| **기능 코드** | `src/features/`, `src/pages/`, `src/app/` 하위에 위치. 화면/도메인별 기능 구현 |

---

## 실제 파일 위치 (`src/shared/`)

### `src/shared/ui/` — UI 컴포넌트 15개
| 파일 | 비고 |
|---|---|
| `Button.jsx` | |
| `Dialog.jsx` | |
| `Input.jsx` | |
| `Sheet.jsx` | |
| `alert-dialog.jsx` | |
| `avatar.jsx` | |
| `badge.jsx` | |
| `card.jsx` | |
| `confirm-modal.jsx` | `alert-dialog` 조합 |
| `label.jsx` | |
| `select.jsx` | |
| `separator.jsx` | |
| `tabs.jsx` | |
| `textarea.jsx` | |
| `tooltip.jsx` | |

### `src/shared/lib/`
| 파일 | 내용 |
|---|---|
| `utils.js` | `cn()` (clsx + tailwind-merge) |
| `datetime.js` | 한국시간 포맷 유틸 |
| `errors.js` | `ERROR_CODE` 상수 및 에러 헬퍼 |

### `src/shared/api/`
| 파일 | 내용 |
|---|---|
| `client.js` | axios 인스턴스 + interceptor |
| `admin.js` | 관리자 API |
| `groups.js` | 그룹/워크스페이스/문서 API |
| `exports.js` | export job API |

### `src/shared/hooks/`
| 파일 | 내용 |
|---|---|
| `useTheme.js` | 다크모드 토글 |

### `src/shared/assets/`
| 파일 | 내용 |
|---|---|
| `nongdamgom.png` | 챗봇 위젯 버튼 이미지 |

---

## 현재 구조 메모

- 구버전 `src/lib/`, `src/hooks/`, `src/api/`, `src/components/ui/` shim 계층은 현재 저장소에 남아 있지 않다.
- 공용 코드는 `src/shared/...`, 기능 코드는 `src/features/...`, 라우트 단위 화면은 `src/pages/...`를 source of truth로 사용한다.
