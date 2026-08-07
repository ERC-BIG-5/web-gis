<script setup>
import { onMounted, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import Spiderfy from '@nazka/map-gl-js-spiderfy'

const props = defineProps({
  style: {
    type: [String, Object],
    default: 'https://tiles.openfreemap.org/styles/liberty',
  },
  center: {
    type: Array,
    default: () => [0, 20],
  },
  zoom: {
    type: Number,
    default: 1.5,
  },
  points: {
    type: Object,
    default: null,
  },
  cluster: {
    type: Boolean,
    default: true,
  },
  clusterLayout: {
    type: String,
    default: 'grid', // 'grid' | 'spiral'
    validator: (v) => ['grid', 'spiral'].includes(v),
  },
  // optional secondary layer of already-validated posts (workshop mode)
  done: {
    type: Object,
    default: null,
  },
  showDone: {
    type: Boolean,
    default: true,
  },
  // draw a bright ring under each point so the current post is always
  // visible even when its image/thumbnail is missing (workshop mode)
  highlightCurrent: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['point-click', 'cluster-list'])

const container = ref(null)
const map = shallowRef(null)
const spiderfy = shallowRef(null)
const SOURCE_ID = 'points'

function setupPoints(m, data) {
  m.addSource(SOURCE_ID, {
    type: 'geojson',
    data,
    cluster: props.cluster,
    clusterMaxZoom: 22,
    clusterRadius: 50,
  })

  addFallbackMarker(m)
  if (props.cluster) {
    addClusterIcons(m)

    m.addLayer({
      id: 'clusters',
      type: 'symbol',
      source: SOURCE_ID,
      filter: ['has', 'point_count'],
      layout: {
        'icon-image': [
          'step',
          ['to-number', ['get', 'point_count']],
          'cluster-sm', 10,
          'cluster-md', 30,
          'cluster-lg',
        ],
        'icon-allow-overlap': true,
        'icon-anchor': 'center',
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': ['Noto Sans Bold'],
        'text-size': 12,
        'text-allow-overlap': true,
      },
    })

    m.on('mouseenter', 'clusters', () => (m.getCanvas().style.cursor = 'pointer'))
    m.on('mouseleave', 'clusters', () => (m.getCanvas().style.cursor = ''))

    const useGrid = props.clusterLayout === 'grid'
    spiderfy.value = new Spiderfy(m, {
      onLeafClick: (feature, event) =>
        emit('point-click', { feature, map: m, lngLat: event.lngLat }),
      closeOnLeafClick: false,
      circleSpiralSwitchover: useGrid ? Infinity : 12,
      circleOptions: {
        leavesSeparation: ICON_SIZE * 2,
      },
      spiralOptions: {
        legLengthStart: ICON_SIZE * 1.5,
        legLengthFactor: 5,
        leavesSeparation: ICON_SIZE * 2.4,
      },
      spiderLegsAreHidden: useGrid,
      spiderLeavesLayout: {
        'icon-image': ['get', 'image_name'],
        'icon-size': 1,
        'icon-allow-overlap': true,
        'icon-anchor': 'center',
      },
    })
    spiderfy.value.applyTo('clusters')

    if (useGrid) {
      spiderfy.value._calculatePointsInCircle = (n) => calculatePointsInGrid(n, ICON_SIZE + 8)
    }

    const origSpiderfy = spiderfy.value.spiderfy.bind(spiderfy.value)
    spiderfy.value.spiderfy = function (layerId, clusterId) {
      const cluster = m
        .querySourceFeatures(SOURCE_ID)
        .find((f) => f.properties?.cluster_id === clusterId)
      const pc = cluster?.properties?.point_count ?? 0
      if (pc > 50) {
        const c = cluster?.geometry?.coordinates
        const z = Math.min(m.getMaxZoom(), m.getZoom() + 2)
        if (c) m.jumpTo({ center: c, zoom: z })
        return
      }
      return origSpiderfy(layerId, clusterId)
    }

    const origDraw = spiderfy.value._drawFeaturesOnMap.bind(spiderfy.value)
    spiderfy.value._drawFeaturesOnMap = function (...args) {
      origDraw(...args)
      setBackgroundDim(m, true)
    }
    const origClear = spiderfy.value._clearSpiderifiedCluster.bind(spiderfy.value)
    spiderfy.value._clearSpiderifiedCluster = function (...args) {
      origClear(...args)
      setBackgroundDim(m, false)
    }
  }

  if (props.highlightCurrent) {
    m.addLayer({
      id: 'current-highlight',
      type: 'circle',
      source: SOURCE_ID,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': 26,
        'circle-color': '#f59e0b',
        'circle-opacity': 0.35,
        'circle-stroke-color': '#d97706',
        'circle-stroke-width': 3,
      },
    })
  }

  m.addLayer({
    id: 'unclustered-point',
    type: 'symbol',
    source: SOURCE_ID,
    filter: ['!', ['has', 'point_count']],
    layout: {
      'icon-image': ['get', 'image_name'],
      'icon-size': 1,
      'icon-allow-overlap': true,
      'icon-anchor': 'center',
      'text-field': ['coalesce', ['get', 'ces_short'], ''],
      'text-font': ['Noto Sans Bold'],
      'text-size': 14,
      'text-anchor': 'top',
      'text-offset': [0, 2.4],
      'text-allow-overlap': true,
      'text-letter-spacing': 0.05,
    },
    paint: {
      'text-color': '#111',
      'text-halo-color': '#fff',
      'text-halo-width': 2,
    },
  })

  m.on('click', 'unclustered-point', (e) => {
    emit('point-click', { feature: e.features[0], map: m, lngLat: e.lngLat })
  })
  m.on('mouseenter', 'unclustered-point', () => (m.getCanvas().style.cursor = 'pointer'))
  m.on('mouseleave', 'unclustered-point', () => (m.getCanvas().style.cursor = ''))
}

function makeClusterIcon(color, size) {
  const canvas = new OffscreenCanvas(size, size)
  const ctx = canvas.getContext('2d')
  ctx.beginPath()
  ctx.arc(size / 2, size / 2, size / 2 - 2, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = '#fff'
  ctx.stroke()
  return ctx.getImageData(0, 0, size, size)
}

function addClusterIcons(m) {
  if (!m.hasImage('cluster-sm')) m.addImage('cluster-sm', makeClusterIcon('#51bbd6', 32))
  if (!m.hasImage('cluster-md')) m.addImage('cluster-md', makeClusterIcon('#f1f075', 44))
  if (!m.hasImage('cluster-lg')) m.addImage('cluster-lg', makeClusterIcon('#f28cb1', 56))
}

function addFallbackMarker(m) {
  if (m.hasImage('fallback-marker')) return
  m.addImage('fallback-marker', makeClusterIcon('#888', 32))
}

function calculatePointsInGrid(n, cellSize) {
  const cols = Math.ceil(Math.sqrt(n))
  const rows = Math.ceil(n / cols)
  const points = []
  for (let i = 0; i < n; i += 1) {
    const col = i % cols
    const row = Math.floor(i / cols)
    points.push([(col - (cols - 1) / 2) * cellSize, (row - (rows - 1) / 2) * cellSize])
  }
  return points
}

function setBackgroundDim(m, dim) {
  const op = dim ? 0.2 : 1
  for (const id of ['clusters', 'unclustered-point']) {
    if (!m.getLayer(id)) continue
    m.setPaintProperty(id, 'icon-opacity', op)
    m.setPaintProperty(id, 'text-opacity', op)
  }
}

const ICON_SIZE = 60

async function loadIconImage(m, name, baseUrl) {
  if (m.hasImage(name)) return
  const res = await fetch(`${baseUrl}/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  const bmp = await createImageBitmap(blob, {
    resizeWidth: ICON_SIZE,
    resizeHeight: ICON_SIZE,
    resizeQuality: 'high',
  })
  const canvas = new OffscreenCanvas(ICON_SIZE, ICON_SIZE)
  const ctx = canvas.getContext('2d')
  ctx.drawImage(bmp, 0, 0)
  m.addImage(name, ctx.getImageData(0, 0, ICON_SIZE, ICON_SIZE))
}

const pendingImages = new Set()

function registerImageHandler(m, getBaseUrl) {
  if (m._imageHandlerRegistered) return
  m._imageHandlerRegistered = true
  m.on('styleimagemissing', async (e) => {
    const id = e.id
    if (!id || m.hasImage(id) || pendingImages.has(id)) return
    if (id === 'fallback-marker' || id.startsWith('cluster-')) return
    pendingImages.add(id)
    try {
      const base = getBaseUrl()
      if (!base) throw new Error('no media base')
      await loadIconImage(m, id, base)
    } catch {
      if (!m.hasImage(id)) m.addImage(id, makeClusterIcon('#888', 32))
    } finally {
      pendingImages.delete(id)
    }
  })
}

async function applyPoints(data) {
  const m = map.value
  if (!m || !data) return
  registerImageHandler(m, () => {
    const base = props.points?.base_media_path
    return base ? `/images/${base}/thumb` : null
  })
  const src = m.getSource(SOURCE_ID)
  if (src) {
    // updating an existing source is always safe, even mid-render
    src.setData(data)
    return
  }
  if (!m.isStyleLoaded()) {
    // only initial layer creation must wait; 'idle' fires repeatedly,
    // unlike 'load' which fires exactly once per map lifetime
    m.once('idle', () => applyPoints(data))
    return
  }
  setupPoints(m, data)
}

const DONE_SOURCE = 'done-points'
const DONE_LAYER = 'done-points-layer'

function applyDone(data) {
  const m = map.value
  if (!m || !data) return
  const src = m.getSource(DONE_SOURCE)
  if (src) {
    src.setData(data)
    return
  }
  if (!m.isStyleLoaded()) {
    m.once('idle', () => applyDone(data))
    return
  }
  m.addSource(DONE_SOURCE, { type: 'geojson', data })
    m.addLayer({
      id: DONE_LAYER,
      type: 'circle',
      source: DONE_SOURCE,
      paint: {
        'circle-radius': 6,
        'circle-color': '#9ca3af',
        'circle-opacity': 0.75,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    })
    syncDoneVisibility()
}

function syncDoneVisibility() {
  const m = map.value
  if (!m || !m.getLayer(DONE_LAYER)) return
  m.setLayoutProperty(DONE_LAYER, 'visibility', props.showDone ? 'visible' : 'none')
}

watch(() => props.done, applyDone)
watch(() => props.showDone, syncDoneVisibility)

function fit(fc) {
  const m = map.value
  if (!m || !fc?.features?.length) return
  const bounds = new maplibregl.LngLatBounds()
  for (const f of fc.features) {
    if (f.geometry?.type === 'Point') bounds.extend(f.geometry.coordinates)
  }
  if (!bounds.isEmpty()) {
    const cam = m.cameraForBounds(bounds, { padding: 80, maxZoom: 11 })
    if (cam) m.jumpTo(cam)
  }
}

onMounted(() => {
  map.value = new maplibregl.Map({
    container: container.value,
    style: props.style,
    center: props.center,
    zoom: props.zoom,
  })
  map.value.easeTo = map.value.jumpTo.bind(map.value)
  map.value.on('load', () => {
    if (props.points) applyPoints(props.points)
    if (props.done) applyDone(props.done)
  })
})

watch(() => props.points, applyPoints)
watch(
  () => [props.center, props.zoom],
  ([c, z]) => {
    const m = map.value
    if (!m) return
    m.jumpTo({ center: c, zoom: z })
  },
  { deep: true },
)

onBeforeUnmount(() => {
  map.value?.remove()
})

defineExpose({ map, fit })
</script>

<template>
  <div class="map-root">
    <div ref="container" class="map-canvas"></div>
    <div class="map-overlays">
      <slot :map="map" />
    </div>
  </div>
</template>

<style scoped>
.map-root {
  position: relative;
  width: 100%;
  height: 100%;
}
.map-canvas {
  position: absolute;
  inset: 0;
}
.map-overlays {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.map-overlays > :deep(*) {
  pointer-events: auto;
}
</style>