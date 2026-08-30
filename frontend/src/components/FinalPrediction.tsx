import { stateColor } from '../api'
import './FinalPrediction.css'

export interface FinalPredictionData {
  prediction: string
  confidence: number
  match_rate: number
  rsrp: number
  rsrq: number
  neighbor_count: number
  actual_traffic: string
  explanation: string
  timestamp: string
  location_name?: string
  scenario?: string
  wander?: number
  jitter?: number
}

interface FinalPredictionProps {
  result: FinalPredictionData | null
}

export function FinalPrediction({ result }: FinalPredictionProps) {
  if (!result) {
    return (
      <section className="final-panel empty">
        <h2>Final prediction</h2>
        <p>Run a 60s simulation to see the model’s verdict and explanation.</p>
      </section>
    )
  }

  const color = stateColor(result.prediction)

  return (
    <section className="final-panel">
      <h2>Final prediction</h2>
      <div className="final-status" style={{ borderColor: color }}>
        <span className="final-state" style={{ color }}>
          {result.prediction.replace('_', ' ')}
        </span>
        <span className="final-conf">{(result.confidence * 100).toFixed(0)}% confidence</span>
      </div>
      <p className="final-meta">
        60s clip · mean match {result.match_rate}% · RSRP {result.rsrp} · RSRQ {result.rsrq}
        {result.wander != null ? ` · wander ${result.wander}` : ''}
        {result.jitter != null ? ` · jitter ${result.jitter}` : ''}
        {result.scenario && result.scenario !== 'CUSTOM' ? ` · What-If ${result.scenario}` : ''}
      </p>
      <p className="final-explain">{result.explanation}</p>
    </section>
  )
}
