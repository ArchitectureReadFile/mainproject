import styles from '../../styles/Footer.module.css'

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.row}>
          <p className={styles.brand}>판례 AI 플랫폼</p>
          <p className={styles.desc}>챗봇 · 워크스페이스 · 문서 요약</p>
        </div>
        <p className={styles.copy}>© 2026 참고용 도구입니다. 법률 자문을 대체하지 않습니다.</p>
      </div>
    </footer>
  )
}