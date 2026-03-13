import { FolderOpen, Home, Upload } from "lucide-react";

export const MENU_ITEMS = [
  { key: "upload", to: "/upload", label: "업로드", icon: Upload, match: (path) => path.startsWith("/upload") },
  { key: "documents", to: "/documents", label: "목록보기", icon: FolderOpen, match: (path) => path.startsWith("/documents") },
  { key: "home", to: "/", label: "홈", icon: Home, match: (path) => path === "/" },
];
