import client from '@/api/client'
import Button from '@/components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import { Calendar, LogOut, Mail } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { meApi } from '../../features/auth/api/authApi'

const FILES_PER_PAGE = 5

export default function MypagePage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [username, setUsername] = useState('')
  const [inputWidth, setInputWidth] = useState(0)
  const inputRef = useRef(null)
  const nameRef = useRef(null)
  const spanRef = useRef(null)

  const fetchUser = useCallback(async () => {
    try {
      const data = await meApi()
      setUser(data)
      setUsername(data.username)
    } catch (e) {
      toast.error(e.message || '사용자 정보를 불러오지 못했습니다.')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }, [navigate])

  const fetchMyFiles = async () => {
    try {
      const PAGE_SIZE = 50
      let skip = 0
      let allItems = []
      let total = Infinity
      while (allItems.length < total) {
        const res = await client.get('/documents/', { params: { skip, limit: PAGE_SIZE, view_type: 'my' } })
        const { items, total: t } = res.data
        total = t
        allItems = [...allItems, ...(items || [])]
        if (items.length < PAGE_SIZE) break
        skip += PAGE_SIZE
      }
      setUploadedFiles(allItems)
    } catch {
      toast.error('파일 목록을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUser(); fetchMyFiles() }, [fetchUser])

  useEffect(() => {
    if (nameRef.current) setInputWidth(nameRef.current.offsetWidth)
  }, [username, editing, user])

  useEffect(() => {
    if (spanRef.current) setInputWidth(spanRef.current.offsetWidth)
  }, [username])

  const handleUpdateUsername = async () => {
    try {
      const res = await client.patch('/auth/username', { username })
      setUser((prev) => ({ ...prev, username: res.data.username }))
      setEditing(false)
      toast.success('이름이 변경되었습니다.')
    } catch {
      toast.error('이름 변경 실패')
    }
  }

  const handleDeleteAccount = async () => {
    if (!window.confirm('정말로 회원탈퇴를 하시겠습니까?')) return
    try {
      await client.delete('/auth/delete')
      toast.success('회원탈퇴가 완료되었습니다.')
      localStorage.clear()
      navigate('/')
      window.location.reload()
    } catch {
      toast.error('회원탈퇴 실패')
    }
  }

  const startIndex = (page - 1) * FILES_PER_PAGE
  const paginatedFiles = uploadedFiles.slice(startIndex, startIndex + FILES_PER_PAGE)
  const totalPages = Math.ceil(uploadedFiles.length / FILES_PER_PAGE)

  if (loading || !user) return <div className="p-8 text-center text-muted-foreground">Loading...</div>

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">프로필</h1>
        <p className="text-muted-foreground text-sm mt-1">계정 정보를 확인하고 관리하세요</p>
      </div>

      {/* 기본 정보 */}
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          <div>
            {editing ? (
              <div className="flex items-center gap-2">
                <span ref={spanRef} className="invisible absolute">{username || '이름'}</span>
                <Input
                  ref={inputRef}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="text-lg font-semibold"
                  style={{ width: inputWidth + 'px', minWidth: '80px' }}
                />
                <Button size="sm" onClick={handleUpdateUsername}>저장</Button>
                <Button size="sm" variant="outline" onClick={() => { setUsername(user.username); setEditing(false) }}>취소</Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 ref={nameRef} className="text-xl font-semibold">{user.username}</h2>
                <Button size="sm" variant="outline" onClick={() => { setEditing(true); setTimeout(() => inputRef.current?.focus(), 0) }}>
                  이름 수정
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Mail className="w-4 h-4" />
              <div>
                <p className="text-xs text-muted-foreground">이메일</p>
                <p className="text-foreground">{user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Calendar className="w-4 h-4" />
              <div>
                <p className="text-xs text-muted-foreground">가입일</p>
                <p className="text-foreground">{new Date(user.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 업로드 파일 */}
      <Card>
        <CardHeader>
          <CardTitle>업로드 파일</CardTitle>
          <CardDescription>업로드한 판례 파일 목록</CardDescription>
        </CardHeader>
        <CardContent>
          {paginatedFiles.length === 0 ? (
            <p className="text-sm text-muted-foreground">업로드된 파일이 없습니다.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {paginatedFiles.map((file) => (
                <li key={file.id} className="flex justify-between items-center text-sm py-2 border-b last:border-0">
                  {file.summary_id ? (
                    <a
                      href={'/api/summaries/' + file.summary_id + '/download'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >{file.title}</a>
                  ) : (
                    <span className="text-foreground">{file.title}</span>
                  )}
                  <span className="text-muted-foreground text-xs">{new Date(file.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          )}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-4">
              <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>이전</Button>
              <span className="text-sm text-muted-foreground">{page} / {totalPages}</span>
              <Button size="sm" variant="outline" disabled={page === totalPages} onClick={() => setPage(page + 1)}>다음</Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 계정 설정 */}
      <Card>
        <CardHeader>
          <CardTitle>계정 설정</CardTitle>
          <CardDescription>계정 및 보안 관리</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" className="w-full gap-2" onClick={handleDeleteAccount}>
            <LogOut className="w-4 h-4" />
            회원탈퇴
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}