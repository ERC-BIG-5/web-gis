<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  session: { type: Object, required: true }, // {session_id, target, ces_values, ...}
})
const emit = defineEmits(['current', 'validated', 'quit'])

const current = ref(null) // /next payload
const progress = ref(null)
const doneAll = ref(false)
const loadingNext = ref(false)
const error = ref('')

const natureChoice = ref(null) // 'image' | 'text' | 'both' | 'none'
const judgments = ref({}) // ces key -> true | false
const comment = ref('')
const locationWrong = ref(false)
const skipOpen = ref(false)
const lightbox = ref(false)
const defsOpen = ref(false)
const imgFailed = ref(false)

let postStart = Date.now()

// ---- session timer ------------------------------------------------------
const elapsed = ref(0)
let timerId = null
function startTimer(fromServerSeconds) {
  elapsed.value = fromServerSeconds ?? 0
  if (timerId) clearInterval(timerId)
  timerId = setInterval(() => {
    elapsed.value += 1
  }, 1000)
}
const elapsedLabel = computed(() => {
  const m = Math.floor(elapsed.value / 60)
  const s = elapsed.value % 60
  return `${m}:${String(s).padStart(2, '0')}`
})

// ---- ces meta ------------------------------------------------------------
const cesMeta = computed(() => {
  const map = {}
  for (const v of props.session.ces_values ?? []) map[v.key] = v
  return map
})
const cesKeys = computed(() => {
  const ces = current.value?.feature?.properties?.ces
  return Array.isArray(ces) ? ces : []
})
// CES categories the LLM did NOT assign — offered as optional additions
const otherCesKeys = computed(() => {
  const assigned = new Set(cesKeys.value)
  return (props.session.ces_values ?? [])
    .map((v) => v.key)
    .filter((k) => !assigned.has(k))
})
const added = ref([])
function toggleAdded(key) {
  added.value = added.value.includes(key)
    ? added.value.filter((k) => k !== key)
    : [...added.value, key]
}

// ---- image ---------------------------------------------------------------
function imgUrl(maxSide) {
  const f = current.value
  const name = f?.feature?.properties?.image_name
  if (!f || !name) return ''
  return `/scaled?base=${encodeURIComponent(f.base_media_path)}&name=${encodeURIComponent(name)}&max_side=${maxSide}`
}
const panelImg = computed(() => imgUrl(900))
const fullImg = computed(() => imgUrl(1600))

// ---- flow ----------------------------------------------------------------
function resetForm() {
  natureChoice.value = null
  judgments.value = {}
  added.value = []
  comment.value = ''
  locationWrong.value = false
  skipOpen.value = false
  lightbox.value = false
  imgFailed.value = false
  postStart = Date.now()
}

async function loadNext() {
  loadingNext.value = true
  error.value = ''
  try {
    const res = await fetch(`/session/${props.session.session_id}/next`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    progress.value = data.progress
    if (!timerId) startTimer(0) // count this sitting, not session age
    if (data.done) {
      doneAll.value = true
      current.value = null
      return
    }
    current.value = data
    resetForm()
    emit('current', data)
  } catch (e) {
    error.value = `failed to load next post: ${e.message}`
  } finally {
    loadingNext.value = false
  }
}

const canSave = computed(() => {
  if (!current.value || loadingNext.value) return false
  if (!natureChoice.value) return false
  if (natureChoice.value === 'none') return true
  return cesKeys.value.every((k) => judgments.value[k] === true || judgments.value[k] === false)
})

async function submit(payloadExtra) {
  const f = current.value
  if (!f) return
  loadingNext.value = true
  error.value = ''
  try {
    const res = await fetch(`/session/${props.session.session_id}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feature_id: f.feature_id,
        elapsed_ms: Date.now() - postStart,
        ...payloadExtra,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
    const data = await res.json()
    progress.value = data.progress
    emit('validated', { feature: f.feature, feature_id: f.feature_id, status: data.status })
    await loadNext()
  } catch (e) {
    error.value = `save failed: ${e.message}`
    loadingNext.value = false
  }
}

function save() {
  if (!canSave.value) return
  const isNone = natureChoice.value === 'none'
  const judged = isNone ? {} : { ...judgments.value }
  if (!isNone) {
    for (const k of added.value) judged[k] = 'added'
  }
  submit({
    nature_elements: natureChoice.value,
    ces_judgments: judged,
    comment: comment.value.trim() || null,
    location_incorrect: locationWrong.value,
  })
}

function cantJudge(reason) {
  skipOpen.value = false
  submit({ skipped_reason: reason, nature_elements: null, ces_judgments: {} })
}

function setJudgment(key, val) {
  judgments.value = {
    ...judgments.value,
    [key]: judgments.value[key] === val ? null : val,
  }
}

// ---- keyboard ------------------------------------------------------------
const NATURE_KEYS = { 1: 'image', 2: 'text', 3: 'both', 4: 'none' }
function onKey(e) {
  const tag = e.target?.tagName
  if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return
  if (defsOpen.value) {
    if (e.key === 'Escape') defsOpen.value = false
    return
  }
  if (lightbox.value && e.key === 'Escape') {
    lightbox.value = false
    return
  }
  if (NATURE_KEYS[e.key] && current.value) {
    natureChoice.value = NATURE_KEYS[e.key]
    e.preventDefault()
  } else if (e.key === 'Enter' && canSave.value) {
    save()
    e.preventDefault()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  loadNext()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  if (timerId) clearInterval(timerId)
})

const pct = computed(() => {
  if (!progress.value?.target) return 0
  return Math.min(100, (progress.value.validated / progress.value.target) * 100)
})
</script>

<template>
  <div class="vpanel">
    <!-- progress -->
    <div class="progress">
      <div class="progress-row">
        <strong>
          {{ progress?.validated ?? 0 }} / {{ progress?.target ?? session.target }}
          validated
        </strong>
        <span class="timer">⏱ {{ elapsedLabel }}</span>
      </div>
      <div class="bar"><div class="bar-fill" :style="{ width: pct + '%' }"></div></div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- completion -->
    <div v-if="doneAll" class="done-screen">
      <h2>All done — thank you! 🎉</h2>
      <p>
        You validated <strong>{{ progress?.validated }}</strong> posts
        ({{ progress?.skipped ?? 0 }} skipped) in {{ elapsedLabel }}.
      </p>
      <p class="muted">You can close this window now.</p>
      <button class="secondary" @click="$emit('quit')">Back to start</button>
    </div>

    <!-- current post -->
    <template v-else-if="current">
      <div class="post">
        <div class="img-box" @click="!imgFailed && (lightbox = true)">
          <img
            v-if="!imgFailed"
            :key="current.feature_id"
            :src="panelImg"
            alt=""
            @error="imgFailed = true"
          />
          <div v-else class="img-fail">image failed to load<br /><span>use "Can't judge"</span></div>
          <span v-if="!imgFailed" class="zoom-hint">click to enlarge</span>
        </div>
        <p v-if="current.feature.properties.text" class="post-text">
          {{ current.feature.properties.text }}
        </p>
      </div>

      <!-- step 1 -->
      <div class="step">
        <div class="step-label">1 · Does this post contain nature elements?</div>
        <div class="nature-btns">
          <button
            v-for="(val, key) in { 1: 'image', 2: 'text', 3: 'both', 4: 'none' }"
            :key="val"
            :class="['nature-btn', { active: natureChoice === val }]"
            @click="natureChoice = val"
          >
            <span class="kbd">{{ key }}</span>
            {{ val === 'image' ? 'In image' : val === 'text' ? 'In text' : val === 'both' ? 'In both' : 'None' }}
          </button>
        </div>
      </div>

      <!-- step 2 -->
      <div class="step" :class="{ disabled: natureChoice === 'none' }">
        <div class="step-head">
          <div class="step-label">2 · Do you agree with the model's CES categories?</div>
          <button type="button" class="defs-link" @click="defsOpen = true">
            CES definitions
          </button>
        </div>
        <div v-if="!cesKeys.length" class="muted">No CES assigned by the model — nothing to judge here.</div>
        <div v-else class="chips">
          <div v-for="k in cesKeys" :key="k" class="chip" :class="{
            agreed: judgments[k] === true,
            disagreed: judgments[k] === false,
          }">
            <span class="chip-short">{{ cesMeta[k]?.short ?? k }}</span>
            <span class="chip-name">{{ cesMeta[k]?.name ?? k }}</span>
            <button
              type="button"
              class="chip-btn no"
              :class="{ on: judgments[k] === false }"
              :disabled="natureChoice === 'none'"
              title="disagree"
              @click="setJudgment(k, false)"
            >✗</button>
            <button
              type="button"
              class="chip-btn yes"
              :class="{ on: judgments[k] === true }"
              :disabled="natureChoice === 'none'"
              title="agree"
              @click="setJudgment(k, true)"
            >✓</button>
          </div>
        </div>
        <div v-if="otherCesKeys.length" class="add-section">
          <div class="add-label">Add categories the model missed (optional)</div>
          <div class="add-pills">
            <button
              v-for="k in otherCesKeys"
              :key="k"
              type="button"
              class="add-pill"
              :class="{ on: added.includes(k) }"
              :disabled="natureChoice === 'none'"
              :title="cesMeta[k]?.name ?? k"
              @click="toggleAdded(k)"
            >
              <span class="add-plus">{{ added.includes(k) ? '✓' : '+' }}</span>
              {{ cesMeta[k]?.short ?? k }}
              <span class="add-name">{{ cesMeta[k]?.name ?? '' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- location flag -->
      <label class="loc-flag" :class="{ on: locationWrong }">
        <input v-model="locationWrong" type="checkbox" />
        📍 The location of this post on the map seems incorrect
      </label>

      <!-- comment -->
      <textarea
        v-model="comment"
        class="comment"
        rows="1"
        placeholder="Optional comment…"
      ></textarea>

      <!-- actions -->
      <div class="actions">
        <div class="skip-wrap">
          <button class="secondary" @click="skipOpen = !skipOpen">Can't judge</button>
          <div v-if="skipOpen" class="skip-menu">
            <button @click="cantJudge('broken image')">Broken image</button>
            <button @click="cantJudge('language')">Language</button>
            <button @click="cantJudge('other')">Other</button>
          </div>
        </div>
        <button class="primary" :disabled="!canSave" @click="save">
          {{ loadingNext ? '…' : 'Save & Next ⏎' }}
        </button>
      </div>
    </template>

    <div v-else-if="loadingNext" class="muted center">Loading…</div>

    <!-- lightbox -->
    <div v-if="lightbox" class="lightbox" @click="lightbox = false">
      <img :src="fullImg" alt="" />
    </div>

    <!-- CES definitions -->
    <div v-if="defsOpen" class="defs-overlay" @click.self="defsOpen = false">
      <div class="defs-card">
        <div class="defs-header">
          <h2>CES categories — definitions & examples</h2>
          <button class="defs-close" @click="defsOpen = false">✕ close</button>
        </div>
        <div class="defs-list">
          <div
            v-for="v in session.ces_values"
            :key="v.key"
            class="defs-item"
            :class="{ assigned: cesKeys.includes(v.key) }"
          >
            <div class="defs-title">
              <span class="defs-short">{{ v.short }}</span>
              <strong>{{ v.name }}</strong>
              <span v-if="cesKeys.includes(v.key)" class="defs-tag">assigned to this post</span>
            </div>
            <p class="defs-def">{{ v.definition || 'No definition provided.' }}</p>
            <p v-if="v.examples" class="defs-ex"><em>Examples:</em> {{ v.examples }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vpanel {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  overflow-y: auto;
  box-sizing: border-box;
}
.progress-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 14px;
}
.timer {
  color: #666;
  font-variant-numeric: tabular-nums;
}
.bar {
  height: 6px;
  border-radius: 3px;
  background: #eee;
  margin-top: 5px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: #1b6cd9;
  transition: width 0.25s ease;
}
.post {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.img-box {
  position: relative;
  width: 100%;
  background: #f3f4f6;
  border-radius: 8px;
  overflow: hidden;
  cursor: zoom-in;
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.img-box img {
  width: 100%;
  max-height: 44vh;
  object-fit: contain;
  display: block;
}
.img-fail {
  padding: 40px 10px;
  color: #999;
  font-size: 14px;
  text-align: center;
}
.img-fail span {
  font-size: 12px;
}
.zoom-hint {
  position: absolute;
  right: 8px;
  bottom: 8px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border-radius: 4px;
  padding: 2px 6px;
}
.post-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.45;
  max-height: 7.5em;
  overflow-y: auto;
  color: #333;
  white-space: pre-wrap;
}
.step-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.defs-link {
  background: none;
  border: 0;
  color: #1b6cd9;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  white-space: nowrap;
}
.defs-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 120;
  padding: 24px;
  box-sizing: border-box;
}
.defs-card {
  background: #fff;
  border-radius: 12px;
  width: min(680px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}
.defs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}
.defs-header h2 {
  margin: 0;
  font-size: 16px;
}
.defs-close {
  background: none;
  border: 0;
  color: #666;
  font-size: 13px;
  cursor: pointer;
}
.defs-list {
  overflow-y: auto;
  padding: 12px 20px 20px;
}
.defs-item {
  padding: 10px 12px;
  border-radius: 8px;
}
.defs-item.assigned {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}
.defs-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
}
.defs-short {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #1b6cd9;
  width: 34px;
}
.defs-tag {
  font-size: 11px;
  color: #1b6cd9;
  background: #dbeafe;
  border-radius: 999px;
  padding: 1px 8px;
}
.defs-def {
  margin: 4px 0 2px 42px;
  font-size: 13px;
  color: #333;
  line-height: 1.45;
}
.defs-ex {
  margin: 0 0 2px 42px;
  font-size: 12px;
  color: #777;
  line-height: 1.4;
}
.step-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #555;
  margin-bottom: 6px;
}
.step.disabled .chips,
.step.disabled .add-section {
  opacity: 0.35;
  pointer-events: none;
}
.add-section {
  margin-top: 10px;
}
.add-label {
  font-size: 11px;
  color: #888;
  margin-bottom: 5px;
}
.add-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.add-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 4px 9px;
  border: 1.2px dashed #ccc;
  border-radius: 999px;
  background: #fff;
  color: #555;
  cursor: pointer;
  font-weight: 600;
  letter-spacing: 0.03em;
}
.add-pill .add-name {
  font-weight: 400;
  color: #999;
  letter-spacing: 0;
}
.add-pill:hover {
  border-color: #93c5fd;
}
.add-pill.on {
  border-style: solid;
  border-color: #1b6cd9;
  background: #dbeafe;
  color: #1b3e73;
}
.add-pill.on .add-name {
  color: #1b6cd9;
}
.add-plus {
  font-size: 12px;
}
.nature-btns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.nature-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 10px 4px;
  font-size: 13px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
}
.nature-btn:hover {
  border-color: #93c5fd;
}
.nature-btn.active {
  border-color: #1b6cd9;
  background: #dbeafe;
  font-weight: 600;
}
.kbd {
  font-size: 10px;
  color: #888;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 0 4px;
  background: #fff;
}
.chips {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chip {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1.5px solid #dbeafe;
  background: #eff6ff;
  border-radius: 999px;
  padding: 6px 8px 6px 12px;
  font-size: 13px;
}
.chip.agreed {
  border-color: #6ee7b7;
  background: #d1fae5;
}
.chip.disagreed {
  border-color: #fca5a5;
  background: #fee2e2;
}
.chip-short {
  font-weight: 700;
  letter-spacing: 0.05em;
  font-size: 11px;
  width: 34px;
}
.chip-name {
  flex: 1;
  color: #333;
}
.chip-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid #bbb;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
}
.chip-btn:hover {
  background: #f3f3f3;
}
.chip-btn.yes.on {
  background: #16a34a;
  border-color: #16a34a;
  color: #fff;
}
.chip-btn.no.on {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
}
.loc-flag {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #555;
  border: 1.2px dashed #ddd;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
}
.loc-flag:hover {
  border-color: #fbbf24;
}
.loc-flag.on {
  border-style: solid;
  border-color: #f59e0b;
  background: #fef3c7;
  color: #92400e;
}
.comment {
  resize: vertical;
  min-height: 34px;
  font-size: 13px;
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-family: inherit;
}
.actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-top: auto;
  padding-top: 4px;
}
.primary {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  padding: 12px;
  border: 0;
  border-radius: 8px;
  background: #1b6cd9;
  color: #fff;
  cursor: pointer;
}
.primary:hover:not(:disabled) {
  background: #1559b3;
}
.primary:disabled {
  opacity: 0.4;
  cursor: default;
}
.secondary {
  font-size: 13px;
  padding: 12px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.secondary:hover {
  background: #f5f5f5;
}
.skip-wrap {
  position: relative;
}
.skip-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  min-width: 150px;
  overflow: hidden;
  z-index: 5;
}
.skip-menu button {
  background: none;
  border: 0;
  padding: 10px 12px;
  text-align: left;
  font-size: 13px;
  cursor: pointer;
}
.skip-menu button:hover {
  background: #f3f4f6;
}
.done-screen {
  margin: auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}
.done-screen h2 {
  margin: 0;
}
.muted {
  color: #999;
  font-size: 13px;
}
.center {
  margin: auto;
}
.error {
  color: #c33;
  font-size: 13px;
  margin: 0;
}
.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  cursor: zoom-out;
}
.lightbox img {
  max-width: 94vw;
  max-height: 94vh;
  object-fit: contain;
}
</style>