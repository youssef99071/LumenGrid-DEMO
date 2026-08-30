import type { TrafficPrediction } from '../api'
import './PredictionFeed.css'

function tagClass(state: string) {
  if (state === 'TRAFFIC_JAM') return 'tag jam'
  if (state === 'SLOW') return 'tag slow'
  if (state === 'EMPTY') return 'tag empty'
  if (state === 'LOW_OCCUPANCY') return 'tag low'
  return 'tag normal'
}

interface PredictionFeedProps {
  items: TrafficPrediction[]
}

export function PredictionFeed({ items }: PredictionFeedProps) {
  return (
    <section className="feed-panel">
      <h2>Prediction feed</h2>
      <div className="feed-scroll">
        {items.length === 0 ? (
          <p className="empty">No predictions yet. Run a simulation or generate data.</p>
        ) : (
          items.map((p) => (
            <article key={p.id} className="feed-item">
              <div className="feed-top">
                <span className={tagClass(p.predicted_state)}>
                  {p.predicted_state.replace('_', ' ')}
                </span>
                <span className="feed-conf">{(p.confidence * 100).toFixed(0)}%</span>
              </div>
              <p className="feed-loc">{p.location_id}</p>
              <time>{new Date(p.timestamp).toLocaleTimeString()}</time>
            </article>
          ))
        )}
      </div>
    </section>
  )
}
