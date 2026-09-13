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

interface GenerateProps {
  mode: 'generate'
  locations: LocationDef[]
  running: boolean
  progress: number
  busyLabel: string | null
  hasClip: boolean
  onRun: (opts: {
    traffic_intensity: number
    location_id: string
    time_of_day: 'morning' | 'afternoon' | 'evening' | 'night'
    speed: 1 | 5 | 10
    scenario: WhatIfScenario
  }) => void
}

interface PredictProps {
  mode: 'predict'
  busyLabel: string | null
  hasClip: boolean
  running?: boolean
  onPredictMap: () => void
  onPredictClip: () => void
}

type SimulationPanelProps = GenerateProps | PredictProps

const SCENARIO_HINT: Record<WhatIfScenario, string> = {
  CUSTOM: 'Use the intensity slider for a free-form recording.',
  EMPTY: 'Near-empty road — match rate ~90–99%.',
  LOW_OCCUPANCY: 'Light traffic — match rate ~80–92%.',
  NORMAL: 'Typical flow — match rate ~68–82%.',
  SLOW: 'Congested — match rate ~52–68%.',
  TRAFFIC_JAM: 'Jam band — match rate 35–55%.',
}

export function SimulationPanel(props: SimulationPanelProps) {
  if (props.mode === 'predict') {
    const { busyLabel, hasClip, running, onPredictClip, onPredictMap } = props
    const disabled = !!running || !!busyLabel
    return (
      <section className="sim-panel">
        <h2>⚡ Step 3 — Run Live Detection</h2>
        <p className="sim-copy">
          Pick a traffic scenario and watch the AI detect it in real time — purely from 5G signal
          patterns. No cameras involved.
        </p>
        <div className="sim-actions">
          <button className="primary" disabled={disabled || !hasClip} onClick={onPredictClip}>
            {busyLabel === 'clip' ? 'Detecting…' : '▶ Run Live Detection'}
          </button>
          <button disabled={disabled} onClick={onPredictMap}>
            {busyLabel === 'map' ? 'Scanning…' : '🗺 Scan All Locations on Map'}
          </button>
        </div>
        {!hasClip && (
          <p className="hint">Go to the Data tab first and load training data to begin.</p>
        )}
      </section>
    )
  }

  return <GenerateClipForm {...props} />
}

function GenerateClipForm({
  locations,
  running,
  progress,
  busyLabel,
  hasClip,
  onRun,
}: GenerateProps) {
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
      <h2>🎮 Simulate a Traffic Scenario</h2>
      <p className="sim-copy">
        Pick what is happening on the road. The system will generate the 5G signal that scenario
        would produce — then the AI detects it.
      </p>

      <label className="field">
        <span>Occupancy class</span>
        <select
          value={scenario}
          disabled={disabled}
          onChange={(e) => setScenario(e.target.value as WhatIfScenario)}
        >
          <option value="EMPTY">🟢 Empty road</option>
          <option value="LOW_OCCUPANCY">🟡 Light traffic</option>
          <option value="NORMAL">🟠 Normal flow</option>
          <option value="SLOW">🔵 Slow / congested</option>
          <option value="TRAFFIC_JAM">🔴 Traffic jam</option>
          <option value="CUSTOM">⚙️ Custom (slider)</option>
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
        <legend>Recording speed</legend>
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
          {running ? 'Generating signal…' : '📡 Generate 5G Signal Clip'}
        </button>
      </div>

      <div className="progress-wrap">
        <div className="progress-label">
          {running
            ? `Generating ${progress.toFixed(0)}%`
            : hasClip
              ? 'Clip stored — open Prediction to match it'
              : 'Idle — generate a clip'}
        </div>
        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${running ? progress : 0}%` }} />
        </div>
      </div>
    </section>
  )
}
