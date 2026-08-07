<script setup>
import { onMounted, ref } from 'vue'

const emit = defineEmits(['start', 'browse'])

const locations = ref([])
const caseStudy = ref('')
const participant = ref('')
const busy = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/locations')
    locations.value = await res.json()
    caseStudy.value = locations.value[0] ?? ''
  } catch (e) {
    error.value = `failed to fetch case studies: ${e.message}`
  }
})

async function start() {
  if (!caseStudy.value || !participant.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const res = await fetch('/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_study: caseStudy.value,
        participant: participant.value.trim(),
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
    emit('start', await res.json())
  } catch (e) {
    error.value = `could not start session: ${e.message}`
  } finally {
    busy.value = false
  }
}

function pretty(loc) {
  return loc.replace(/_/g, ' ')
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <h1>CES Validation Workshop</h1>
      <p class="sub">
        Pick your case study and enter your name to start (or resume) your
        validation session.
      </p>

      <label class="field">
        <span>Case study</span>
        <select v-model="caseStudy" :disabled="!locations.length || busy">
          <option v-for="loc in locations" :key="loc" :value="loc">
            {{ pretty(loc) }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>Your name</span>
        <input
          v-model="participant"
          type="text"
          placeholder="e.g. Anna"
          :disabled="busy"
          @keydown.enter="start"
        />
      </label>

      <button
        class="start-btn"
        :disabled="!caseStudy || !participant.trim() || busy"
        @click="start"
      >
        {{ busy ? 'Starting…' : 'Start validation' }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="browse-link" type="button" @click="$emit('browse')">
        Browse mode (facilitator)
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #eef4fb 0%, #f7f9f7 100%);
}
.login-card {
  width: min(420px, 92vw);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 30px rgba(0, 0, 0, 0.12);
  padding: 32px 34px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
h1 {
  margin: 0;
  font-size: 22px;
}
.sub {
  margin: 0;
  color: #666;
  font-size: 14px;
  line-height: 1.4;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #444;
  font-weight: 600;
}
.field select,
.field input {
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #ccc;
  border-radius: 8px;
  font-weight: 400;
}
.start-btn {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 600;
  padding: 12px;
  border: 0;
  border-radius: 8px;
  background: #1b6cd9;
  color: #fff;
  cursor: pointer;
}
.start-btn:hover:not(:disabled) {
  background: #1559b3;
}
.start-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.error {
  color: #c33;
  font-size: 13px;
  margin: 0;
}
.browse-link {
  background: none;
  border: 0;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  align-self: center;
}
</style>
