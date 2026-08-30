export type TrafficState =
  | 'EMPTY'
  | 'LOW_OCCUPANCY'
  | 'NORMAL'
  | 'SLOW'
  | 'TRAFFIC_JAM'


export interface LocationDef {
  id: string
  name: string
  latitude: number
  longitude: number
  district: string
}

export interface MapMarker {
  location_id: string
  name: string
  district: string
  latitude: number
  longitude: number
  prediction: TrafficState | string
  confidence: number
  match_rate: number | null
  updated_at: string | null
  pulsing?: boolean
}

export interface DashboardStats {
  traffic_health_pct: number
  active_anchors: number
  model_accuracy: number | null
  latest_confidence: number | null
  total_readings: number
  total_predictions: number
  markers: MapMarker[]
}

export interface TrafficPrediction {
  id: string
  timestamp: string
  location_id: string
  predicted_state: string
  confidence: number
  model_version: string
}

export interface AnchorReading {
  id: string
  timestamp: string
  anchor_id: string
  latitude: number
  longitude: number
  match_rate: number
  rsrp: number
  rsrq: number
  neighbor_count: number
  traffic_label: string
}

export interface NaCStatus {
  connected: boolean
  sandbox_mode: boolean
  api_url: string
  message: string
}

export interface RecordingRow {
  timestamp: string
  match_rate: number
  rsrp: number
  rsrq: number
  actual_traffic: string
  predicted_traffic: string
  correct: boolean
  confidence: number
}

export interface MatchRatePoint {
  t: number
  match_rate: number
}

export interface PredictionUpdate {
  type: 'prediction_update'
  location_id: string
  latitude: number
  longitude: number
  prediction: string
  confidence: number
  match_rate: number
  rsrp: number
  rsrq: number
  neighbor_count: number
  actual_traffic: string
  correct: boolean
  probabilities: Record<string, number>
  progress: number
  sample_index: number
  total_samples: number
  timestamp: string
  prediction_id?: string
  reading_id?: string
}

export type WsMessage =
  | PredictionUpdate
  | {
      type: 'simulation_started'
      location_id: string
      location_name: string
      duration_seconds: number
      speed: number
      scenario?: string
    }
  | {
      type: 'simulation_complete'
      location_id: string
      samples: number
      scenario?: string
      location_name?: string
      final_prediction?: {
        prediction: string
        confidence: number
        match_rate: number
        rsrp: number
        rsrq: number
        neighbor_count: number
        actual_traffic: string
        probabilities: Record<string, number>
        explanation: string
        timestamp: string
      }
    }
  | { type: 'error'; message: string }

const BASE = ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; sandbox_mode: boolean }>('/health'),
  nacStatus: () => request<NaCStatus>('/api/nac/status'),
  locations: () => request<LocationDef[]>('/api/locations'),
  dashboardStats: () => request<DashboardStats>('/api/dashboard/stats'),
  predictions: (limit = 40) =>
    request<TrafficPrediction[]>(`/api/predictions?limit=${limit}`),
  readings: (limit = 120) =>
    request<AnchorReading[]>(`/api/dataset/readings?limit=${limit}`),
  generateDataset: (body?: {
    num_anchors?: number
    duration_minutes?: number
    sample_interval_seconds?: number
  }) =>
    request<{ readings_created: number }>('/api/dataset/generate', {
      method: 'POST',
      body: JSON.stringify({
        num_anchors: 3,
        duration_minutes: 60,
        sample_interval_seconds: 60,
        clear_existing: true,
        ...body,
      }),
    }),
  seedDemo: (force = true) =>
    request<{
      seeded: boolean
      readings_created?: number
      model_accuracy?: number
    }>(`/api/dataset/seed-demo?force=${force}`, { method: 'POST' }),
  trainModel: () =>
    request<{ trained: boolean; accuracy: number; model_version: string; n_readings: number }>(
      '/api/ml/train',
      { method: 'POST' },
    ),
  modelStatus: () => request<{ ready: boolean; accuracy?: number; model_version?: string }>('/api/ml/status'),
  samplePredict: (body: {
    modality: 'full' | 'gps_camara' | 'cell_camara' | 'gps_cell_camara'
    scenario?: 'EMPTY' | 'LOW_OCCUPANCY' | 'NORMAL' | 'SLOW' | 'TRAFFIC_JAM'
    samples?: Array<{
      match_rate: number
      rsrp?: number
      rsrq?: number
      neighbor_count?: number
      latitude?: number
      longitude?: number
    }>
    latitude?: number
    longitude?: number
    location_name?: string
  }) =>
    request<{
      prediction: string
      confidence: number
      probabilities: Record<string, number>
      explanation: string
      modality: string
      sample_count: number
      match_rate_mean: number
      wander: number
      jitter: number
    }>('/api/ml/predict', { method: 'POST', body: JSON.stringify(body) }),
  predictAnchors: (modality: 'full' | 'gps_camara' | 'cell_camara' | 'gps_cell_camara' = 'full') =>
    request<{ markers: MapMarker[]; count: number }>(
      `/api/ml/predict-anchors?modality=${modality}`,
      { method: 'POST' },
    ),
  batchPredict: (limit = 100) =>
    request<TrafficPrediction[]>(`/api/predictions/batch?limit=${limit}`, {
      method: 'POST',
    }),
  runSimulation: (body: {
    traffic_intensity: number
    location_id: string
    time_of_day: 'morning' | 'afternoon' | 'evening' | 'night'
    speed: 1 | 5 | 10
    duration_seconds?: number
    scenario?: 'CUSTOM' | 'EMPTY' | 'LOW_OCCUPANCY' | 'NORMAL' | 'SLOW' | 'TRAFFIC_JAM'
  }) =>
    request<{ status: string }>('/api/simulation/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  simulationStatus: () => request<{ running: boolean }>('/api/simulation/status'),
  ooredooTowers: () => request<TowerLayerResponse>('/api/towers/ooredoo'),
}

export function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}

export interface TowerPoint {
  lat: number
  lon: number
  radio: string
  mcc: number
  mnc: number
  cell: number
}

export interface TowerLayerResponse {
  operator: string
  mcc: number
  mnc: number
  source: string
  attribution: string
  count: number
  total: number
  towers: TowerPoint[]
}

export function stateColor(state: string): string {
  switch (state) {
    case 'EMPTY':
      return '#7dd3c0'
    case 'LOW_OCCUPANCY':
      return '#5bb89a'
    case 'NORMAL':
      return '#3ecf8e'
    case 'SLOW':
      return '#f4c95f'
    case 'TRAFFIC_JAM':
      return '#e07a5f'
    default:
      return '#5b8fa8'
  }
}
