import { useState } from 'react'
import { api } from '../api'
import './SamplePredict.css'

type Modality = 'full' | 'gps_camara' | 'cell_camara'

interface SamplePredictProps {
  locationId?: string | null
  locationName?: string
}

export function SamplePredict({ locationId, locationName }: SamplePredictProps) {
  const [modality, setModality] = useState<Modality>('full')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{
    prediction: string
    confidence: number
    explanation: string
    sample_count: number
    match_rate_mean: number
    wander: number
    jitter: number
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.predictClip({
        modality,
        location_id: locationId || undefined,
      })
      setResult({
        prediction: res.prediction,
        confidence: res.confidence,
        explanation: res.explanation,
        sample_count: res.sample_count,
        match_rate_mean: res.match_rate,
        wander: res.wander,
        jitter: res.jitter,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Predict failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="sample-panel">
      <h2>Predict stored clip</h2>
      <p className="sample-copy">
        Inference only — uses the latest generated 60s clip
        {locationName ? ` at ${locationName}` : ''}. Generate data first if none exist.
      </p>

      <label className="field">
        <span>Modality</span>
        <select value={modality} onChange={(e) => setModality(e.target.value as Modality)}>
          <option value="full">GPS + cellinfo + CAMARA</option>
          <option value="gps_camara">GPS + CAMARA</option>
          <option value="cell_camara">cellinfo + CAMARA</option>
        </select>
      </label>

      <button className="primary" disabled={busy} onClick={() => void run()}>
        {busy ? 'Matching clip…' : 'Predict 60s clip'}
      </button>

      {error && <p className="sample-error">{error}</p>}
      {result && (
        <div className="sample-result">
          <strong>{result.prediction.replace(/_/g, ' ')}</strong>
          <span>{(result.confidence * 100).toFixed(0)}%</span>
          <p>
            {result.sample_count}s clip · mean match {result.match_rate_mean}% · wander{' '}
            {result.wander} · jitter {result.jitter}
          </p>
          <p>{result.explanation}</p>
        </div>
      )}
    </section>
  )
}
