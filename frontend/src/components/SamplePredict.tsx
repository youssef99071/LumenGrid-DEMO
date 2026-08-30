import { useState } from 'react'
import { api } from '../api'
import './SamplePredict.css'

type Scenario = 'EMPTY' | 'LOW_OCCUPANCY' | 'NORMAL' | 'SLOW' | 'TRAFFIC_JAM'
type Modality = 'full' | 'gps_camara' | 'cell_camara'

export function SamplePredict() {
  const [modality, setModality] = useState<Modality>('full')
  const [scenario, setScenario] = useState<Scenario>('TRAFFIC_JAM')
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
      const res = await api.samplePredict({
        modality,
        scenario,
        latitude: 36.7992,
        longitude: 10.1802,
        location_name: 'Sample 60s clip',
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Predict failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="sample-panel">
      <h2>Sample 60s clip</h2>
      <p className="sample-copy">
        Matching uses a full 60-second sequence (wander + jitter), not a single snapshot. Pick a
        What-If class to synthesize a clip, then run inference.
      </p>

      <label className="field">
        <span>Modality</span>
        <select value={modality} onChange={(e) => setModality(e.target.value as Modality)}>
          <option value="full">GPS + cellinfo + CAMARA</option>
          <option value="gps_camara">GPS + CAMARA</option>
          <option value="cell_camara">cellinfo + CAMARA</option>
        </select>
      </label>

      <label className="field">
        <span>Synthesize 60s clip as</span>
        <select value={scenario} onChange={(e) => setScenario(e.target.value as Scenario)}>
          <option value="EMPTY">EMPTY</option>
          <option value="LOW_OCCUPANCY">LOW OCCUPANCY</option>
          <option value="NORMAL">NORMAL</option>
          <option value="SLOW">SLOW</option>
          <option value="TRAFFIC_JAM">TRAFFIC JAM</option>
        </select>
      </label>

      <button className="primary" disabled={busy} onClick={() => void run()}>
        {busy ? 'Matching clip…' : 'Match 60s clip'}
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
