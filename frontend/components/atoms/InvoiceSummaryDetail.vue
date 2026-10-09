<!-- components/atoms/InvoiceSummaryDetail.vue -->

<template>
  <div class="divide-y divide-slate-200">
    <section v-for="(value, key) in billingSummary" :key="key" class="py-4 first:pt-0 last:pb-0">
      <div :class="headerClass(value)">
        <h3 class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {{ t(key) }}
        </h3>
        <p v-if="!isNestedGroup(value)" class="text-sm font-semibold tabular-nums text-slate-900">
          {{ scalarValue(value) }}
        </p>
      </div>

      <div v-if="isNestedGroup(value)">
        <!-- <p v-if="displayEntries(value).length === 0" class="px-2 text-sm text-slate-400">
          {{ t('common.no_results') }}
        </p> -->
        <div>
          <div v-for="entry in visibleSecondLevelEntries(value, key)" :key="`${key}-${entry.key}`"
            :class="rowClass(entry)">
            <div class="min-w-0 truncate">
              {{ secondLevelLabel(entry.key) }}
            </div>

            <div v-if="isPlainObject(entry.value)" class="grid grid-cols-2 gap-2">
              <template v-for="item in displayEntries(entry.value)" :key="item.key">
                <div class="text-right tabular-nums">
                  {{ isHeaderRow(entry) ? t(item.key) : item.key }}
                </div>
                <div class="text-right tabular-nums">
                  {{ isHeaderRow(entry) ? t(item.value) : item.value }}
                </div>
              </template>
            </div>
            <div v-else class="text-right tabular-nums">
              {{ entry.value }}
            </div>
          </div>
        </div>

        <div v-if="secondLevelHasMore(value, key) || secondLevelIsExpanded(value, key)" class="mt-2 flex gap-3">
          <button v-if="secondLevelHasMore(value, key)" type="button"
            class="inline-flex items-center gap-1 text-xs font-semibold text-blue-500 hover:text-blue-800"
            @click="expandSecondLevel(key)">
            <Icon name="fa6-solid:chevron-down" class="h-3 w-3" />
            {{ t('common.show_all_entries') }}
          </button>
          <button v-if="secondLevelIsExpanded(value, key)" type="button"
            class="inline-flex items-center gap-1 text-xs font-semibold text-blue-500 hover:text-blue-800"
            @click="collapseSecondLevel(key)">
            <Icon name="fa6-solid:chevron-up" class="h-3 w-3" />
            {{ t('common.show_less') }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

defineProps({
  billingSummary: Object
});

const expandedSecondLevel = ref(new Set());

const DEFAULT_LIMIT = 5;
const META_PREFIX = '__';

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function displayEntries(obj) {
  if (!isPlainObject(obj)) return [];
  return Object.entries(obj)
    .filter(([key]) => !String(key).startsWith(META_PREFIX))
    .map(([key, value]) => ({ key, value }));
}

function groupLimit(value) {
  if (isPlainObject(value) && Number.isFinite(value.__limit)) {
    return value.__limit;
  }
  for (const entry of displayEntries(value)) {
    if (isPlainObject(entry.value) && Number.isFinite(entry.value.__limit)) {
      return entry.value.__limit;
    }
  }
  return DEFAULT_LIMIT;
}

function isHighlighted(value) {
  return isPlainObject(value) && value.__highlight === true;
}

function scalarValue(value) {
  if (!isPlainObject(value)) return value;
  if (isHighlighted(value) && '__value' in value) return value.__value;
  return t('common.no_results');
}

function isNestedGroup(value) {
  return isPlainObject(value) && displayEntries(value).length > 0;
}

function headerClass(value) {
  if (isHighlighted(value)) {
    return 'mb-2 flex items-baseline justify-between gap-4 rounded-md bg-slate-100 px-2.5 py-1.5';
  }
  return 'mb-2 flex items-baseline justify-between gap-4';
}

function isHeaderRow(entry) {
  return entry.key === '' || entry.key == null;
}

function secondLevelLabel(key) {
  if (key === '' || key == null) return '';
  return key === 'None' ? t(key) : key;
}

function rowClass(entry) {
  if (isHeaderRow(entry)) {
    return 'grid grid-cols-[minmax(0,1.5fr)_1fr] items-center gap-x-3 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400';
  }
  if (isHighlighted(entry.value)) {
    return 'mb-3 last:mb-0 grid grid-cols-[minmax(0,1.5fr)_1fr] items-center gap-x-3 rounded bg-slate-100 px-2.5 py-1.5 text-sm font-semibold text-slate-900';
  }
  return 'grid grid-cols-[minmax(0,1.5fr)_1fr] items-center gap-x-3 px-2 py-1 text-sm text-slate-700';
}

function visibleSecondLevelEntries(value, groupKey) {
  const entries = displayEntries(value);
  const limit = groupLimit(value);
  if (entries.length <= limit || expandedSecondLevel.value.has(groupKey)) {
    return entries;
  }
  return entries.slice(0, limit);
}

function secondLevelHasMore(value, groupKey) {
  const limit = groupLimit(value);
  return displayEntries(value).length > limit && !expandedSecondLevel.value.has(groupKey);
}

function secondLevelIsExpanded(value, groupKey) {
  const limit = groupLimit(value);
  return displayEntries(value).length > limit && expandedSecondLevel.value.has(groupKey);
}

function expandSecondLevel(groupKey) {
  expandedSecondLevel.value = new Set([...expandedSecondLevel.value, groupKey]);
}

function collapseSecondLevel(groupKey) {
  const next = new Set(expandedSecondLevel.value);
  next.delete(groupKey);
  expandedSecondLevel.value = next;
}
</script>
