<script setup>
import { useI18n } from 'vue-i18n';

const props = defineProps({
  label: String,
  icon: String,
  // `FieldDetail` se usa también con valores booleanos/numericos (p.ej. telecontrol).
  // Vue avisa si el tipo no coincide, así que ampliamos el tipo aceptado.
  value: {
    type: [String, Boolean, Number, Object, Array],
    default: null,
  },
  strong: Boolean
});
</script>

<template>
  <div :id="'field_' + props.label" class="mb-2 grid" :class="props.icon ? 'grid-cols-[20px,1fr]' : 'grid-cols-[120px,1fr]'">
    <Icon v-if="props.icon" :name="props.icon" class="text-slate-400" />
    <label v-else class="inline-block truncate" :class="strong ? 'text-slate-600 font-bold' : 'text-slate-600'" :title="props.label">{{ props.label }}</label>
    <slot><span class="text-black-900">{{ props.value == null ? '-' : String(props.value) }}</span></slot>
  </div>
</template>