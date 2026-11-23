<script setup>
// Anomalies vigents d'una persona.
// - Mode normal: una etiqueta per anomalia (fitxa de la persona).
// - Mode compacte: només una icona d'avís; el detall surt en passar-hi el ratolí o en clicar-la
//   (regió del contracte, on l'espai és just).
import { ref, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

const props = defineProps({
  anomalies: { type: Array, default: () => [] },
  small: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
});

const { t, te } = useI18n();

const label = (anomaly) => {
  const key = `person_anomaly.types.${anomaly.token}`;
  return te(key) ? t(key) : anomaly.name;
};

const title = (anomaly) => {
  const parts = [`${t('person_anomaly.start_date')}: ${formatDate(anomaly.start_date)}`];
  if (anomaly.end_date) parts.push(`${t('person_anomaly.end_date')}: ${formatDate(anomaly.end_date)}`);
  if (anomaly.observation) parts.push(anomaly.observation);
  return `${label(anomaly)}\n${parts.join('\n')}`;
};

// Popover del mode compacte: posició fixa perquè no el retallin les cel·les amb truncate/overflow
const trigger = ref(null);
const open = ref(false);
const pinned = ref(false);
const position = ref({ top: 0, left: 0 });

const place = () => {
  if (!trigger.value) return;
  const rect = trigger.value.getBoundingClientRect();
  const width = 288;
  const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
  position.value = { top: rect.bottom + 6, left };
};

const show = () => {
  place();
  open.value = true;
};

const hide = () => {
  if (!pinned.value) open.value = false;
};

const onDocumentClick = (event) => {
  if (trigger.value && !trigger.value.contains(event.target)) {
    pinned.value = false;
    open.value = false;
    document.removeEventListener('click', onDocumentClick);
  }
};

const toggle = () => {
  pinned.value = !pinned.value;
  if (pinned.value) {
    show();
    document.addEventListener('click', onDocumentClick);
  } else {
    open.value = false;
    document.removeEventListener('click', onDocumentClick);
  }
};

onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick));
</script>

<template>
  <span v-if="props.anomalies?.length && props.compact" ref="trigger" class="inline-flex items-center"
    @mouseenter="show" @mouseleave="hide">
    <button type="button" @click.stop="toggle" :aria-label="t('person_anomaly.current_anomalies')"
      class="inline-flex items-center gap-0.5 text-amber-500 hover:text-amber-600">
      <Icon name="fa6-solid:triangle-exclamation" />
      <span v-if="props.anomalies.length > 1" class="text-[11px] font-semibold leading-none">
        {{ props.anomalies.length }}
      </span>
    </button>
    <Teleport to="body">
      <div v-if="open" class="fixed z-[60] w-72 rounded-md border border-amber-300 bg-white shadow-lg p-3 text-sm"
        :style="{ top: `${position.top}px`, left: `${position.left}px` }"
        @click.stop @mouseenter="open = true" @mouseleave="hide">
        <p class="font-semibold text-amber-800 mb-2 flex items-center gap-2">
          <Icon name="fa6-solid:triangle-exclamation" />
          {{ t('person_anomaly.current_anomalies') }}
        </p>
        <ul class="space-y-2">
          <li v-for="anomaly in props.anomalies" :key="anomaly.id" class="text-slate-700">
            <span class="font-medium">{{ label(anomaly) }}</span>
            <span class="block text-xs text-slate-500">
              {{ t('person_anomaly.start_date') }}: {{ formatDate(anomaly.start_date) }}
              <template v-if="anomaly.end_date">
                · {{ t('person_anomaly.end_date') }}: {{ formatDate(anomaly.end_date) }}
              </template>
            </span>
            <span v-if="anomaly.observation" class="block text-xs text-slate-600 whitespace-pre-line break-words">
              {{ anomaly.observation }}
            </span>
          </li>
        </ul>
      </div>
    </Teleport>
  </span>

  <span v-else-if="props.anomalies?.length" class="inline-flex flex-wrap items-center gap-1">
    <span v-for="anomaly in props.anomalies" :key="anomaly.id" :title="title(anomaly)"
      class="badge-amber inline-flex items-center gap-1 rounded whitespace-nowrap"
      :class="props.small ? 'px-1.5 py-0 text-xs' : 'px-2 py-0.5 text-sm'">
      <Icon name="fa6-solid:triangle-exclamation" />
      {{ label(anomaly) }}
    </span>
  </span>
</template>
