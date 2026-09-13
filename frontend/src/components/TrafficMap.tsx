import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.markercluster'
import { api, stateColor, type MapMarker, type TowerPoint } from '../api'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import './TrafficMap.css'

function rssiFromRsrp(rsrp: number): number {
  return Math.round(rsrp + 10 * Math.log10(12 * 50))
}

function camaraDistanceM(realM: number, matchRate: number | null | undefined, rsrp: number | null | undefined): number {
  const mr = matchRate ?? 70
  const rp = rsrp ?? -90
  const matchBias = 1 + (100 - mr) / 70
  const rsrpBias = 1 + Math.max(0, -90 - rp) / 80
  return Math.round(Math.max(25, realM * matchBias * rsrpBias))
}

function rssiAtDistance(servingRssi: number, servingM: number, targetM: number): number {
  const d0 = Math.max(servingM, 1)
  const d1 = Math.max(targetM, 1)
  return Math.round(Math.max(-120, Math.min(-40, servingRssi - 20 * Math.log10(d1 / d0))))
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`
  return `${(meters / 1000).toFixed(2)} km`
}

function radioTriplets(
  nearby: { distance_m: number }[],
  matchRate: number | null | undefined,
  rsrp: number | null | undefined,
  fallback?: { real?: number[] | null; camara?: number[] | null; rssi?: number[] | null },
) {
  const reals = nearby.length ? nearby.map((t) => t.distance_m) : fallback?.real ?? []
  if (!reals.length) {
    return { real: '—', camara: '—', rssi: '—', reals: [], camaras: [] as number[], rssis: [] as number[] }
  }
  const servingRssi = rssiFromRsrp(rsrp ?? -90)
  const camaras = reals.map((d) => camaraDistanceM(d, matchRate, rsrp))
  const rssis = reals.map((d) => rssiAtDistance(servingRssi, reals[0], d))
  return {
    real: reals.map(formatDistance).join(' · '),
    camara: camaras.map(formatDistance).join(' · '),
    rssi: `${rssis.join(' · ')} dBm`,
    reals,
    camaras,
    rssis,
  }
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function markerIcon(
  state: string,
  pulsing: boolean,
  side: 'left' | 'right',
  card: { name: string; real: string; camara: string; rssi: string },
) {
  const color = stateColor(state)
  return L.divIcon({
    className: `lg-marker tip-${side}`,
    html: `<span class="lg-pin ${pulsing ? 'pulse' : ''}" style="--pin:${color}"></span>
      <div class="lg-metrics">
        <strong>${escapeHtml(card.name)}</strong>
        <span>Real ${escapeHtml(card.real)}</span>
        <span>CAMARA ${escapeHtml(card.camara)}</span>
        <span>RSSI ${escapeHtml(card.rssi)}</span>
      </div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

const TUNIS_CENTER: [number, number] = [36.7992, 10.1802]
const TUNIS_ZOOM = 16

function FitAnchors({ markers }: { markers: MapMarker[] }) {
  const map = useMap()
  const fittedKey = useMemo(
    () => markers.map((m) => m.location_id).sort().join('|'),
    [markers],
  )

  useEffect(() => {
    const frame = map.getContainer().parentElement
    const sync = () => map.invalidateSize()
    const t = window.setTimeout(sync, 0)
    window.addEventListener('resize', sync)
    const ro = frame ? new ResizeObserver(sync) : null
    if (frame && ro) ro.observe(frame)
    return () => {
      window.clearTimeout(t)
      window.removeEventListener('resize', sync)
      ro?.disconnect()
    }
  }, [map])

  useEffect(() => {
    map.invalidateSize()
    if (!markers.length) {
      map.setView(TUNIS_CENTER, TUNIS_ZOOM)
      return
    }
    if (markers.length === 1) {
      map.setView([markers[0].latitude, markers[0].longitude], 16)
      return
    }
    const bounds = L.latLngBounds(markers.map((m) => [m.latitude, m.longitude]))
    map.fitBounds(bounds.pad(0.45), { maxZoom: 16, animate: false })
  }, [map, fittedKey, markers])

  return null
}

const EARTH_M = 6_371_000

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_M * Math.asin(Math.min(1, Math.sqrt(a)))
}

const OPERATOR_LABEL: Record<number, string> = {
  1: 'Orange Tunisia',
  2: 'Tunisie Telecom',
  3: 'Ooredoo Tunisia',
}

interface NearbyTower extends TowerPoint {
  distance_m: number
}

function nearestTowers(lat: number, lon: number, towers: TowerPoint[], n = 3): NearbyTower[] {
  if (towers.length === 0) return []
  const ranked = towers
    .map((t) => ({ ...t, distance_m: haversineMeters(lat, lon, t.lat, t.lon) }))
    .sort((a, b) => a.distance_m - b.distance_m)
  const unique: NearbyTower[] = []
  const seenSites = new Set<string>()
  for (const tower of ranked) {
    const site = `${tower.lat.toFixed(4)},${tower.lon.toFixed(4)}`
    if (seenSites.has(site)) continue
    seenSites.add(site)
    unique.push(tower)
    if (unique.length === n) break
  }
  return unique
}

function towerLabel(t: NearbyTower): string {
  return OPERATOR_LABEL[t.mnc] ?? t.operator ?? `MNC ${t.mnc}`
}

function createTowerLayer(): L.LayerGroup {
  const factory = (L as unknown as { markerClusterGroup?: (o?: object) => L.LayerGroup }).markerClusterGroup
  if (typeof factory === 'function') {
    return factory({
      chunkedLoading: true,
      chunkInterval: 100,
      chunkDelay: 20,
      maxClusterRadius: 55,
      spiderfyOnMaxZoom: false,
      disableClusteringAtZoom: 16,
      showCoverageOnHover: false,
    })
  }
  return L.layerGroup()
}

/** OpenCelliD Greater Tunis cells — canvas dots, clustered when the plugin is present. */
function OoredooTowerLayer({ towers, visible }: { towers: TowerPoint[]; visible: boolean }) {
  const map = useMap()

  useEffect(() => {
    if (!visible || towers.length === 0) return

    const layer = createTowerLayer()
    const renderer = L.canvas({ padding: 0.4 })
    let i = 0
    let cancelled = false

    const addBatch = () => {
      if (cancelled) return
      const end = Math.min(i + 1500, towers.length)
      for (; i < end; i++) {
        const t = towers[i]
        const m = L.circleMarker([t.lat, t.lon], {
          renderer,
          radius: 6,
          color: '#9ec5d4',
          weight: 1,
          fillColor: '#5b8fa8',
          fillOpacity: 0.9,
        })
        m.bindPopup(
          `<strong>${OPERATOR_LABEL[t.mnc] ?? `MNC ${t.mnc}`}</strong> · ${t.radio}<br/>MCC ${t.mcc} / MNC ${t.mnc}<br/>Cell ${t.cell}`,
        )
        layer.addLayer(m)
      }
      if (i < towers.length) {
        window.setTimeout(addBatch, 0)
      }
    }

    map.addLayer(layer)
    addBatch()

    return () => {
      cancelled = true
      map.removeLayer(layer)
    }
  }, [map, towers, visible])

  return null
}

interface TrafficMapProps {
  markers: MapMarker[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function TrafficMap({ markers, selectedId, onSelect }: TrafficMapProps) {
  const [showTowers, setShowTowers] = useState(true)
  const [towers, setTowers] = useState<TowerPoint[]>([])
  const [towerMeta, setTowerMeta] = useState<{ count: number; source: string; attribution: string }>({
    count: 0,
    source: '',
    attribution: '',
  })

  useEffect(() => {
    let cancelled = false
    const load = async (attempt = 1) => {
      try {
        const data = await api.ooredooTowers()
        if (cancelled) return
        const ooredoo = (data.towers ?? []).filter((t) => t.mnc === 3)
        setTowers(ooredoo)
        setTowerMeta({
          count: ooredoo.length,
          source: data.source,
          attribution: data.attribution,
        })
      } catch {
        if (!cancelled && attempt < 5) {
          window.setTimeout(() => void load(attempt + 1), 800 * attempt)
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const nearbyByAnchor = useMemo(() => {
    const next: Record<string, NearbyTower[]> = {}
    for (const m of markers) {
      next[m.location_id] = nearestTowers(m.latitude, m.longitude, towers, 3)
    }
    return next
  }, [markers, towers])

  const selected = useMemo(
    () => markers.find((m) => m.location_id === selectedId) ?? null,
    [markers, selectedId],
  )
  const selectedNearby = selected ? nearbyByAnchor[selected.location_id] ?? [] : []
  const selectedRadio = selected
    ? radioTriplets(selectedNearby, selected.match_rate, selected.rsrp, {
        real: selected.real_distance_m,
        camara: selected.camara_distance_m,
        rssi: selected.rssi_dbm,
      })
    : null

  return (
    <section className="map-panel">
      <div className="map-head">
        <div>
          <h2>Traffic map</h2>
          <p>
            LumenGrid anchors on the Ooredoo Tunisia radio grid (OpenCelliD, MCC 605 / MNC 03)
            {towerMeta.count
              ? ` · ${towerMeta.count.toLocaleString()} cells`
              : ' · loading cells…'}
            .
          </p>
        </div>
        <label className="tower-toggle">
          <input
            type="checkbox"
            checked={showTowers}
            onChange={(e) => setShowTowers(e.target.checked)}
          />
          Show Ooredoo towers
        </label>
      </div>
      <div className="map-frame">
        <MapContainer
          key="tunis-opencellid-map"
          center={TUNIS_CENTER}
          zoom={TUNIS_ZOOM}
          scrollWheelZoom
          className="leaflet-host"
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitAnchors markers={markers} />
          <OoredooTowerLayer towers={towers} visible={showTowers} />

          {markers.flatMap((m) =>
            (nearbyByAnchor[m.location_id] ?? []).map((t) => (
              <Polyline
                key={`${m.location_id}-${t.mnc}-${t.cell}-${t.lat}-${t.lon}`}
                positions={[
                  [m.latitude, m.longitude],
                  [t.lat, t.lon],
                ]}
                pathOptions={{
                  color: m.location_id === selectedId ? '#9ec5d4' : '#5b8fa8',
                  weight: m.location_id === selectedId ? 2 : 1.25,
                  dashArray: '6 5',
                  opacity: m.location_id === selectedId ? 0.9 : 0.45,
                }}
              />
            )),
          )}

          {markers.map((m, index) => {
            const nearby = nearbyByAnchor[m.location_id] ?? []
            const radio = radioTriplets(nearby, m.match_rate, m.rsrp, {
              real: m.real_distance_m,
              camara: m.camara_distance_m,
              rssi: m.rssi_dbm,
            })
            const tipRight = index % 2 === 0
            return (
            <Marker
              key={m.location_id}
              position={[m.latitude, m.longitude]}
              icon={markerIcon(
                m.prediction,
                !!m.pulsing || m.location_id === selectedId,
                tipRight ? 'right' : 'left',
                { name: m.name, real: radio.real, camara: radio.camara, rssi: radio.rssi },
              )}
              eventHandlers={{ click: () => onSelect(m.location_id) }}
              zIndexOffset={800}
            >
              <Popup>
                <strong>{m.name}</strong>
                <br />
                {m.district}
                <br />
                State: {m.prediction.replace('_', ' ')}
                <br />
                Confidence: {(m.confidence * 100).toFixed(0)}%
                {m.match_rate != null && (
                  <>
                    <br />
                    Match rate: {m.match_rate}%
                  </>
                )}
                <br />
                Real: {radio.real}
                <br />
                CAMARA: {radio.camara}
                <br />
                RSSI: {radio.rssi}
                {nearby.length > 0 && (
                  <>
                    <br />
                    <br />
                    <strong>Nearest towers</strong>
                    <ol className="nearby-towers">
                      {nearby.map((t, i) => (
                        <li key={`${t.radio}-${t.mnc}-${t.cell}`}>
                          {towerLabel(t)} {t.radio} · real {formatDistance(radio.reals[i] ?? t.distance_m)}
                          {radio.camaras[i] != null && <> · CAMARA {formatDistance(radio.camaras[i])}</>}
                          {radio.rssis[i] != null && <> · RSSI {radio.rssis[i]} dBm</>}
                        </li>
                      ))}
                    </ol>
                  </>
                )}
              </Popup>
            </Marker>
            )
          })}
        </MapContainer>
        <aside className="map-legend" aria-label="Legend">
          <div>
            <span className="swatch" style={{ background: '#5b8fa8' }} /> Ooredoo (605/03)
          </div>
          <div>
            <span className="swatch" style={{ background: '#7dd3c0' }} /> EMPTY
          </div>
          <div>
            <span className="swatch" style={{ background: '#5bb89a' }} /> LOW OCCUPANCY
          </div>
          <div>
            <span className="swatch" style={{ background: '#3ecf8e' }} /> NORMAL
          </div>
          <div>
            <span className="swatch" style={{ background: '#f4c95f' }} /> SLOW
          </div>
          <div>
            <span className="swatch" style={{ background: '#e07a5f' }} /> TRAFFIC JAM
          </div>
        </aside>
      </div>
      {towerMeta.attribution && <p className="tower-attr">{towerMeta.attribution}</p>}
      {selected && (
        <div className="map-detail">
          <h3>{selected.name}</h3>
          <p>
            {selected.prediction.replace('_', ' ')} · {(selected.confidence * 100).toFixed(0)}%
            confidence
            {selected.match_rate != null ? ` · match ${selected.match_rate}%` : ''}
          </p>
          {selectedRadio && (
            <p>
              Real {selectedRadio.real} · CAMARA {selectedRadio.camara} · RSSI {selectedRadio.rssi}
            </p>
          )}
          {selectedNearby.length > 0 && selectedRadio && (
            <ol className="nearby-towers">
              {selectedNearby.map((t, i) => (
                <li key={`${t.radio}-${t.mnc}-${t.cell}`}>
                  {towerLabel(t)} {t.radio} · real {formatDistance(t.distance_m)}
                  {selectedRadio.camaras[i] != null && <> · CAMARA {formatDistance(selectedRadio.camaras[i])}</>}
                  {selectedRadio.rssis[i] != null && <> · RSSI {selectedRadio.rssis[i]} dBm</>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  )
}
