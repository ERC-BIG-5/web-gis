<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['back'])

const rows = ref([])
const error = ref('')
let pollId = null

async function refresh() {
  try {
    const res = await fetch('facilitator/summary')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    rows.value = await res.json()
    error.value = ''
  } catch (e) {
    error.value = `failed to load summary: ${e.message}`
  }
}

const caseStudies = computed(() => [...new Set(rows.value.map((r) => r.case_study))])

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  refresh()
  pollId = setInterval(refresh, 15000)
})
onBeforeUnmount(() => clearInterval(pollId))
</script>

<template>
  <div class="fac-wrap">
    <div class="fac-card">
      <div class="fac-header">
        <h1>Facilitator dashboard</h1>
        <div>
          <button class="link" @click="refresh">refresh</button>
          <button class="link" @click="$emit('back')">back</button>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <table v-if="rows.length">
        <thead>
          <tr>
            <th>Case study</th>
            <th>Participant</th>
            <th>Validated</th>
            <th>Skipped</th>
            <th>Last activity</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.session_id">
            <td>{{ r.case_study.replace(/_/g, ' ') }}</td>
            <td>{{ r.participant }}</td>
            <td>
              <strong>{{ r.validated }}</strong> / {{ r.target }}
            </td>
            <td>{{ r.skipped }}</td>
            <td>{{ fmtTime(r.last_activity) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">No sessions yet. Auto-refreshes every 15 s.</p>

      <h2>Export results</h2>
      <ul class="exports">
        <li v-for="cs in caseStudies" :key="cs">
          <span>{{ cs.replace(/_/g, ' ') }}</span>
          <a :href="`export/${cs}?format=csv`">CSV</a>
          <a :href="`export/${cs}?format=json`">JSON</a>
        </li>
      </ul>
      <p v-if="!caseStudies.length" class="muted">Exports appear once there are sessions.</p>
    </div>
  </div>
</template>

<style scoped>
.fac-wrap {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  background: #f5f7fa;
  display: flex;
  justify-content: center;
  padding: 40px 16px;
  box-sizing: border-box;
}
.fac-card {
  width: min(760px, 100%);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 28px 32px;
  height: fit-content;
}
.fac-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
h1 {
  font-size: 20px;
  margin: 0 0 12px;
}
h2 {
  font-size: 15px;
  margin: 26px 0 8px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
}
th {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #777;
}
.exports {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}
.exports li {
  display: flex;
  gap: 12px;
  align-items: baseline;
}
.exports li span {
  min-width: 140px;
}
.exports a,
.link {
  color: #1b6cd9;
  font-size: 13px;
  background: none;
  border: 0;
  cursor: pointer;
  text-decoration: underline;
  padding: 0 4px;
}
.muted {
  color: #999;
  font-size: 13px;
}
.error {
  color: #c33;
  font-size: 13px;
}
</style>
