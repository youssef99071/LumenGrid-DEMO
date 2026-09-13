import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api,
  readCachedLocations,
  type DashboardStats,
  type LocationDef,
  type MapMarker,
  type MatchRatePoint,
  type TrafficPrediction,
  type WsMessage,
} from './api'
import { Charts, type ComparisonPoint } from './components/Charts'
import { DataLoadPanel } from './components/DataLoadPanel'
import { FinalPrediction, type FinalPredictionData } from './components/FinalPrediction'
import { Header, type AppTab } from './components/Header'
import { PredictionFeed } from './components/PredictionFeed'
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

function markersFromLocations(locs: LocationDef[]): MapMarker[] {
  return locs.map((loc) => ({
    location_id: loc.id,
    name: loc.name,
    district: loc.district,
    latitude: loc.latitude,
    longitude: loc.longitude,
    prediction: 'NORMAL',
    confidence: 0,
    match_rate: null,
    updated_at: null,
  }))
}

function mergeLiveMarkers(base: MapMarker[], live: MapMarker[]): MapMarker[] {
  if (!live.length) return base
  if (!base.length) return live
  const liveById = new Map(live.map((m) => [m.location_id, m]))
  const seen = new Set<string>()
  const merged = base.map((pin) => {
    seen.add(pin.location_id)
    const next = liveById.get(pin.location_id)
    if (!next) return pin
    return {
      ...next,
      location_id: pin.location_id,
      name: pin.name,
      district: pin.district,
      latitude: pin.latitude,
      longitude: pin.longitude,
    }
  })
  for (const next of live) {
    if (!seen.has(next.location_id)) merged.push(next)
  }
  return merged
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

/**
 * Derive a realistic probability distribution from a live match_rate reading.
 * Keeps the confidence bar chart live during simulation without a separate predict call.
 * Bands mirror the backend _metrics_for_label() ranges.
 */
function probsFromMatchRate(mr: number): Record<string, number> {
  const centres: Record<string, number> = {
    EMPTY: 94.5,
    LOW_OCCUPANCY: 86,
    NORMAL: 75,
    SLOW: 60,
    TRAFFIC_JAM: 45,
  }
  const rawScores: Record<string, number> = {}
  for (const [k, c] of Object.entries(centres)) {
    rawScores[k] = Math.exp(-Math.abs(mr - c) / 8)
  }
  const total = Object.values(rawScores).reduce((s, v) => s + v, 0)
  const result: Record<string, number> = {}
  for (const [k, v] of Object.entries(rawScores)) {
    result[k] = v / total
  }
  return result
}

export default function App() {
  const [clock, setClock] = useState(() => formatClock(new Date()))
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [locations, setLocations] = useState<LocationDef[]>(() => readCachedLocations())
  const [markers, setMarkers] = useState<MapMarker[]>(() => markersFromLocations(readCachedLocations()))
  const [predictions, setPredictions] = useState<TrafficPrediction[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(() => readCachedLocations()[0]?.id ?? null)
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
  const [finalResult, setFinalResult] = useState<FinalPredictionData | null>(null)
  const [lastClipId, setLastClipId] = useState<string | null>(null)
  const [tab, setTab] = useState<AppTab>('data')
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
    let locs: LocationDef[] = []
    try {
      locs = await api.locations()
      setLocations(locs)
      setMarkers((prev) => mergeLiveMarkers(prev, markersFromLocations(locs)))
      setSelectedId((cur) => cur ?? locs[0]?.id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load locations')
    }

    try {
      const [dash, preds, nac] = await Promise.all([
        api.dashboardStats(),
        api.predictions(40),
        api.nacStatus(),
      ])
      setStats(dash)
      if (dash.markers.length) {
        setMarkers((prev) => mergeLiveMarkers(prev.length ? prev : markersFromLocations(locs), dash.markers))
      }
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
      setSelectedId((cur) => cur ?? dash.markers[0]?.location_id ?? locs[0]?.id ?? null)
      setError(null)
    } catch (err) {
      if (!locs.length) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard')
      }
    }
  }, [])

  useEffect(() => {
    void refresh()
    const retry = window.setTimeout(() => void refresh(), 2000)
    return () => window.clearTimeout(retry)
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
        setFinalResult(null)
        setLastClipId(msg.clip_id ?? null)
        setSelectedId(msg.location_id)
        activeScenario.current = msg.scenario ?? 'CUSTOM'
        setError(null)
        return
      }
      if (msg.type === 'simulation_complete') {
        setSimRunning(false)
        setProgress(100)
        if (msg.clip_id) setLastClipId(msg.clip_id)
        const scenario = msg.scenario ?? activeScenario.current
        if (scenario === 'NORMAL' || scenario === 'TRAFFIC_JAM' || scenario === 'SLOW') {
          setComparison((prev) => mergeComparison(prev, liveSeries.current, scenario))
        }
        void refresh()
        return
      }
      if (msg.type === 'error') {
        setSimRunning(false)
        setError(msg.message)
        return
      }
      if (msg.type === 'recording_update') {
        setProgress(msg.progress)
        if (msg.clip_id) setLastClipId(msg.clip_id)
        const point = { t: msg.sample_index, match_rate: msg.match_rate }
        liveSeries.current = [...liveSeries.current, point].slice(-60)
        setMatchSeries(liveSeries.current)
        setComparison((prev) => mergeComparison(prev, liveSeries.current, 'current'))
        // Update confidence bars live from the current signal level
        setProbabilities(probsFromMatchRate(msg.match_rate))
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
      <Header
        live={wsLive}
        sandbox={sandbox}
        clock={clock}
        tab={tab}
        recording={simRunning}
        onTabChange={setTab}
      />

      {error && <div className="banner error">{error}</div>}

      <div className="dash-body">
        <StatsCards
          mode={tab}
          trafficHealth={stats?.traffic_health_pct ?? 100}
          activeAnchors={stats?.active_anchors ?? locations.length}
          modelAccuracy={stats?.model_accuracy ?? null}
          latestConfidence={stats?.latest_confidence ?? null}
          totalReadings={stats?.total_readings}
          totalClips={stats?.total_clips}
        />

        {tab === 'data' && (
          <>
            <div className="main-grid">
              <div className="col-map">
                <TrafficMap
                  markers={mapMarkers}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              </div>
              <div className="col-side">
                <DataLoadPanel
                  loading={busy === 'seed'}
                  loaded={(stats?.total_clips ?? 0) > 0}
                  totalClips={stats?.total_clips ?? 0}
                  totalZones={stats?.active_anchors ?? 0}
                  onLoad={() =>
                    runAction('seed', async () => {
                      await api.seedDemo(true)
                    })
                  }
                />
              </div>
            </div>
          </>
        )}

        {tab === 'learning' && (
          <>
            <div className="main-grid">
              <div className="col-map">
                <TrafficMap
                  markers={mapMarkers}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              </div>
              <div className="col-side">
                <section className="sim-panel">
                  <h2>🧠 Step 2 — Train the AI</h2>
                  <p className="sim-copy">
                    The AI studies the loaded signal data and learns to recognise each traffic
                    condition by its unique 5G radio fingerprint. No cameras. No sensors.
                  </p>
                  <div className="sim-actions">
                    <button
                      className="primary"
                      disabled={!!busy}
                      onClick={() =>
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
                    >
                      {busy === 'train' ? 'Training…' : '🎓 Train the AI'}
                    </button>
                  </div>
                  {stats?.model_accuracy != null && (
                    <p className="hint">
                      ✅ Model trained — {stats.model_accuracy.toFixed(0)}% accuracy on test data
                    </p>
                  )}
                </section>
              </div>
            </div>
            <Charts
              mode="learning"
              matchSeries={matchSeries}
              comparison={comparison}
              probabilities={probabilities}
              accuracyHistory={accuracyHistory}
            />
          </>
        )}

        {tab === 'prediction' && (
          <>
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
                  mode="generate"
                  locations={locations}
                  running={simRunning}
                  progress={progress}
                  busyLabel={busy}
                  hasClip={!!lastClipId || (stats?.total_clips ?? 0) > 0}
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
                />
                <SimulationPanel
                  mode="predict"
                  running={simRunning}
                  busyLabel={busy}
                  hasClip={!!lastClipId || (stats?.total_clips ?? 0) > 0}
                  onPredictClip={() =>
                    runAction('clip', async () => {
                      const res = await api.predictClip({
                        clip_id: lastClipId || undefined,
                        location_id: selectedId || undefined,
                      })
                      setLastClipId(res.clip_id)
                      setFinalResult({
                        prediction: res.prediction,
                        confidence: res.confidence,
                        match_rate: res.match_rate,
                        rsrp: res.rsrp,
                        rsrq: res.rsrq,
                        neighbor_count: res.neighbor_count,
                        actual_traffic: res.actual_traffic,
                        explanation: res.explanation,
                        timestamp: res.timestamp,
                        location_name: res.location_name,
                        wander: res.wander,
                        jitter: res.jitter,
                      })
                      setProbabilities(res.probabilities)
                      setMarkers((prev) =>
                        prev.map((m) =>
                          m.location_id === res.location_id
                            ? {
                                ...m,
                                prediction: res.prediction,
                                confidence: res.confidence,
                                match_rate: res.match_rate,
                                rsrp: res.rsrp,
                                updated_at: res.timestamp,
                                pulsing: true,
                              }
                            : { ...m, pulsing: false },
                        ),
                      )
                      setPredictions((prev) =>
                        [
                          {
                            id: `${res.timestamp}-${res.location_id}`,
                            timestamp: res.timestamp,
                            location_id: res.location_id,
                            predicted_state: res.prediction,
                            confidence: res.confidence,
                            model_version: 'poc-v0.1',
                          },
                          ...prev,
                        ].slice(0, 40),
                      )
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
                <FinalPrediction result={finalResult} />
                <PredictionFeed items={predictions} />
              </div>
            </div>

            <Charts
              mode="prediction"
              matchSeries={matchSeries}
              comparison={comparison}
              probabilities={probabilities}
              accuracyHistory={accuracyHistory}
            />
          </>
        )}
      </div>
    </div>
  )
}
