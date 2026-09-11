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
        <h2>🔍 Detection Result</h2>
        <p>Run a detection (Step 3) to see what the AI found.</p>
      </section>
    )
  }

  const color = stateColor(result.prediction)
  const label = result.prediction.replace('_', ' ')

  return (
    <section className="final-panel">
      <h2>🔍 Detection Result</h2>
      <div className="final-status" style={{ borderColor: color }}>
        <span className="final-state" style={{ color }}>
          {label}
        </span>
        <span className="final-conf">{(result.confidence * 100).toFixed(0)}% confident</span>
      </div>
      <p className="final-explain">{result.explanation}</p>
      <p className="final-tagline">No cameras. No sensors. Just the 5G network.</p>
    </section>
  )
}

