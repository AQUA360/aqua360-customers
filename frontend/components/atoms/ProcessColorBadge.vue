<script setup>
import { AppColors } from '~/utils/config';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';

const props = defineProps({
  value: String,
  taskId: String,
  color: {
    type: String,
    default: 'gray'
  },
  noBackground: {
    type: Boolean,
    default: false
  },
  billingId: [String, Number],
});

const emit = defineEmits(['refresh', 'error']);
const emits = emit;

const { $apiManager } = useNuxtApp();
const { t } = useI18n();

const progress = ref(0);
const error = ref(false);
const restarting = ref(false);
const failedQueueItemId = ref(null);
let itvl = null;
let pendingPolls = 0;
let stalledPolls = 0;
let lastPercent = 0;
// Tasca que no arrenca (PENDING): ens rendim als 3 min (90 × 2 s).
const MAX_PENDING_POLLS = 90;
// Tasca en marxa (STARTED/PROGRESS) sense que el percentatge pugi: ens rendim als 10 min
// (300 × 2 s). Cada avanç del percentatge torna a començar el compte, així que una tasca
// llarga que progressa no es talla mai.
const MAX_STALLED_POLLS = 300;

const colorClass = ref('badge-gray');
const progressWidth = computed(() => `${Math.min(Math.max(Number(progress.value), 0), 100)}%`);

onBeforeRouteLeave((to, from) => {
  console.log("User is leaving the page, clear all intervals");
  clearInterval(itvl)
});

const setColor = () => {
  const color = AppColors.find(c => c.code === props.color);
  colorClass.value = color ? color.class : 'badge-gray';
};

const startInterval = async() => {
  clearInterval(itvl)
  pendingPolls = 0;
  stalledPolls = 0;
  lastPercent = 0;
  error.value = false;
  failedQueueItemId.value = null;

  itvl = setInterval(async () => {
      try {
        let activeItem = null;

        if (props.billingId) {
          // Filtrem per billing_id perquè el llistat sense filtre només retorna els
          // últims 10 items finalitzats de TOT el sistema: si hi ha molts altres lots
          // finalitzats recentment, l'item d'aquest lot (p.ex. failed) podria quedar
          // fora de la finestra i semblar "no trobat" indefinidament.
          const queueList = await $apiManager.fetch(useRuntimeConfig().public.apiHost + `/billing/billing-queue/?billing_id=${props.billingId}`, 'GET');
          if (queueList && Array.isArray(queueList)) {
            // Agafem el més recent (per created_at) entre pending/running/failed/skipped.
            activeItem = [...queueList]
              .filter(item => ['pending', 'running', 'failed', 'skipped'].includes(item.status))
              .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
          }

          if (!activeItem) {
            clearInterval(itvl);
            emit('refresh');
            return;
          }

          // L'endpoint de billing-queue ja retorna `percent`/`status` fets i actualitzats
          // (inclou l'autoreparació via AsyncResult al propi backend), així que no cal
          // consultar `/task-progress/<task_id>/` també des del front per cada badge.
          progress.value = activeItem.percent || 0;

          if (activeItem.status === 'completed') {
            clearInterval(itvl);
            emit('refresh');
            return;
          }

          if (activeItem.status === 'failed' || activeItem.status === 'skipped') {
            error.value = true;
            failedQueueItemId.value = activeItem.id;
            clearInterval(itvl);
            return;
          }

          // running/pending: seguim fent polling amb el següent tick.
          return;
        }

        // Sense billingId (component usat només amb taskId directe): mantenim el
        // comportament antic basat en `checkTask`.
        if (props.taskId) {
          const res = await $apiManager.checkTask(props.taskId)
          if (res) {
            progress.value = res.percent || 0

            if (res.state === 'SUCCESS') {
              clearInterval(itvl);
              emit('refresh');
            }
            else if (res.state === 'FAILURE' || res.state === 'REVOKED') {
              error.value = true;
              clearInterval(itvl);
              // El badge pot estar amagat (v-show="false"): sense aquest esdeveniment
              // el pare no sap que la tasca ha fallat i es queda esperant indefinidament.
              emits('error', { state: res.state });
            }
            else if (res.state === 'PENDING') {
              pendingPolls += 1;
              if (pendingPolls >= MAX_PENDING_POLLS) {
                error.value = true;
                clearInterval(itvl);
                emits('error', { state: res.state, reason: 'timeout' });
              }
            }
            else if (res.state === 'STARTED' || res.state === 'PROGRESS') {
              const percent = Number(res.percent) || 0;
              if (percent > lastPercent) {
                lastPercent = percent;
                stalledPolls = 0;
              } else {
                stalledPolls += 1;
                if (stalledPolls >= MAX_STALLED_POLLS) {
                  error.value = true;
                  clearInterval(itvl);
                }
              }
            }
          }
        }
      }
      catch (e) {
        clearInterval(itvl);
        emit('refresh');
      }
    }, 2000)
};

const restartQueueItem = async () => {
  if (!failedQueueItemId.value) {
    emit('refresh');
    return;
  }
  restarting.value = true;
  try {
    await $apiManager.fetch(
      useRuntimeConfig().public.apiHost + `/billing/billing-queue/${failedQueueItemId.value}/action/`,
      'POST',
      { action: 'restart' },
      { 'Content-Type': 'application/json' }
    );
    error.value = false;
    failedQueueItemId.value = null;
    progress.value = 0;
    startInterval();
    emit('refresh');
  } catch (e) {
    console.error('Error restarting queue item:', e);
  } finally {
    restarting.value = false;
  }
};

onMounted(() => {
  setColor();
  if (props.taskId || props.billingId) {
    startInterval();
  }
});

onUnmounted(() => {
  clearInterval(itvl);
});

watch(() => props.color, setColor);
watch(() => props.taskId, startInterval);
watch(() => props.billingId, startInterval);
</script>

<template>
  <div v-if="error" class="inline-flex items-center gap-2 rounded px-2 py-0.5 text-sm badge-red">
    <span class="flex items-center gap-1">
      <Icon name="fa6-solid:circle-exclamation" class="w-4 h-4" />
      {{ t('failed') }}
    </span>
    <button type="button" :disabled="restarting" @click.stop="restartQueueItem"
      class="flex items-center gap-1 rounded px-1.5 py-0.5 bg-white/60 hover:bg-white text-red-800 disabled:opacity-50"
      :title="t('common.restart')">
      <Icon :name="restarting ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'" :class="{ 'animate-spin': restarting }" />
    </button>
  </div>
  <div v-else class="relative inline-block rounded px-2 py-0.5 text-sm cursor-default overflow-hidden" :class="noBackground ? 'bg-transparent' : colorClass">
    <div class="absolute top-0 left-0 h-full transition-all duration-200" :style="{ width: progressWidth, backgroundColor: 'rgba(50, 50, 50, 0.1)' }"></div>
    <div class="relative flex items-center gap-1">
      <Icon name="mdi-loading" class="w-4 h-4 animate-spin" v-if="progress < 100" />
      <span>{{ props.value }}</span>
    </div>
  </div>
</template>

<style scoped>
</style>
