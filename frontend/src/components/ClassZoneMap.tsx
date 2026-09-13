import { useEffect, useMemo, useRef, useState, type CSSProperties, type MutableRefObject } from 'react'
import { Circle, MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { stateColor, type LocationDef, type TrafficState } from '../api'
import 'leaflet/dist/leaflet.css'
import './TrafficMap.css'
import './ClassZoneMap.css'

export interface ClassZone {
  id: string
  latitude: number
  longitude: number
  label: TrafficState
  radius_m: number
}

const CLASSES: { id: TrafficState; name: string }[] = [
  { id: 'EMPTY', name: 'Empty' },
  { id: 'LOW_OCCUPANCY', name: 'Low' },
  { id: 'NORMAL', name: 'Normal' },
  { id: 'SLOW', name: 'Slow' },
  { id: 'TRAFFIC_JAM', name: 'Jam' },
]

const TUNIS_CENTER: [number, number] = [36.7992, 10.1802]
const ZONES_KEY = 'lumengrid.class-zones.v1'

function isZone(value: unknown): value is ClassZone {
  if (!value || typeof value !== 'object') return false
  const z = value as ClassZone
  return (
    typeof z.id === 'string' &&
    typeof z.latitude === 'number' &&
    typeof z.longitude === 'number' &&
    typeof z.label === 'string' &&
    typeof z.radius_m === 'number'
  )
}

export function readCachedZones(): ClassZone[] {
  try {
    const raw = localStorage.getItem(ZONES_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.filter(isZone) : []
  } catch {
    return []
  }
}

function writeCachedZones(zones: ClassZone[]) {
  try {
    localStorage.setItem(ZONES_KEY, JSON.stringify(zones))
  } catch {
    /* ignore */
  }
}

function classIcon(label: TrafficState) {
  const color = stateColor(label)
  return L.divIcon({
    className: 'lg-marker zone-marker',
    html: `<span class="lg-pin" style="--pin:${color}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

function FitZones({ zones, anchors }: { zones: ClassZone[]; anchors: LocationDef[] }) {
  const map = useMap()
  const key = useMemo(
    () => [...zones.map((z) => z.id), ...anchors.map((a) => a.id)].join('|'),
    [zones, anchors],
  )

  useEffect(() => {
    const t = window.setTimeout(() => map.invalidateSize(), 0)
    return () => window.clearTimeout(t)
  }, [map])

  useEffect(() => {
    map.invalidateSize()
    const pts: [number, number][] = [
      ...zones.map((z) => [z.latitude, z.longitude] as [number, number]),
      ...anchors.map((a) => [a.latitude, a.longitude] as [number, number]),
    ]
    if (!pts.length) {
      map.setView(TUNIS_CENTER, 16)
      return
    }
    if (pts.length === 1) {
      map.setView(pts[0], 16)
      return
    }
    map.fitBounds(L.latLngBounds(pts).pad(0.35), { maxZoom: 16, animate: false })
  }, [map, key, zones, anchors])

  return null
}

function MapClicks({
  onAdd,
  skipNext,
}: {
  onAdd: (lat: number, lon: number) => void
  skipNext: MutableRefObject<boolean>
}) {
  useMapEvents({
    click(e) {
      if (skipNext.current) {
        skipNext.current = false
        return
      }
      onAdd(e.latlng.lat, e.latlng.lng)
    },
  })
  return null
}

interface ClassZoneMapProps {
  zones: ClassZone[]
  anchors?: LocationDef[]
  onChange: (zones: ClassZone[]) => void
}

export function ClassZoneMap({ zones, anchors = [], onChange }: ClassZoneMapProps) {
  const [active, setActive] = useState<TrafficState>('NORMAL')
  const [radius, setRadius] = useState(80)
  const skipNext = useRef(false)

  function addZone(lat: number, lon: number) {
    const next: ClassZone = {
      id: `zone-${active}-${Date.now()}`,
      latitude: lat,
      longitude: lon,
      label: active,
      radius_m: radius,
    }
    const updated = [...zones, next]
    writeCachedZones(updated)
    onChange(updated)
  }

  function removeZone(id: string) {
    skipNext.current = true
    const updated = zones.filter((z) => z.id !== id)
    writeCachedZones(updated)
    onChange(updated)
  }

  function clearZones() {
    writeCachedZones([])
    onChange([])
  }

  const counts = useMemo(() => {
    const next: Record<string, number> = {}
    for (const c of CLASSES) next[c.id] = 0
    for (const z of zones) next[z.label] = (next[z.label] ?? 0) + 1
    return next
  }, [zones])

  return (
    <section className="map-panel zone-map">
      <div className="map-head">
        <div>
          <h2>Class areas</h2>
          <p>Pick a class, then click the map to drop an area. Click a pin to remove it.</p>
        </div>
        <button type="button" className="zone-clear" disabled={!zones.length} onClick={clearZones}>
          Clear areas
        </button>
      </div>

      <div className="zone-toolbar">
        <div className="zone-classes" role="radiogroup" aria-label="Occupancy class">
          {CLASSES.map((c) => (
            <button
              key={c.id}
              type="button"
              role="radio"
              aria-checked={active === c.id}
              className={active === c.id ? 'zone-chip active' : 'zone-chip'}
              style={{ '--chip': stateColor(c.id) } as CSSProperties}
              onClick={() => setActive(c.id)}
            >
              <span className="zone-swatch" />
              {c.name}
              <em>{counts[c.id]}</em>
            </button>
          ))}
        </div>
        <label className="zone-radius">
          <span>Area {radius} m</span>
          <input
            type="range"
            min={40}
            max={200}
            step={10}
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          />
        </label>
      </div>

      <div className={`map-frame zone-frame placing-${active.toLowerCase()}`}>
        <MapContainer
          center={TUNIS_CENTER}
          zoom={16}
          scrollWheelZoom
          className="leaflet-host"
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitZones zones={zones} anchors={anchors} />
          <MapClicks onAdd={addZone} skipNext={skipNext} />

          {anchors.map((a) => (
            <Circle
              key={a.id}
              center={[a.latitude, a.longitude]}
              radius={12}
              pathOptions={{ color: '#9ec5d4', weight: 1, fillColor: '#5b8fa8', fillOpacity: 0.35 }}
            />
          ))}

          {zones.map((z) => (
            <Circle
              key={`${z.id}-area`}
              center={[z.latitude, z.longitude]}
              radius={z.radius_m}
              pathOptions={{
                color: stateColor(z.label),
                weight: 1.5,
                fillColor: stateColor(z.label),
                fillOpacity: 0.18,
              }}
            />
          ))}

          {zones.map((z) => (
            <Marker
              key={z.id}
              position={[z.latitude, z.longitude]}
              icon={classIcon(z.label)}
              eventHandlers={{ click: () => removeZone(z.id) }}
              zIndexOffset={700}
            />
          ))}
        </MapContainer>
      </div>
    </section>
  )
}
