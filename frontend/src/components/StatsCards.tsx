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
        <p className="stat-label">🛣️ Roads Clear</p>
        <p className="stat-value">{trafficHealth.toFixed(0)}%</p>
        <p className="stat-hint">of monitored zones flowing normally</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">📡 Zones Monitored</p>
        <p className="stat-value">{activeAnchors}</p>
        <p className="stat-hint">live sensing points across Tunis</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">🎯 AI Accuracy</p>
        <p className="stat-value">{modelAccuracy != null ? `${modelAccuracy.toFixed(0)}%` : '—'}</p>
        <p className="stat-hint">correctly identifies congestion</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">✅ Confidence</p>
        <p className="stat-value">
          {latestConfidence != null ? `${(latestConfidence * 100).toFixed(0)}%` : '—'}
        </p>
        <p className="stat-hint">certainty of the last detection</p>
      </article>
    </section>
  )
}

