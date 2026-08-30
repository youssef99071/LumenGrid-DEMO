import './Header.css'

interface HeaderProps {
  live: boolean
  sandbox: boolean
  clock: string
}

export function Header({ live, sandbox, clock }: HeaderProps) {
  return (
    <header className="dash-header">
      <div className="brand-block">
        <img src="/grid.svg" alt="" width={28} height={28} />
        <div>
          <h1 className="logo">LumenGrid</h1>
          <p className="tag">5G traffic sensing · Tunis</p>
        </div>
      </div>
      <div className="header-meta">
        <div className={`live-pill ${live ? 'on' : 'off'}`}>
          <span className="live-dot" />
          {live ? 'Live' : 'Offline'}
          {sandbox ? ' · NaC sandbox' : ''}
        </div>
        <time className="clock" dateTime={clock}>
          {clock}
        </time>
      </div>
    </header>
  )
}
