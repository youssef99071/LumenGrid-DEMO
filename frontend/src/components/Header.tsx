import './Header.css'

export type AppTab = 'data' | 'learning' | 'prediction'

interface HeaderProps {
  live: boolean
  sandbox: boolean
  clock: string
  tab: AppTab
  recording?: boolean
  onTabChange: (tab: AppTab) => void
}

function TabIcon({ name }: { name: AppTab }) {
  if (name === 'data') {
    return (
      <svg className="tab-icon" viewBox="0 0 16 16" aria-hidden="true">
        <ellipse cx="8" cy="4" rx="5.2" ry="2.1" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path
          d="M2.8 4v8c0 1.16 2.33 2.1 5.2 2.1s5.2-.94 5.2-2.1V4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path d="M2.8 8c0 1.16 2.33 2.1 5.2 2.1s5.2-.94 5.2-2.1" fill="none" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    )
  }
  if (name === 'learning') {
    return (
      <svg className="tab-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          d="M8 2.4 2.4 5.1 8 7.8l5.6-2.7L8 2.4Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
        <path d="M4.1 6.4v3.3c0 .9 1.7 1.9 3.9 1.9s3.9-1 3.9-1.9V6.4" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M13.6 5.2v4.8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    )
  }
  return (
    <svg className="tab-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 14.2s4.4-4.15 4.4-7.15A4.4 4.4 0 0 0 8 2.6a4.4 4.4 0 0 0-4.4 4.45C3.6 10.05 8 14.2 8 14.2Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="7" r="1.55" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  )
}

export function Header({ live, sandbox, clock, tab, recording, onTabChange }: HeaderProps) {
  return (
    <header className="dash-header">
      <div className="brand-block">
        <div>
          <h1 className="logo">LumenGrid</h1>
          <p className="tag">AI TRAFFIC DETECTION · NO CAMERAS, JUST 5G</p>
        </div>
      </div>
      <nav className="app-tabs" role="tablist" aria-label="Workspace">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'data'}
          className={tab === 'data' ? 'tab active' : 'tab'}
          onClick={() => onTabChange('data')}
        >
          <TabIcon name="data" />
          Data
          {recording ? <span className="tab-live">rec</span> : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'learning'}
          className={tab === 'learning' ? 'tab active' : 'tab'}
          onClick={() => onTabChange('learning')}
        >
          <TabIcon name="learning" />
          Learning
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'prediction'}
          className={tab === 'prediction' ? 'tab active' : 'tab'}
          onClick={() => onTabChange('prediction')}
        >
          <TabIcon name="prediction" />
          Simulation
        </button>
      </nav>
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
