<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
const { t } = useI18n();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isGuide: {
    type: Boolean,
    default: false
  },
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'payment_commitments'
  },
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $PaymentCommitmentApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns below.
const exportColumns = computed(() => {
  if (props.isGuide) {
    return [
      { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
      { header: t('common.start_date'), value: (row) => row.start_date ? formatDate(row.start_date) : '', key: 'start_date' },
      { header: t('common.due_date'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
      { header: t('billing_block.paid'), value: (row) => Number(row.currently_paid ?? 0), key: 'currently_paid' },
      { header: t('common.total'), value: (row) => Number(row.amount ?? 0), key: 'amount' },
    ];
  }
  return [
    { header: t('billing_block.payment_date'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '', key: 'payment_date' },
    { header: t('common.payment_method'), value: (row) => row.payment_type?.name, key: 'payment_type' },
    { header: t('billing_block.paid'), value: (row) => Number(row.currently_paid ?? 0), key: 'currently_paid' },
  ];
});

const loading = ref(false)
const localData = ref(null);

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

const getData = async () => {
  loading.value = true
  try {
    const result = await $PaymentCommitmentApiService.getByDeposit(props.id, props.isGuide);
    localData.value = result.results;
    emit('update:count', localData.value.length);
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false;
  }
}

const gridTemplateColumns = computed(() => {
  if (!props.isGuide) return '1fr 1fr 1fr'
  return '100px 1fr 1fr 1fr 1fr';
});

onMounted(() => {
  getData()
})

watch(() => props.item, (newVal) => {
  localData.value = newVal
});

</script>
<template>
  <div v-if="loading" class="flex gap-3 mx-auto p-1">
    <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
    {{ $t('common.loading') }}...
  </div>
  <div v-else class="mt-2">
    <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800">

      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span v-if="isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
        <span v-if="isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.start_date') }} </span>
        <span v-if="isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.due_date') }} </span>
        <span v-if="!isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('billing_block.payment_date') }}
        </span>
        <span v-if="!isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.payment_method') }}
        </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('billing_block.paid') }} </span>
        <span v-if="isGuide" class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.total') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }">

        <div v-if="isGuide" class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" />
        </div>

        <div v-if="isGuide" class="footering text-slate-500 p-2 w-full">
          <p>{{ item.start_date ? formatDate(item.start_date) : '-' }}</p>
        </div>

        <div v-if="isGuide" class="footering text-slate-500 p-2 w-full">
          <p>{{ formatDate(item.due_date) }}</p>
        </div>

        <div v-if="!isGuide" class="footering text-slate-500 p-2 w-full">
          <p>{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</p>
        </div>

        <div v-if="!isGuide" class="footering text-slate-500 p-2 w-full">
          <p>{{ item.payment_type.name }}</p>
        </div>

        <div class="footering p-2 w-full"
        :class="{ 
          'text-red-500': item.currently_paid < 0,
          'text-slate-500': item.currently_paid >= 0
          }">
          <p>{{ formatMoneyWithCurrency(item.currently_paid) }}</p>
        </div>

        <div v-if="isGuide" class="footering text-slate-500 p-2 w-full">
          <p>{{ formatMoneyWithCurrency(item.amount) }}</p>
        </div>

      </div>
    </div>
    <div v-else>
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_records') }}
      </div>
    </div>
  </div>

</template>