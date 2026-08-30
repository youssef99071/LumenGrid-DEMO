import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api,
  type DashboardStats,
  type LocationDef,
  type MapMarker,
  type MatchRatePoint,
  type PredictionUpdate,
  type RecordingRow,
  type TrafficPrediction,
  type WsMessage,
} from './api'
import { Charts, type ComparisonPoint } from './components/Charts'
import { DataTable } from './components/DataTable'
import { FinalPrediction, type FinalPredictionData } from './components/FinalPrediction'
import { Header } from './components/Header'
import { PredictionFeed } from './components/PredictionFeed'
import { SamplePredict } from './components/SamplePredict'
import { SimulationPanel } from './components/SimulationPanel'
import { StatsCards } from './components/StatsCards'
import { TrafficMap } from './components/TrafficMap'
import { usePredictionSocket } from './hooks/usePredictionSocket'
import './App.css'

function formatClock(d: Date) {
  return d.toLocaleString(undefined, {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function mergeComparison(
  base: ComparisonPoint[],
  series: MatchRatePoint[],
  key: 'NORMAL' | 'TRAFFIC_JAM' | 'SLOW' | 'current',
): ComparisonPoint[] {
  const byT = new Map<number, ComparisonPoint>()
  for (const p of base) byT.set(p.t, { ...p })
  for (const p of series) {
    const row = byT.get(p.t) ?? { t: p.t }
    row[key] = p.match_rate
    byT.set(p.t, row)
  }
  return Array.from(byT.values()).sort((a, b) => a.t - b.t)
}

export default function App() {
  const [clock, setClock] = useState(() => formatClock(new Date()))
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [locations, setLocations] = useState<LocationDef[]>([])
  const [markers, setMarkers] = useState<MapMarker[]>([])
  const [predictions, setPredictions] = useState<TrafficPrediction[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sandbox, setSandbox] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [simRunning, setSimRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [matchSeries, setMatchSeries] = useState<MatchRatePoint[]>([])
  const [comparison, setComparison] = useState<ComparisonPoint[]>([])
  const [probabilities, setProbabilities] = useState<Record<string, number>>({
    NORMAL: 0.34,
    SLOW: 0.33,
    TRAFFIC_JAM: 0.33,
  })
  const [recording, setRecording] = useState<RecordingRow[]>([])
  const [finalResult, setFinalResult] = useState<FinalPredictionData | null>(null)
  const [accuracyHistory, setAccuracyHistory] = useState<{ label: string; accuracy: number }[]>([
    { label: 't-4', accuracy: 88 },
    { label: 't-3', accuracy: 90 },
    { label: 't-2', accuracy: 91 },
    { label: 't-1', accuracy: 89 },
    { label: 'now', accuracy: 90 },
  ])
  const activeScenario = useRef<string>('CUSTOM')
  const liveSeries = useRef<MatchRatePoint[]>([])

  const refresh = useCallback(async () => {
    try {
      const [dash, locs, preds, nac] = await Promise.all([
        api.dashboardStats(),
        api.locations(),
        api.predictions(40),
        api.nacStatus(),
      ])
      setStats(dash)
      setLocations(locs)
      setMarkers(dash.markers)
      setPredictions(preds)
      setSandbox(nac.sandbox_mode)
      if (dash.model_accuracy != null) {
        setAccuracyHistory((prev) => {
          const next = [...prev.slice(-4), { label: 'now', accuracy: dash.model_accuracy! }]
          return next.map((p, i) => ({
            ...p,
            label: i === next.length - 1 ? 'now' : `t-${next.length - 1 - i}`,
          }))
        })
      }
      setSelectedId((cur) => cur ?? dash.markers[0]?.location_id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const id = window.setInterval(() => setClock(formatClock(new Date())), 1000)
    return () => window.clearInterval(id)
  }, [])

  const onWs = useCallback(
    (msg: WsMessage) => {
      if (msg.type === 'simulation_started') {
        setSimRunning(true)
        setProgress(0)
        setMatchSeries([])
        liveSeries.current = []
        setRecording([])
        setFinalResult(null)
        setSelectedId(msg.location_id)
        activeScenario.current = msg.scenario ?? 'CUSTOM'
        setError(null)
        return
      }
      if (msg.type === 'simulation_complete') {
        setSimRunning(false)
        setProgress(100)
        const scenario = msg.scenario ?? activeScenario.current
        if (scenario === 'NORMAL' || scenario === 'TRAFFIC_JAM' || scenario === 'SLOW') {
          setComparison((prev) => mergeComparison(prev, liveSeries.current, scenario))
        }
        if (msg.final_prediction) {
          setFinalResult({
            ...msg.final_prediction,
            location_name: msg.location_name,
            scenario,
          })
          setProbabilities(msg.final_prediction.probabilities)
        }
        void refresh()
        return
      }
      if (msg.type === 'error') {
        setSimRunning(false)
        setError(msg.message)
        return
      }
      if (msg.type === 'prediction_update') {
        const update = msg as PredictionUpdate
        setProgress(update.progress)
        setProbabilities(update.probabilities)
        const point = { t: update.sample_index, match_rate: update.match_rate }
        liveSeries.current = [...liveSeries.current, point].slice(-60)
        setMatchSeries(liveSeries.current)
        setComparison((prev) => mergeComparison(prev, liveSeries.current, 'current'))
        setRecording((prev) =>
          [
            {
              timestamp: update.timestamp,
              match_rate: update.match_rate,
              rsrp: update.rsrp,
              rsrq: update.rsrq,
              actual_traffic: update.actual_traffic,
              predicted_traffic: update.prediction,
              correct: update.correct,
              confidence: update.confidence,
            },
            ...prev,
          ].slice(0, 60),
        )
        setMarkers((prev) =>
          prev.map((m) =>
            m.location_id === update.location_id
              ? {
                  ...m,
                  prediction: update.prediction,
                  confidence: update.confidence,
                  match_rate: update.match_rate,
                  updated_at: update.timestamp,
                  pulsing: true,
                  latitude: update.latitude,
                  longitude: update.longitude,
                }
              : { ...m, pulsing: false },
          ),
        )
        setPredictions((prev) =>
          [
            {
              id: update.prediction_id ?? `${update.timestamp}-${update.location_id}`,
              timestamp: update.timestamp,
              location_id: update.location_id,
              predicted_state: update.prediction,
              confidence: update.confidence,
              model_version: 'poc-v0.1',
            },
            ...prev,
          ].slice(0, 40),
        )
        setStats((prev) =>
          prev
            ? {
                ...prev,
                latest_confidence: update.confidence,
              }
            : prev,
        )
      }
    },
    [refresh],
  )

  const wsLive = usePredictionSocket(onWs)

  async function runAction(label: string, fn: () => Promise<void>) {
    setBusy(label)
    setError(null)
    try {
      await fn()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed')
    } finally {
      setBusy(null)
    }
  }

  const mapMarkers = useMemo(() => markers, [markers])

  return (
    <div className="dashboard">
      <Header live={wsLive} sandbox={sandbox} clock={clock} />

      {error && <div className="banner error">{error}</div>}

      <div className="dash-body">
        <StatsCards
          trafficHealth={stats?.traffic_health_pct ?? 100}
          activeAnchors={stats?.active_anchors ?? locations.length}
          modelAccuracy={stats?.model_accuracy ?? null}
          latestConfidence={stats?.latest_confidence ?? null}
        />

        <div className="main-grid">
          <div className="col-map">
            <TrafficMap
              markers={mapMarkers}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>

          <div className="col-side">
            <SimulationPanel
              locations={locations}
              running={simRunning}
              progress={progress}
              busyLabel={busy}
              onRun={(opts) => {
                void (async () => {
                  setError(null)
                  try {
                    await api.runSimulation({ ...opts, duration_seconds: 60 })
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Simulation failed')
                  }
                })()
              }}
              onSeedDemo={() =>
                runAction('seed', async () => {
                  await api.seedDemo(true)
                })
              }
              onTrain={() =>
                runAction('train', async () => {
                  const res = await api.trainModel()
                  if (res.accuracy != null) {
                    setAccuracyHistory((prev) => [
                      ...prev.slice(-4),
                      { label: 'train', accuracy: res.accuracy },
                    ])
                  }
                })
              }
              onPredictMap={() =>
                runAction('map', async () => {
                  const res = await api.predictAnchors('full')
                  setMarkers(
                    res.markers.map((m) => ({
                      ...m,
                      pulsing: true,
                    })),
                  )
                })
              }
            />
            <SamplePredict />
            <FinalPrediction result={finalResult} />
            <PredictionFeed items={predictions} />
          </div>
        </div>

        <Charts
          matchSeries={matchSeries}
          comparison={comparison}
          probabilities={probabilities}
          accuracyHistory={accuracyHistory}
        />

        <DataTable rows={recording} />
      </div>
    </div>
  )
}
