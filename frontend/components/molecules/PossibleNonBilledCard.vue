<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  billing: Object,
  info: {
    type: Object,
    default: () => ({})
  },
  loading: Boolean,
  showLocationBreakdown: {
    type: Boolean,
    default: true
  },
  readingBatches: {
    type: Array,
    default: () => []
  },
  readingBatchesTitleKey: {
    type: String,
    default: 'billing_block.reading_batches'
  }
});

const emit = defineEmits(['open-missing-region']);

const causes = [
  { key: 'new_contracts', label: 'billing_block.cause_new_contract' },
  { key: 'no_readings', label: 'billing_block.cause_no_reading' },
  { key: 'no_batches', label: 'billing_block.cause_no_batch' },
  { key: 'no_billing', label: 'billing_block.cause_no_billing' },
  { key: 'new_termination', label: 'billing_block.cause_new_termination' },
  { key: 'no_route', label: 'billing_block.cause_no_route' },
  { key: 'no_meter', label: 'billing_block.cause_no_meter' },
  { key: 'no_price_rate', label: 'billing_block.cause_no_price_rate' },
  { key: 'excluded_billing', label: 'billing_block.cause_excluded_billing' },
  { key: 'block_billing', label: 'billing_block.cause_block_billing' },
  { key: 'unprocessed_invoice', label: 'billing_block.cause_unprocessed_invoice' }
];

const activeCauses = computed(() => causes.filter((cause) => (props.info?.[cause.key] || 0) > 0));

const locationBreakdown = [
  { key: 'missing_by_route', type: 'missing_by_route', label: 'route' },
  { key: 'missing_by_exploitation', type: 'missing_by_exploitation', label: 'exploitation' }
];
</script>

<template>
  <div v-if="!billing?.og_billing" class="w-full max-w-md mx-1 border border-gray-300 rounded-md bg-white h-fit">
    <div class="px-4 py-3 border-b border-slate-200 relative group">
      <div class="mt-1 flex items-center justify-between">
        <span class="font-bold">{{ t('billing_block.possible_non_billed') }}</span>
        <span v-if="!loading"
          class="inline-flex items-center justify-center rounded-full bg-rose-200 py-1 px-2 text-xs font-semibold text-rose-700 mr-5">
          {{ info.missing_contracts }}
        </span>
        <div v-else class="flex items-center gap-2 text-xs text-slate-500 mr-5">
          <Icon name="fa6-solid:spinner" class="animate-spin" />
        </div>
      </div>
      <div v-if="!loading && info.missing_contracts > 0"
        class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full rounded-tr-md absolute top-0 right-0 flex items-center justify-center"
        @click="emit('open-missing-region', 'all_contracts')">
        <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
      </div>
    </div>

    <ul v-if="showLocationBreakdown" class="p-2 space-y-1 border-b border-slate-200">
      <li v-for="(item, index) in locationBreakdown" :key="item.key"
        class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-1.5 relative group">
        <span class="text-sm font-medium text-slate-700">{{ t(item.label) }}</span>
        <span v-if="!loading"
          class="inline-flex items-center justify-center rounded-full bg-slate-200 py-1 px-2 text-xs font-semibold text-slate-700 mr-5">
          {{ info[item.key] }}
        </span>
        <div v-else class="text-xs text-slate-400 mr-5">
          <Icon name="fa6-solid:spinner" class="animate-spin" />
        </div>
        <div v-if="!loading && info[item.key] > 0"
          class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 absolute -right-2 flex items-center justify-center"
          :class="[index === 0 ? '-top-2' : '-top-0.5',
                   index === locationBreakdown.length - 1 ? '-bottom-2' : '-bottom-0.5']"
          @click="emit('open-missing-region', item.type)">
          <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
        </div>
      </li>
    </ul>

    <div v-if="activeCauses.length > 0" class="px-4 py-3">
      <p class="text-sm font-bold text-slate-700 mb-2">{{ t('billing_block.possible_reasons') }}</p>
      <ul class="space-y-1.5">
        <li v-for="cause in activeCauses" :key="cause.key"
          class="flex items-center justify-between rounded-md px-2 text-sm text-slate-600 transition-colors hover:bg-slate-50/70">
          <span class="font-medium">{{ t(cause.label) }}:</span>
          <span v-if="!loading" class="font-semibold text-slate-600">{{ info[cause.key] }}</span>
          <div v-else class="text-xs text-slate-500">
            <Icon name="fa6-solid:spinner" class="animate-spin" />
          </div>
        </li>
      </ul>
    </div>

    <div v-if="readingBatches.length > 0" class="border-t border-slate-200 px-4 py-3">
      <p class="mb-2 text-sm font-bold text-slate-700">{{ t(readingBatchesTitleKey) }}</p>
      <ul class="space-y-2">
        <li v-for="batch in readingBatches" :key="batch.id" class="rounded-md bg-slate-50 px-3 py-2">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 space-y-1">
              <p class="truncate text-sm font-semibold text-slate-700">{{ batch.name || batch.token }}</p>
              <p class="text-xs text-slate-500">
                {{ t('billing_block.batch_readings') }}: {{ batch.num_total_readings !== undefined ?
                  batch.num_total_readings : batch.num_readings || 0 }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <AtomsColorBadge :value="batch.status?.name || batch.status_name"
                :color="batch.status?.color || batch.status_color" />
              <AtomsRedirectButton :id="batch.id" :path="'/reading/reading-batches/'" />
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>

  <div v-else class="w-full max-w-md m-1 h-fit rounded-lg border border-slate-200 bg-white shadow-sm">
    <div class="border-b border-slate-100 px-4 py-3">
      <p class="text-xs font-bold uppercase tracking-wider text-slate-500">{{ t('billing_block.original_billing') }}</p>
    </div>
    <div class="space-y-3 px-4 py-3">
      <p class="text-sm font-bold text-slate-700">{{ t('informative_block.info_original_billing') }}</p>
      <div class="flex items-center justify-between gap-3 rounded-md bg-slate-50 px-3 py-2">
        <p class="text-sm font-semibold text-slate-700">{{ billing.og_billing.billing_missing_name }}</p>
        <AtomsRedirectButton :id="billing.og_billing.billing_missing_id" :path="'/billing/billing/'" />
      </div>
      <div class="space-y-1 py-2">
        <p class="text-sm font-bold text-slate-600">{{ t('billing_block.reading_batch') }}</p>
        <div
          class="flex items-center justify-between gap-3 text-sm text-slate-700 rounded-md border border-slate-100 px-3 py-2">
          <span class="font-semibold text-slate-800">{{ billing.og_billing.token }}</span>
          <AtomsRedirectButton :id="billing.og_billing.id" :path="'/reading/reading-batches/'" />
        </div>
      </div>
    </div>
  </div>
</template>
