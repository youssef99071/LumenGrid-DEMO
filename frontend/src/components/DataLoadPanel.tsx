import { useEffect, useState } from 'react'
import './DataLoadPanel.css'

interface DataLoadPanelProps {
  loading: boolean
  loaded: boolean
  totalClips: number
  totalZones: number
  onLoad: () => void
}

const STEPS = [
  { label: 'Connecting to 10 monitoring zones', duration: 900 },
  { label: 'Streaming 7 days of 5G signal history', duration: 2200 },
  { label: 'Labelling traffic states per signal window', duration: 1400 },
  { label: 'Writing signal clips to database', duration: 800 },
]

export function DataLoadPanel({
  loading,
  loaded,
  totalClips,
  totalZones,
  onLoad,
}: DataLoadPanelProps) {
  const [activeStep, setActiveStep] = useState(-1)
  const [doneSteps, setDoneSteps] = useState<number[]>([])

  useEffect(() => {
    if (!loading) {
      if (!loaded) {
        setActiveStep(-1)
        setDoneSteps([])
      }
      return
    }

    // Animate steps one by one based on their durations
    setActiveStep(0)
    setDoneSteps([])

    let elapsed = 0
    const timers: ReturnType<typeof setTimeout>[] = []

    STEPS.forEach((step, i) => {
      // Mark step as done after its duration
      const doneAt = elapsed + step.duration
      timers.push(
        setTimeout(() => {
          setDoneSteps((prev) => [...prev, i])
          if (i < STEPS.length - 1) setActiveStep(i + 1)
        }, doneAt),
      )
      elapsed += step.duration
    })

    return () => timers.forEach(clearTimeout)
  }, [loading, loaded])

  return (
    <section className="dlp-panel">
      <div className="dlp-head">
        <h2>🚀 Step 1 — Load Training Data</h2>
        <p className="dlp-copy">
          Feed the AI 7 days of historical 5G signal data across 10 monitoring zones along Avenue
          Habib Bourguiba. This teaches it what each traffic state looks like in radio waves.
        </p>
      </div>

      {/* Step list — only shown while loading or after done */}
      {(loading || loaded) && (
        <ol className="dlp-steps">
          {STEPS.map((step, i) => {
            const isDone = doneSteps.includes(i)
            const isActive = activeStep === i && loading
            return (
              <li
                key={i}
                className={`dlp-step ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
              >
                <span className="dlp-icon">
                  {isDone ? '✅' : isActive ? <span className="dlp-spinner" /> : '○'}
                </span>
                <span className="dlp-label">{step.label}</span>
              </li>
            )
          })}
        </ol>
      )}

      {/* Success message */}
      {loaded && !loading && (
        <div className="dlp-success">
          <span className="dlp-success-icon">⚡</span>
          <div>
            <p className="dlp-success-title">Data loaded successfully</p>
            <p className="dlp-success-sub">
              {totalClips.toLocaleString()} signal clips across {totalZones} zones — ready to train
            </p>
          </div>
        </div>
      )}

      {/* CTA button */}
      <div className="dlp-actions">
        <button className="primary" disabled={loading} onClick={onLoad}>
          {loading ? 'Loading…' : '📥 Load Training Data'}
        </button>
        {loaded && !loading && (
          <p className="dlp-next">→ Go to the <strong>Learning</strong> tab to train the AI</p>
        )}
      </div>
    </section>
  )
}
