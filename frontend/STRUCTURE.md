# Frontend 구조 리팩토링 현황

## 파일 분류 기준

| 구분 | 설명 |
|---|---|
| **실제 파일 (source of truth)** | `src/shared/` 하위에 위치. 실제 구현 코드 |
| **브릿지 shim** | 기존 경로(`src/lib/`, `src/hooks/`, `src/api/`, `src/components/ui/`)에 위치. re-export만 함 |

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

## 브릿지 shim 위치 (기존 경로 호환용)

> vite alias + re-export shim 이중으로 구버전 import를 보장.
> 향후 팀 전체 import 경로 정리 후 제거 예정.

### `src/components/ui/` — 15개 (전부 shim)
`Button.jsx`, `Dialog.jsx`, `Input.jsx`, `Sheet.jsx`, `alert-dialog.jsx`,
`avatar.jsx`, `badge.jsx`, `card.jsx`, `confirm-modal.jsx`, `label.jsx`,
`select.jsx`, `separator.jsx`, `tabs.jsx`, `textarea.jsx`, `tooltip.jsx`

### `src/lib/` — 3개 (전부 shim)
`utils.js`, `datetime.js`, `errors.js`

### `src/api/` — 4개 (전부 shim)
`client.js`, `admin.js`, `groups.js`, `exports.js`

### `src/hooks/` — 1개 (전부 shim)
`useTheme.js`

---

## shim 제거 기준 (향후)
- `features/`, `pages/` 내 모든 import가 `@/shared/...` 또는 `@/features/...` 경로로 전환 완료된 시점
- vite alias의 backward-compat 항목 제거와 동시에 shim 삭제
