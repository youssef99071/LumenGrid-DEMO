import './StatsCards.css'

interface StatsCardsProps {
  trafficHealth: number
  activeAnchors: number
  modelAccuracy: number | null
  latestConfidence: number | null
  totalReadings?: number
  totalClips?: number
  mode?: 'data' | 'learning' | 'prediction'
}

export function StatsCards({
  trafficHealth,
  activeAnchors,
  modelAccuracy,
  latestConfidence,
  totalReadings,
  totalClips,
  mode = 'prediction',
}: StatsCardsProps) {
  if (mode === 'data' || mode === 'learning') {
    return (
      <section className="stats-grid" aria-label={mode === 'data' ? 'Data statistics' : 'Learning statistics'}>
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
          <p className="stat-label">Generated clips</p>
          <p className="stat-value">{totalClips ?? '—'}</p>
          <p className="stat-hint">60s labeled sequences</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Samples</p>
          <p className="stat-value">{totalReadings ?? '—'}</p>
          <p className="stat-hint">1 Hz readings in store</p>
        </article>
      </section>
    )
  }

  return (
    <section className="stats-grid" aria-label="Prediction statistics">
      <article className="stat-card">
        <p className="stat-label">🛣️ Roads Clear</p>
        <p className="stat-value">{trafficHealth.toFixed(0)}%</p>
        <p className="stat-hint">of monitored routes flowing normally</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">📡 Zones Monitored</p>
        <p className="stat-value">{activeAnchors}</p>
        <p className="stat-hint">active 5G monitoring points</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">🎯 AI Accuracy</p>
        <p className="stat-value">{modelAccuracy != null ? `${modelAccuracy.toFixed(0)}%` : '—'}</p>
        <p className="stat-hint">correct traffic classifications</p>
      </article>
      <article className="stat-card">
        <p className="stat-label">✅ Confidence</p>
        <p className="stat-value">
          {latestConfidence != null ? `${(latestConfidence * 100).toFixed(0)}%` : '—'}
        </p>
        <p className="stat-hint">latest detection certainty</p>
      </article>
    </section>
  )
}
