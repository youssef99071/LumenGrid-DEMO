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
        <div>
          <h1 className="logo">LumenGrid</h1>
          <p className="tag">AI traffic detection · No cameras, just 5G</p>
        </div>
      </div>
      <div className="header-meta">
        <div className={`live-pill ${live ? 'on' : 'off'}`}>
          <span className="live-dot" />
          {live ? 'Live' : 'Offline'}
          {sandbox ? ' · Demo mode' : ''}
        </div>
        <time className="clock" dateTime={clock}>
          {clock}
        </time>
      </div>
    </header>
  )
}

