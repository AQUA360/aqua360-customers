<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  errors: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['fix-error']);

const count = computed(() => props.errors?.length || 0);

const contextLabel = (err) => {
  const parts = [];
  if (err.reading_id) parts.push(`${t('billing_block.reading_id') || 'Lectura'} #${err.reading_id}`);
  if (err.supply_point_id) parts.push(`${t('supply_point') || 'Subministrament'} #${err.supply_point_id}`);
  if (err.contract_id) parts.push(`${t('contract') || 'Contracte'} #${err.contract_id}`);
  if (err.meter_id) parts.push(`${t('meter') || 'Comptador'} #${err.meter_id}`);
  return parts.join(' · ');
};

const canFix = (err) => err.fixable && err.reading_id && err.fix_field === 'reading_date';
</script>

<template>
  <div v-if="count > 0" class="mb-4 rounded-md border border-yellow-300 bg-yellow-50 text-slate-700">
    <div class="flex items-center gap-2 px-4 py-3">
      <Icon name="fa6-solid:triangle-exclamation" class="text-yellow-500 shrink-0" />
      <span class="font-semibold text-sm">
        {{ t('billing_block.partial_processing_errors_title', { count }) }}
      </span>
    </div>
    <details class="px-4 pb-3">
      <summary class="cursor-pointer text-sm text-slate-500 hover:text-slate-700 select-none">
        {{ t('billing_block.partial_processing_errors_show_detail') }}
      </summary>
      <ul class="mt-2 divide-y divide-yellow-200 max-h-64 overflow-y-auto">
        <li v-for="(err, idx) in errors" :key="idx" class="py-2 text-sm flex items-start justify-between gap-3">
          <div>
            <div class="font-medium text-slate-600">{{ contextLabel(err) }}</div>
            <div class="text-slate-500">
              {{ err.message || err.error }}
            </div>
          </div>
          <button v-if="canFix(err)"
            class="shrink-0 text-xs font-semibold text-sky-600 hover:text-sky-800 border border-sky-300 rounded-md px-2 py-1 whitespace-nowrap"
            @click="emit('fix-error', err)">
            {{ t('billing_block.partial_processing_errors_fix') }}
          </button>
        </li>
      </ul>
    </details>
  </div>
</template>
