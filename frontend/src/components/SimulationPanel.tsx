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
  const [speed, setSpeed] = useState<1 | 5 | 10>(10)
  const [scenario, setScenario] = useState<WhatIfScenario>('TRAFFIC_JAM')

  useEffect(() => {
    if (!locationId && locations[0]) setLocationId(locations[0].id)
  }, [locations, locationId])

  const disabled = running || !!busyLabel
  const custom = scenario === 'CUSTOM'

  return (
    <section className="sim-panel">
      <h2>Demo controls</h2>
      <p className="sim-copy">
        Record a 60s clip (wander/jitter), then match occupancy on the full sequence — same unit as
        learning.
      </p>

      <label className="field">
        <span>What-If occupancy class</span>
        <select
          value={scenario}
          disabled={disabled}
          onChange={(e) => setScenario(e.target.value as WhatIfScenario)}
        >
          <option value="EMPTY">EMPTY</option>
          <option value="LOW_OCCUPANCY">LOW OCCUPANCY</option>
          <option value="NORMAL">NORMAL</option>
          <option value="SLOW">SLOW</option>
          <option value="TRAFFIC_JAM">TRAFFIC JAM</option>
          <option value="CUSTOM">CUSTOM (slider)</option>
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

      <label className="field">
        <span>Time of day</span>
        <select
          value={timeOfDay}
          disabled={disabled}
          onChange={(e) => setTimeOfDay(e.target.value as typeof timeOfDay)}
        >
          <option value="morning">Morning</option>
          <option value="afternoon">Afternoon</option>
          <option value="evening">Evening</option>
          <option value="night">Night</option>
        </select>
      </label>

      <fieldset className="speed-row" disabled={disabled}>
        <legend>Simulation speed</legend>
        {([1, 5, 10] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={speed === s ? 'chip active' : 'chip'}
            onClick={() => setSpeed(s)}
          >
            {s}x
          </button>
        ))}
      </fieldset>

      <div className="sim-actions">
        <button
          className="primary"
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
          {running ? 'Recording…' : 'Run simulation'}
        </button>
        <button disabled={disabled} onClick={onTrain}>
          {busyLabel === 'train' ? 'Training…' : 'Train model'}
        </button>
        <button disabled={disabled} onClick={onPredictMap}>
          {busyLabel === 'map' ? 'Predicting…' : 'Predict all anchors'}
        </button>
        <button disabled={disabled} onClick={onSeedDemo}>
          {busyLabel === 'seed' ? 'Seeding…' : 'Reload learning data'}
        </button>
      </div>

      <div className="progress-wrap">
        <div className="progress-label">
          {running ? `Recording ${progress.toFixed(0)}%` : 'Idle — ready for demo'}
        </div>
        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${running ? progress : 0}%` }} />
        </div>
      </div>
    </section>
  )
}
