import { useEffect, useState } from 'react'
import type { LocationDef } from '../api'
import './SimulationPanel.css'

export type WhatIfScenario =
  | 'CUSTOM'
  | 'EMPTY'
  | 'LOW_OCCUPANCY'
  | 'NORMAL'
  | 'SLOW'
  | 'TRAFFIC_JAM'

interface SimulationPanelProps {
  locations: LocationDef[]
  running: boolean
  progress: number
  busyLabel: string | null
  onRun: (opts: {
    traffic_intensity: number
    location_id: string
    time_of_day: 'morning' | 'afternoon' | 'evening' | 'night'
    speed: 1 | 5 | 10
    scenario: WhatIfScenario
  }) => void
  onSeedDemo: () => void
  onTrain: () => void
  onPredictMap: () => void
}

const SCENARIO_HINT: Record<WhatIfScenario, string> = {
  CUSTOM: 'Use the intensity slider for a free-form recording.',
  EMPTY: 'Near-empty road — match rate ~90–99%.',
  LOW_OCCUPANCY: 'Light traffic — match rate ~80–92%.',
  NORMAL: 'Typical flow — match rate ~68–82%.',
  SLOW: 'Congested — match rate ~52–68%.',
  TRAFFIC_JAM: 'Jam band — match rate 35–55%.',
}

export function SimulationPanel({
  locations,
  running,
  progress,
  busyLabel,
  onRun,
  onSeedDemo,
  onTrain,
  onPredictMap,
}: SimulationPanelProps) {
  const [intensity, setIntensity] = useState(55)
  const [locationId, setLocationId] = useState('')
  const [timeOfDay, setTimeOfDay] = useState<'morning' | 'afternoon' | 'evening' | 'night'>(
    'morning',
  )
  const [speed] = useState<1 | 5 | 10>(10)
  const [scenario, setScenario] = useState<WhatIfScenario>('TRAFFIC_JAM')

  useEffect(() => {
    if (!locationId && locations[0]) setLocationId(locations[0].id)
  }, [locations, locationId])

  const disabled = running || !!busyLabel
  const custom = scenario === 'CUSTOM'

  return (
    <section className="sim-panel">
      <h2>🎬 Run the Demo</h2>
      <p className="sim-copy">
        See how LumenGrid detects traffic using invisible 5G signals — no cameras, no sensors.
      </p>

      {/* Step 1 */}
      <div className="step-block">
        <div className="step-header">
          <span className="step-badge">1</span>
          <span className="step-title">Load Training Data</span>
        </div>
        <p className="step-desc">Feed the AI one week of historical signal data to learn from.</p>
        <button disabled={disabled} onClick={onSeedDemo} className="step-btn">
          {busyLabel === 'seed' ? '⏳ Loading data…' : '📥 Load Training Data'}
        </button>
      </div>

      {/* Step 2 */}
      <div className="step-block">
        <div className="step-header">
          <span className="step-badge">2</span>
          <span className="step-title">Train the AI</span>
        </div>
        <p className="step-desc">The AI learns to recognize traffic patterns from the 5G signal fingerprint.</p>
        <button disabled={disabled} onClick={onTrain} className="step-btn">
          {busyLabel === 'train' ? '⏳ Training AI…' : '🧠 Train the AI (~2 seconds)'}
        </button>
      </div>

      {/* Step 3 */}
      <div className="step-block">
        <div className="step-header">
          <span className="step-badge">3</span>
          <span className="step-title">Run Live Detection</span>
        </div>
        <p className="step-desc">Pick a traffic scenario and watch the AI detect it in real time.</p>

        <label className="field">
          <span>Traffic scenario</span>
          <select
            value={scenario}
            disabled={disabled}
            onChange={(e) => setScenario(e.target.value as WhatIfScenario)}
          >
            <option value="EMPTY">🟢 Empty road</option>
            <option value="LOW_OCCUPANCY">🔵 Light traffic</option>
            <option value="NORMAL">🟡 Normal flow</option>
            <option value="SLOW">🟠 Slow — congestion building</option>
            <option value="TRAFFIC_JAM">🔴 Traffic jam</option>
            <option value="CUSTOM">⚙️ Custom (use slider)</option>
          </select>
          <span className="hint">{SCENARIO_HINT[scenario]}</span>
        </label>

        {custom && (
          <label className="field">
            <span>Traffic intensity · {intensity}%</span>
            <input
              type="range"
              min={0}
              max={100}
              value={intensity}
              disabled={disabled}
              onChange={(e) => setIntensity(Number(e.target.value))}
            />
          </label>
        )}

        <label className="field">
          <span>Location</span>
          <select
            value={locationId || locations[0]?.id || ''}
            disabled={disabled}
            onChange={(e) => setLocationId(e.target.value)}
          >
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>

        <button
          className="primary step-btn run-btn"
          disabled={disabled || !locations.length}
          onClick={() =>
            onRun({
              traffic_intensity: intensity,
              location_id: locationId || locations[0].id,
              time_of_day: timeOfDay,
              speed,
              scenario,
            })
          }
        >
          {running ? '📡 Detecting… ' : '▶  Run Live Detection'}
        </button>
      </div>

      {/* Bonus action */}
      <div className="step-block step-block--alt">
        <button disabled={disabled} onClick={onPredictMap} className="step-btn">
          {busyLabel === 'map' ? '⏳ Scanning…' : '🗺️ Scan All Locations on Map'}
        </button>
        <p className="step-desc">Instantly predict traffic for every monitored zone across Tunis.</p>
      </div>

      <div className="progress-wrap">
        <div className="progress-label">
          {running ? `Detecting… ${progress.toFixed(0)}%` : 'Ready — choose a step above'}
        </div>
        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${running ? progress : 0}%` }} />
        </div>
      </div>
    </section>
  )
}

