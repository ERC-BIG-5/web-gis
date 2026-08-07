<script setup>
import { computed, createApp, h, nextTick, onMounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import MapView from './components/MapView.vue'
import CesEvaluator from './components/CesEvaluator.vue'
import LoginScreen from './components/LoginScreen.vue'
import ValidationPanel from './components/ValidationPanel.vue'
import FacilitatorView from './components/FacilitatorView.vue'

// ---- workshop mode state --------------------------------------------------
const mode = ref('login') // 'login' | 'validate' | 'browse' | 'facilitator'
const session = ref(null)
const valMapRef = ref(null)
const currentFC = ref(null) // FeatureCollection with only the current post
const doneFC = ref({ type: 'FeatureCollection', features: [] })
const showDone = ref(true)

const SESSION_KEY = 'workshopSession'

function onStart(ses) {
  session.value = ses
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ case_study: ses.case_study, participant: ses.participant }),
  )
  currentFC.value = null
  doneFC.value = { type: 'FeatureCollection', features: [] }
  mode.value = 'validate'
  loadDoneLayer(ses.session_id)
}

async function loadDoneLayer(sessionId) {
  try {
    const res = await fetch(`/session/${sessionId}/done`)
    if (res.ok) doneFC.value = await res.json()
  } catch {
    /* non-fatal */
  }
}

function onCurrent(payload) {
  currentFC.value = {
    type: 'FeatureCollection',
    base_media_path: payload.base_media_path,
    features: [payload.feature],
  }
  const coords = payload.feature?.geometry?.coordinates
  const m = valMapRef.value?.map
  if (m && coords) {
    m.jumpTo({ center: coords, zoom: Math.max(m.getZoom(), 14) })
  }
}

function onValidated({ feature, feature_id, status }) {
  doneFC.value = {
    type: 'FeatureCollection',
    features: [
      ...doneFC.value.features,
      {
        type: 'Feature',
        geometry: feature.geometry,
        properties: { id: feature_id, status },
      },
    ],
  }
}

function logout() {
  sessionStorage.removeItem(SESSION_KEY)
  session.value = null
  currentFC.value = null
  mode.value = 'login'
}

function enterBrowse() {
  mode.value = 'browse'
  if (!locations.value.length) initBrowse()
}

async function tryResume() {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return false
  try {
    const { case_study, participant } = JSON.parse(raw)
    const res = await fetch('/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_study, participant }),
    })
    if (!res.ok) throw new Error()
    onStart(await res.json())
    return true
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    return false
  }
}

// ---- browse mode (original app) -------------------------------------------
const locations = ref([])
const selected = ref('')
const rawPoints = ref(null)
const enabledFilters = ref({}) // field -> Set<key> for categorical, boolean for boolean filter
const loading = ref(false)
const error = ref('')
const mapRef = ref(null)

const classification = computed(() => rawPoints.value?.classification ?? null)
const popupFields = computed(() => rawPoints.value?.popup_fields ?? null)
const evaluatorConfig = computed(() => rawPoints.value?.evaluator ?? null)

const snackbar = ref(null) // { message, kind } | null
let snackbarTimer = null
function showSnackbar(message, kind = 'info', timeout = 3000) {
  snackbar.value = { message, kind }
  if (snackbarTimer) clearTimeout(snackbarTimer)
  snackbarTimer = setTimeout(() => { snackbar.value = null }, timeout)
}

function groupedValues(filter) {
  if (!filter.values) return null
  const groups = new Map()
  for (const v of filter.values) {
    const g = v.group ?? ''
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g).push(v)
  }
  return Array.from(groups, ([label, values]) => ({ label, values }))
}

watch(rawPoints, (data) => {
  const cls = data?.classification
  if (!cls?.filters?.length) {
    enabledFilters.value = {}
    return
  }
  const next = {}
  for (const f of cls.filters) {
    if (f.values) {
      const def = f.default
      let keys
      if (def === 'all' || def == null) keys = f.values.map((v) => v.key)
      else if (def === 'none') keys = []
      else if (Array.isArray(def)) keys = def
      else keys = f.values.map((v) => v.key)
      next[f.field] = new Set(keys)
    } else {
      next[f.field] = f.default === true
    }
  }
  enabledFilters.value = next
})

function passesFilter(props, flt) {
  const enabled = enabledFilters.value[flt.field]
  const val = props?.[flt.field]
  if (flt.values) {
    if (Array.isArray(val)) return val.some((v) => enabled.has(v))
    return enabled.has(val)
  }
  if (!enabled) return true // boolean filter inactive → no constraint
  return val === true
}

const filteredPoints = computed(() => {
  if (!rawPoints.value) return null
  const filters = classification.value?.filters ?? []
  if (!filters.length) return rawPoints.value
  return {
    ...rawPoints.value,
    features: rawPoints.value.features.filter((f) =>
      filters.every((flt) => passesFilter(f.properties, flt)),
    ),
  }
})

async function initBrowse() {
  try {
    const res = await fetch('/locations')
    locations.value = await res.json()
    selected.value = locations.value.includes('the_hague')
      ? 'the_hague'
      : (locations.value[0] ?? '')
    if (selected.value) load()
  } catch (e) {
    error.value = `failed to fetch locations: ${e.message}`
  }
}

function syncHash() {
  if (window.location.hash === '#facilitator') {
    mode.value = 'facilitator'
  }
}

function exitFacilitator() {
  if (window.location.hash === '#facilitator') {
    history.replaceState(null, '', window.location.pathname)
  }
  mode.value = 'login'
}

onMounted(async () => {
  window.addEventListener('hashchange', syncHash)
  if (window.location.hash === '#facilitator') {
    mode.value = 'facilitator'
    return
  }
  const resumed = await tryResume()
  if (!resumed) mode.value = 'login'
})

async function load() {
  if (!selected.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/geo-dataset?location=${encodeURIComponent(selected.value)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    rawPoints.value = await res.json()
    await nextTick()
    mapRef.value?.fit(rawPoints.value)
  } catch (e) {
    error.value = `failed to load: ${e.message}`
  } finally {
    loading.value = false
  }
}

function toggleCategory(field, key) {
  const s = new Set(enabledFilters.value[field])
  if (s.has(key)) s.delete(key)
  else s.add(key)
  enabledFilters.value = { ...enabledFilters.value, [field]: s }
}

function setAllForFilter(flt, value) {
  if (!flt.values) return
  enabledFilters.value = {
    ...enabledFilters.value,
    [flt.field]: new Set(value ? flt.values.map((v) => v.key) : []),
  }
}

function toggleBoolean(field) {
  enabledFilters.value = {
    ...enabledFilters.value,
    [field]: !enabledFilters.value[field],
  }
}

function formatVal(v) {
  if (v === true) return '✓'
  if (v === false) return '✗'
  if (v == null) return ''
  if (Array.isArray(v)) {
    if (!v.length) return ''
    return v.map((x) => (typeof x === 'string' ? x.replace(/_/g, ' ') : String(x))).join(', ')
  }
  if (typeof v === 'string') return v.replace(/_/g, ' ')
  return String(v)
}

function onPointClick({ feature, map, lngLat }) {
  const props = feature.properties ?? {}
  const id = props.id ?? feature.id ?? ''
  const imageName = props.image_name ?? ''
  const base = rawPoints.value?.base_media_path
  const scaledUrl = base && imageName
    ? `/scaled?base=${encodeURIComponent(base)}&name=${encodeURIComponent(imageName)}`
    : ''

  const fields = popupFields.value ?? [{ field: 'name' }, { field: 'ces' }]

  const root = document.createElement('div')
  if (scaledUrl) {
    const img = document.createElement('img')
    img.className = 'point-popup-img'
    img.alt = ''
    img.src = scaledUrl
    root.appendChild(img)
  }
  for (const f of fields) {
    const val = props[f.field]
    const row = document.createElement('div')
    row.className = 'point-popup-row'
    if (f.label) {
      const lbl = document.createElement('span')
      lbl.className = 'point-popup-label'
      lbl.textContent = f.label + ':'
      row.appendChild(lbl)
      row.appendChild(document.createTextNode(' '))
    }
    const formatted = formatVal(val)
    const val_el = document.createElement('span')
    val_el.className = formatted ? 'point-popup-val' : 'point-popup-val empty'
    val_el.textContent = formatted || '—'
    row.appendChild(val_el)
    root.appendChild(row)
  }
  const evalContainer = document.createElement('div')
  root.appendChild(evalContainer)
  let evalApp = null
  let evalState = {}

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'point-popup-eval'
  btn.textContent = 'Evaluate'
  function closeEvaluator() {
    if (!evalApp) return
    evalApp.unmount()
    evalApp = null
    evalContainer.innerHTML = ''
    btn.style.display = ''
    requestAnimationFrame(() => fitPopup(map, popup))
  }

  btn.addEventListener('click', () => {
    if (evalApp) return
    const cfg = evaluatorConfig.value
    if (!cfg) {
      fetch(`/evaluate?id=${encodeURIComponent(id)}`).catch(() => {})
      return
    }
    const modelKeys = Array.isArray(props[cfg.field]) ? props[cfg.field] : []
    btn.style.display = 'none'
    evalApp = createApp({
      setup() {
        const state = ref({})
        return () =>
          h(CesEvaluator, {
            values: cfg.values,
            modelKeys,
            label: cfg.label ?? 'Evaluation',
            modelValue: state.value,
            'onUpdate:modelValue': (v) => {
              state.value = v
              evalState = v
            },
            onSubmit: async (eval_) => {
              try {
                const res = await fetch('/evaluate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ id, evaluation: eval_, field: cfg.field }),
                })
                const body = await res.json().catch(() => null)
                console.log('evaluate', id, res.status, body)
                const msg = body?.message ?? body?.status ?? `HTTP ${res.status}`
                showSnackbar(msg, res.ok ? 'success' : 'error')
              } catch (e) {
                console.error('evaluate failed', e)
                showSnackbar(`evaluate failed: ${e.message}`, 'error')
              }
              popup.remove()
            },
            onCancel: closeEvaluator,
          })
      },
    })
    evalApp.mount(evalContainer)
    requestAnimationFrame(() => fitPopup(map, popup))
  })
  root.appendChild(btn)

  const popup = new maplibregl.Popup({
    closeButton: false,
    anchor: 'top',
    offset: 32,
    maxWidth: '520px',
    className: 'point-popup',
  })
    .setLngLat(lngLat ?? feature.geometry.coordinates)
    .setDOMContent(root)
    .addTo(map)
  popup.on('close', () => {
    if (evalApp) {
      evalApp.unmount()
      evalApp = null
    }
  })

  const ensureFits = () => fitPopup(map, popup)
  requestAnimationFrame(ensureFits)
  const img = root.querySelector('.point-popup-img')
  if (img && !img.complete) img.addEventListener('load', ensureFits, { once: true })
}

function fitPopup(map, popup) {
  const el = popup.getElement()
  if (!el) return
  const pr = el.getBoundingClientRect()
  const mr = map.getContainer().getBoundingClientRect()
  const margin = 12
  let dx = 0
  let dy = 0
  if (pr.right > mr.right - margin) dx = pr.right - (mr.right - margin)
  if (pr.left < mr.left + margin) dx = pr.left - (mr.left + margin)
  if (pr.bottom > mr.bottom - margin) dy = pr.bottom - (mr.bottom - margin)
  if (pr.top < mr.top + margin) dy = pr.top - (mr.top + margin)
  if (!dx && !dy) return
  const c = map.getCenter()
  const pt = map.project(c)
  pt.x += dx
  pt.y += dy
  map.jumpTo({ center: map.unproject(pt) })
}

</script>

<template>
  <LoginScreen v-if="mode === 'login'" @start="onStart" @browse="enterBrowse" />

  <FacilitatorView v-else-if="mode === 'facilitator'" @back="exitFacilitator" />

  <div v-else-if="mode === 'validate'" class="val-layout">
    <div class="val-map">
      <MapView
        key="validate-map"
        ref="valMapRef"
        :points="currentFC"
        :cluster="false"
        :done="doneFC"
        :show-done="showDone"
        :highlight-current="true"
      >
        <label class="done-toggle">
          <input v-model="showDone" type="checkbox" />
          Show validated ({{ doneFC.features.length }})
        </label>
        <div class="who">
          {{ session.participant }} · {{ session.case_study.replace(/_/g, ' ') }}
          <button class="link" @click="logout">exit</button>
        </div>
      </MapView>
    </div>
    <div class="val-panel">
      <ValidationPanel
        :session="session"
        @current="onCurrent"
        @validated="onValidated"
        @quit="logout"
      />
    </div>
  </div>

  <MapView
    v-else
    key="browse-map"
    ref="mapRef"
    :points="filteredPoints"
    @point-click="onPointClick"
  >
    <div class="menu">
      <div class="row">
        <select v-model="selected" :disabled="!locations.length">
          <option v-for="loc in locations" :key="loc" :value="loc">{{ loc }}</option>
        </select>
        <button :disabled="!selected || loading" @click="load">
          {{ loading ? 'Loading…' : 'Load' }}
        </button>
        <button class="link" @click="mode = 'login'">workshop</button>
        <span v-if="error" class="error">{{ error }}</span>
      </div>
      <div v-if="classification" class="filters">
        <div class="filters-label">{{ classification.label }}</div>
        <template v-for="flt in classification.filters" :key="flt.field">
          <div v-if="flt.values" class="filter-block">
            <div class="row toggle-all">
              <span class="filter-name">{{ flt.label ?? flt.field }}</span>
              <button class="link" @click="setAllForFilter(flt, true)">all</button>
              <span>·</span>
              <button class="link" @click="setAllForFilter(flt, false)">none</button>
            </div>
            <div v-for="g in groupedValues(flt)" :key="g.label" class="class-group">
              <div v-if="g.label" class="class-group-label">{{ g.label }}</div>
              <ul class="class-list">
                <li v-for="v in g.values" :key="v.key">
                  <label>
                    <input
                      type="checkbox"
                      :checked="enabledFilters[flt.field]?.has(v.key)"
                      @change="toggleCategory(flt.field, v.key)"
                    />
                    <span class="acr">{{ v.short ?? v.key }}</span>
                    <span class="full">{{ v.name }}</span>
                  </label>
                </li>
              </ul>
            </div>
          </div>
          <label v-else class="filter-block bool-filter">
            <input
              type="checkbox"
              :checked="!!enabledFilters[flt.field]"
              @change="toggleBoolean(flt.field)"
            />
            <span>{{ flt.label ?? flt.field }}</span>
          </label>
        </template>
      </div>
    </div>

    <transition name="snack">
      <div v-if="snackbar" :class="['snackbar', `snack-${snackbar.kind}`]">
        {{ snackbar.message }}
      </div>
    </transition>
  </MapView>
</template>

<style scoped>
.val-layout {
  display: flex;
  width: 100%;
  height: 100%;
}
.val-map {
  flex: 55;
  min-width: 0;
  position: relative;
}
.val-panel {
  flex: 45;
  min-width: 360px;
  max-width: 620px;
  border-left: 1px solid #e5e7eb;
  position: relative;
}
.done-toggle {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}
.who {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  padding: 6px 10px;
  font-size: 12px;
  color: #444;
}
.menu {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  font-size: 13px;
  max-width: 320px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.menu select,
.menu > .row > button {
  font-size: 13px;
  padding: 3px 8px;
}
.error {
  color: #c33;
  margin-left: 6px;
}
.toggle-all {
  font-size: 11px;
  color: #777;
  gap: 6px;
}
.link {
  background: none;
  border: 0;
  padding: 0;
  font-size: 11px;
  color: #1b6cd9;
  cursor: pointer;
  text-decoration: underline;
}
.class-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.class-list li label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  cursor: pointer;
  font-size: 12px;
}
.class-list .acr {
  font-weight: 700;
  letter-spacing: 0.05em;
  width: 32px;
}
.class-list .full {
  color: #666;
}
.filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.filters-label {
  font-size: 11px;
  color: #555;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.filter-block {
  border-top: 1px solid #eee;
  padding-top: 6px;
}
.filter-name {
  font-size: 11px;
  color: #444;
  font-weight: 600;
  margin-right: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.bool-filter {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: pointer;
}
.class-group {
  margin-top: 6px;
}
.class-group-label {
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 2px;
}
.snackbar {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: 6px;
  background: #333;
  color: #fff;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  z-index: 10;
  pointer-events: auto;
  max-width: 80%;
}
.snackbar.snack-success { background: #16a34a; }
.snackbar.snack-error { background: #dc2626; }
.snack-enter-active, .snack-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.snack-enter-from, .snack-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
.cluster-list {
  position: absolute;
  top: 12px;
  right: 12px;
  bottom: 12px;
  width: 280px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  font-size: 13px;
  pointer-events: auto;
}
.cluster-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
}
.cluster-list-header .close {
  font-size: 18px;
  line-height: 1;
  text-decoration: none;
  color: #666;
}
.cluster-list-items {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}
.cluster-list-items li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid #f3f3f3;
}
.cluster-list-items .item-main {
  flex: 1;
  min-width: 0;
}
.cluster-list-items .item-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cluster-list-items .item-ces {
  font-size: 11px;
  color: #888;
  letter-spacing: 0.05em;
}
.cluster-list-items .eval-btn {
  background: #1b6cd9;
  color: #fff;
  border: 0;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.cluster-list-items .eval-btn:hover {
  background: #1559b3;
}
</style>
