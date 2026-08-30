import 'leaflet'

declare module 'leaflet' {
  function markerClusterGroup(options?: Record<string, unknown>): LayerGroup
}

declare module 'leaflet.markercluster'
