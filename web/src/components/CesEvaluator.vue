<script setup>
import { computed } from 'vue'

const props = defineProps({
  values: { type: Array, required: true }, // [{key, short, name}, ...]
  modelKeys: { type: Array, default: () => [] }, // keys the model selected
  modelValue: { type: Object, default: () => ({}) }, // {key: true|false|null}
  label: { type: String, default: 'Evaluation' },
})
const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

const modelKeysSet = computed(() => new Set(props.modelKeys))

function evalState(key) {
  const v = props.modelValue[key]
  return v === true || v === false ? v : null
}

function pillClass(v) {
  const inModel = modelKeysSet.value.has(v.key)
  const e = evalState(v.key)
  if (inModel && e === null) return 'pill-blue'    // model: yes, untouched
  if (inModel && e === true) return 'pill-green'   // TP
  if (inModel && e === false) return 'pill-red'    // FP
  if (!inModel && e === true) return 'pill-yellow' // FN
  return 'pill-grey'                                // default / TN
}

function setEval(key, target) {
  const cur = evalState(key)
  const next = cur === target ? null : target // toggle off if already on
  emit('update:modelValue', { ...props.modelValue, [key]: next })
}
</script>

<template>
  <div class="ces-eval">
    <div class="ces-eval-header">
      <strong>{{ label }}</strong>
    </div>
    <div class="pills">
      <div
        v-for="v in values"
        :key="v.key"
        :class="['pill', pillClass(v)]"
      >
        <span class="short">{{ v.short ?? v.key }}</span>
        <span class="name">{{ v.name }}</span>
        <button
          v-if="modelKeysSet.has(v.key)"
          type="button"
          :class="['icon', 'icon-no', { active: evalState(v.key) === false }]"
          @click="setEval(v.key, false)"
          title="reject"
        >✗</button>
        <button
          type="button"
          :class="['icon', 'icon-yes', { active: evalState(v.key) === true }]"
          @click="setEval(v.key, true)"
          title="accept"
        >✓</button>
      </div>
    </div>
    <div class="legend">
      <span class="dot pill-blue"></span> model:yes
      <span class="dot pill-green"></span> TP
      <span class="dot pill-red"></span> FP
      <span class="dot pill-yellow"></span> FN
      <span class="dot pill-grey"></span> –
    </div>
    <div class="actions">
      <button type="button" class="cancel-btn" @click="$emit('cancel')">Cancel</button>
      <button type="button" class="submit-btn" @click="$emit('submit', modelValue)">Submit</button>
    </div>
  </div>
</template>

<style scoped>
.ces-eval {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #eee;
  font-size: 12px;
}
.ces-eval-header {
  margin-bottom: 6px;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}
.submit-btn,
.cancel-btn {
  border: 0;
  border-radius: 4px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
}
.submit-btn { background: #1b6cd9; color: #fff; }
.submit-btn:hover { background: #1559b3; }
.cancel-btn { background: #eee; color: #444; }
.cancel-btn:hover { background: #ddd; }
.pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 11px;
  user-select: none;
}
.pill .short {
  font-weight: 700;
  letter-spacing: 0.04em;
  font-size: 10px;
}
.pill .name {
  font-size: 11px;
  margin-right: 2px;
}
.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid #bbb;
  background: #fff;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}
.icon:hover { background: #f3f3f3; }
.icon-yes.active { background: #16a34a; color: #fff; border-color: #16a34a; }
.icon-no.active { background: #dc2626; color: #fff; border-color: #dc2626; }
.pill-grey { background: #eee; color: #555; }
.pill-blue { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
.pill-green { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
.pill-red { background: #fee2e2; color: #991b1b; border-color: #fca5a5; }
.pill-yellow { background: #fef3c7; color: #92400e; border-color: #fcd34d; }
.legend {
  margin-top: 6px;
  font-size: 10px;
  color: #777;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 2px;
  vertical-align: middle;
}
</style>
