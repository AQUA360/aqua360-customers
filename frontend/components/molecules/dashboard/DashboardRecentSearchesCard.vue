<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import { format, isToday, isYesterday } from 'date-fns';
import DashboardCardFrame from './DashboardCardFrame.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import { searchValues, foundItemTranslation } from '~/utils/search';
import { formatDate } from '~/utils/date';

/**
 * Elements visitats recentment des del cercador. Es mostren en una sola fila
 * amb scroll horitzontal, agrupats per dia amb una etiqueta al davant de cada dia.
 */
defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const { $SearchApiService } = useNuxtApp();

const SCROLL_STEP = 320;

const loading = ref(false);
const history = ref([]);
const scroller = ref(null);
const canScrollLeft = ref(false);
const canScrollRight = ref(false);
let resizeObserver = null;

const groups = computed(() => {
  const byDay = {};
  history.value.forEach(result => {
    const key = format(new Date(result.searched_at), 'yyyy-MM-dd');
    (byDay[key] = byDay[key] || []).push(result);
  });
  return Object.entries(byDay).map(([key, results]) => ({ key, results }));
});

const dayLabel = (key) => {
  const date = new Date(`${key}T00:00:00`);
  if (isToday(date)) return t('calendar_tasks.today');
  if (isYesterday(date)) return t('home_dashboard.yesterday');
  return formatDate(key);
};

const updateArrows = () => {
  const el = scroller.value;
  if (!el) return;
  canScrollLeft.value = el.scrollLeft > 2;
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
};

const scrollBy = (direction) => {
  scroller.value?.scrollBy({ left: direction * SCROLL_STEP, behavior: 'smooth' });
};

// La roda vertical desplaça la fila mentre hi hagi on anar; als extrems es deixa
// passar l'esdeveniment perquè la pàgina continuï fent scroll.
const handleWheel = (event) => {
  const el = scroller.value;
  if (!el || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
  const goingRight = event.deltaY > 0;
  if ((goingRight && !canScrollRight.value) || (!goingRight && !canScrollLeft.value)) return;
  event.preventDefault();
  el.scrollLeft += event.deltaY;
};

const getHistoryData = async () => {
  loading.value = true;
  try {
    const data = await $SearchApiService.getSearchHistory();
    history.value = data.results;
  } catch (error) {
    console.error(`Error fetching:`, error);
  } finally {
    loading.value = false;
    await nextTick();
    // El contenidor només existeix quan hi ha resultats: s'observa en aquest moment
    if (scroller.value) {
      scroller.value.scrollLeft = 0;
      resizeObserver?.observe(scroller.value);
    }
    updateArrows();
  }
};

const getItemTranslation = (result) => foundItemTranslation(result, 'cat').cat;
const entityIcon = (result) => searchValues[result.entity]?.[1] || 'fa6-solid:magnifying-glass';

const handleClick = (result) => {
  try {
    const pathName = '/' + result.app.toLowerCase() + '/' + searchValues[result.entity][0] + '/';
    navigateTo({ path: pathName, query: { action: 'showDetail', id: result.item_id } });
  } catch (error) {
    console.error(error);
  }
};

onMounted(() => {
  if (typeof ResizeObserver !== 'undefined') resizeObserver = new ResizeObserver(updateArrows);
  getHistoryData();
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
});
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :loading="loading"
    @refresh="getHistoryData" @configure="emit('configure')" @remove="emit('remove')">
    <div v-if="loading && !history.length">
      <AtomsSkeleton class="w-full" :height="2" :has_icon="false" />
    </div>

    <div v-else-if="!history.length" class="text-center py-4">
      <p class="font-semibold text-slate-700">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500 mr-2" />
        {{ t('dashboard.no_recent_searches') }}
      </p>
      <p class="text-slate-500 text-sm">{{ t('dashboard.no_recent_searches_desc') }}</p>
    </div>

    <!-- `isolate`: els z-index de les fletxes i els degradats només valen dins d'aquest
         bloc, de manera que mai queden per sobre dels panells laterals (regions, z-10). -->
    <div v-else class="relative isolate">
      <!-- Degradats i fletxes només quan hi ha contingut amagat en aquella direcció -->
      <div v-show="canScrollLeft" class="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-white to-transparent z-[1]" />
      <div v-show="canScrollRight" class="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-white to-transparent z-[1]" />
      <button v-show="canScrollLeft" type="button" :aria-label="t('common.previous')" @click="scrollBy(-1)"
        class="absolute left-0 top-1/2 -translate-y-1/2 z-[2] h-7 w-7 rounded-full bg-white customers-shadow text-slate-500 hover:text-slate-700 flex items-center justify-center">
        <Icon name="fa6-solid:chevron-left" class="text-xs" />
      </button>
      <button v-show="canScrollRight" type="button" :aria-label="t('common.next')" @click="scrollBy(1)"
        class="absolute right-0 top-1/2 -translate-y-1/2 z-[2] h-7 w-7 rounded-full bg-white customers-shadow text-slate-500 hover:text-slate-700 flex items-center justify-center">
        <Icon name="fa6-solid:chevron-right" class="text-xs" />
      </button>

      <div ref="scroller" class="recent-scroller flex items-stretch gap-3 overflow-x-auto overflow-y-hidden snap-x snap-proximity px-1 pt-1 pb-3"
        @scroll.passive="updateArrows" @wheel="handleWheel">
        <template v-for="group in groups" :key="group.key">
          <div class="shrink-0 flex items-center snap-start">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-400 [writing-mode:vertical-rl] rotate-180">
              {{ dayLabel(group.key) }}
            </span>
          </div>
          <button v-for="result in group.results" :key="`${group.key}-${result.id || result.item_id}-${result.searched_at}`"
            type="button" @click="handleClick(result)"
            class="shrink-0 w-56 snap-start text-left flex flex-col gap-1 rounded-lg border border-slate-100 bg-white px-3 py-2.5 hover:border-sky-200 hover:bg-sky-50/40 transition-colors">
            <span class="flex items-center gap-2 text-xs text-slate-400 min-w-0">
              <Icon :name="entityIcon(result)" class="text-slate-400 shrink-0" size="14px" />
              <span class="truncate capitalize">{{ result.app }} / {{ result.entity.replace(/-/g, ' ') }}</span>
            </span>
            <span class="text-xs font-semibold text-slate-500 truncate">{{ getItemTranslation(result.found_field) }}</span>
            <span class="text-sm font-medium text-slate-700 line-clamp-2 break-words" v-html="result.found"></span>
            <span class="mt-auto text-xs text-slate-400 text-right">
              <TimeRelative :datetime="result.searched_at" />
            </span>
          </button>
        </template>
      </div>
    </div>
  </DashboardCardFrame>
</template>

<style scoped>
/* Barra de scroll fina: es veu que la fila es pot desplaçar sense que destaqui. */
.recent-scroller {
  scrollbar-width: thin;
  scrollbar-color: rgb(203 213 225) transparent;
}
.recent-scroller::-webkit-scrollbar {
  height: 6px;
}
.recent-scroller::-webkit-scrollbar-thumb {
  background-color: rgb(203 213 225);
  border-radius: 9999px;
}
.recent-scroller::-webkit-scrollbar-track {
  background: transparent;
}
</style>
