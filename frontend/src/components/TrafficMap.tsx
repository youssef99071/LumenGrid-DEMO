import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.markercluster'
import { api, stateColor, type MapMarker, type TowerPoint } from '../api'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import './TrafficMap.css'

function markerIcon(state: string, pulsing: boolean) {
  const color = stateColor(state)
  return L.divIcon({
    className: 'lg-marker',
    html: `<span class="lg-pin ${pulsing ? 'pulse' : ''}" style="--pin:${color}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

function FitTunis({ markers }: { markers: MapMarker[] }) {
  const map = useMap()
  useEffect(() => {
    if (!markers.length) {
      map.setView([36.83, 10.22], 11)
      return
    }
    const bounds = L.latLngBounds(markers.map((m) => [m.latitude, m.longitude]))
    map.fitBounds(bounds.pad(0.35))
  }, [map, markers])
  return null
}

/** Imperative MarkerCluster layer for ~45k Ooredoo sites (canvas-friendly). */
function OoredooTowerLayer({ towers, visible }: { towers: TowerPoint[]; visible: boolean }) {
  const map = useMap()

  useEffect(() => {
    if (!visible || towers.length === 0) return

    const cluster = (L as unknown as { markerClusterGroup: (o?: object) => L.LayerGroup }).markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 100,
      chunkDelay: 20,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: false,
      disableClusteringAtZoom: 16,
      showCoverageOnHover: false,
    })

    const icon = L.divIcon({
      className: 'tower-dot',
      html: '<span class="tower-pin"></span>',
      iconSize: [8, 8],
      iconAnchor: [4, 4],
    })

    const batch = 2000
    let i = 0
    let cancelled = false

    const addBatch = () => {
      if (cancelled) return
      const end = Math.min(i + batch, towers.length)
      for (; i < end; i++) {
        const t = towers[i]
        const m = L.marker([t.lat, t.lon], { icon })
        m.bindPopup(
          `<strong>Ooredoo</strong> · ${t.radio}<br/>MCC ${t.mcc} / MNC ${t.mnc}<br/>Cell ${t.cell}`,
        )
        cluster.addLayer(m)
      }
      if (i < towers.length) {
        window.setTimeout(addBatch, 0)
      }
    }

    map.addLayer(cluster)
    addBatch()

    return () => {
      cancelled = true
      map.removeLayer(cluster)
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
    void (async () => {
      try {
        const data = await api.ooredooTowers()
        setTowers(data.towers)
        setTowerMeta({
          count: data.count,
          source: data.source,
          attribution: data.attribution,
        })
      } catch {
        /* optional layer */
      }
    })()
  }, [])

  const selected = useMemo(
    () => markers.find((m) => m.location_id === selectedId) ?? null,
    [markers, selectedId],
  )

  return (
    <section className="map-panel">
      <div className="map-head">
        <div>
          <h2>Live Traffic Intelligence</h2>
          <p>
            Real-time AI monitoring across Greater Tunis — powered by 5G signal analysis
            {towerMeta.count ? ` · ${towerMeta.count.toLocaleString()} cell towers in range` : ''}
          </p>
        </div>
        <label className="tower-toggle">
          <input
            type="checkbox"
            checked={showTowers}
            onChange={(e) => setShowTowers(e.target.checked)}
          />
          Show 5G cell network
        </label>
      </div>
      <div className="map-frame">
        <MapContainer
          center={[36.83, 10.22]}
          zoom={11}
          scrollWheelZoom
          className="leaflet-host"
          preferCanvas
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitTunis markers={markers} />
          <OoredooTowerLayer towers={towers} visible={showTowers} />

          {markers.map((m) => (
            <Marker
              key={m.location_id}
              position={[m.latitude, m.longitude]}
              icon={markerIcon(m.prediction, !!m.pulsing || m.location_id === selectedId)}
              eventHandlers={{ click: () => onSelect(m.location_id) }}
              zIndexOffset={800}
            >
              <Popup>
                <strong>{m.name}</strong>
                <br />
                {m.district}
                <br />
                Status: <strong>{m.prediction.replace('_', ' ')}</strong>
                <br />
                AI confidence: {(m.confidence * 100).toFixed(0)}%
                {m.match_rate != null && (
                  <>
                    <br />
                    Signal strength: {m.match_rate}%
                  </>
                )}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
        <aside className="map-legend" aria-label="Legend">
          <div>
            <span className="swatch" style={{ background: '#5b8fa8' }} /> 5G cell towers
          </div>
          <div>
            <span className="swatch" style={{ background: '#7dd3c0' }} /> Empty
          </div>
          <div>
            <span className="swatch" style={{ background: '#5bb89a' }} /> Light traffic
          </div>
          <div>
            <span className="swatch" style={{ background: '#3ecf8e' }} /> Normal flow
          </div>
          <div>
            <span className="swatch" style={{ background: '#f4c95f' }} /> Slow
          </div>
          <div>
            <span className="swatch" style={{ background: '#e07a5f' }} /> Traffic jam
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
            {selected.match_rate != null ? ` · signal ${selected.match_rate}%` : ''}
          </p>
        </div>
      )}
    </section>
  )
}

