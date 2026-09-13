import './LearningPanel.css'

interface LearningPanelProps {
  busyLabel: string | null
  onSeedDemo?: () => void
  onTrain?: () => void
}

export function LearningPanel({ busyLabel, onSeedDemo, onTrain }: LearningPanelProps) {
  const disabled = !!busyLabel
  const generateMode = !!onSeedDemo

  return (
    <section className="learn-panel">
      <h2>{generateMode ? 'Data generation' : 'Learning'}</h2>
      {generateMode ? (
        <>
          <p className="learn-copy">
            Paint occupancy areas on the map, then generate labeled 60s clips at those sites. This
            tab does not train or predict.
          </p>
          <ol className="learn-steps">
            <li>Select a class and click the map to mark its area.</li>
            <li>Generate 7 days of 60s clips from those areas (or default anchors if none).</li>
            <li>Open Learning to train, then Prediction to match stored clips.</li>
          </ol>
          <div className="learn-actions">
            <button className="primary" disabled={disabled} onClick={onSeedDemo}>
              {busyLabel === 'seed' ? 'Generating…' : 'Generate learning data'}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="learn-copy">
            Train the occupancy classifier on already-generated clips. Inference stays on the
            Prediction tab.
          </p>
          <div className="learn-actions">
            <button className="primary" disabled={disabled} onClick={onTrain}>
              {busyLabel === 'train' ? 'Training…' : 'Train model'}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
