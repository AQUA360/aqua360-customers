<script setup>
import { formatDate } from '~/utils/date';

const { t } = useI18n();

// Lectures de control més recents que l'última lectura facturable, de la més nova a la més antiga
const props = defineProps({
  readings: {
    type: Array,
    default: () => []
  }
});

const latest = computed(() => props.readings[0] ?? null);
</script>

<template>
  <div v-if="latest" class="mt-1 flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-300 rounded px-2 py-0.5 w-fit"
    :title="t('billing_block.control_reading_not_billed_help')">
    <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500" />
    {{ t('billing_block.newer_control_reading', { value: latest.reading_value, date: formatDate(latest.reading_date) }) }}
    <span v-if="readings.length > 1" class="font-normal text-amber-600">
      {{ t('billing_block.newer_control_readings_more', { count: readings.length - 1 }) }}
    </span>
    <Icon name="fa6-solid:circle-info" class="text-amber-500 cursor-help" />
  </div>
</template>
