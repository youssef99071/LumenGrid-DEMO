import './StatsCards.css'

interface StatsCardsProps {
  trafficHealth: number
  activeAnchors: number
  modelAccuracy: number | null
  latestConfidence: number | null
}

export function StatsCards({
  trafficHealth,
  activeAnchors,
  modelAccuracy,
  latestConfidence,
}: StatsCardsProps) {
  return (
    <section className="stats-grid" aria-label="Traffic statistics">
      <article className="stat-card">
        <p className="stat-label">Traffic health</p>
        <p className="stat-value">{trafficHealth.toFixed(0)}%</p>
        <p className="stat-hint">share labeled NORMAL</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">Active anchors</p>
        <p className="stat-value">{activeAnchors}</p>
        <p className="stat-hint">Tunis corridor sites</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">Model accuracy</p>
        <p className="stat-value">{modelAccuracy != null ? `${modelAccuracy.toFixed(0)}%` : '—'}</p>
        <p className="stat-hint">vs ground-truth labels</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">Latest confidence</p>
        <p className="stat-value">
          {latestConfidence != null ? `${(latestConfidence * 100).toFixed(0)}%` : '—'}
        </p>
        <p className="stat-hint">most recent prediction</p>
      </article>
    </section>
  )
}
