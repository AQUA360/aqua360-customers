<script setup>
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  item: Object, //contracts
  is_request: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
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
    default: 'contracts'
  },
});
const emit = defineEmits(['show-detail', 'refresh']);
const selectedId = ref(null)

const showDetail = function (component, id, sel_id) {
  selectedId.value = sel_id
  emit('show-detail', component, id);
}

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('contract'), value: (row) => row.token, key: 'token' },
  { header: t('supply_point'), value: (row) => row.supply_point, key: 'supply_point' },
  { header: t('contract_block.holder'), value: (row) => [row.holder_token, row.holder_name, row.holder_surname].filter(Boolean).join(' ') },
]);

const gridTemplateColumns = '100px 1fr 2fr 1fr';

const localData = ref([]);

watch(
  () => props.item,
  (newVal) => {
    localData.value = newVal ?? [];
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
    <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName"
      :sheet-name="t('contract')" />
  </div>
  <div v-if="localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
    <div class="group grid bg-gray-100 border-b text-left" :style="{ gridTemplateColumns }">
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('common.status') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('contract') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('supply_point') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('contract_block.holder') }}</span>
    </div>
    <div
      v-for="item in localData"
      :key="item.id"
      class="border-b group grid text-sm leading-4 transition-all duration-100"
      :style="{ gridTemplateColumns }"
      :class="{ 'bg-yellow-50': item.id === selectedId }"
    >
      <div class="footering text-slate-500 p-2 w-full">
        <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <button
          v-if="!props.isSubRegion"
          class="text-start text-sky-500 underline"
          @click="showDetail(is_request ? 'ContractRequestRegion' : 'ContractRegion', item.id, item.id)"
        >
          {{ item.token }}
        </button>
        <span v-else>{{ item.token }}</span>
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <button
          v-if="!props.isSubRegion && item.supply_point_default_id"
          class="text-start text-sky-500 underline"
          @click="showDetail('SupplyPointRegion', item.supply_point_default_id, item.id)"
        >
          {{ item.supply_point }}
        </button>
        <span v-else>{{ item.supply_point }}</span>
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <button v-if="!props.isSubRegion && item.holder_id" @click="showDetail('PersonRegion', item.holder_id, item.id)">
          <p class="text-start text-sky-500 underline">
            {{ item.holder_token }}
          </p>
          <p class="text-xs text-slate-500 no-underline">{{ item.holder_name }} {{ item.holder_surname }}</p>
        </button>
        <template v-else>
          <p>{{ item.holder_token }}</p>
          <p v-if="item.holder_name || item.holder_surname" class="text-xs text-slate-500">
            {{ item.holder_name }} {{ item.holder_surname }}
          </p>
          <p v-else-if="item.holder" class="text-xs text-slate-500">{{ item.holder }}</p>
        </template>
      </div>
    </div>
  </div>
  <div v-else class="footering text-slate-500 p-2">
    {{ t('common.no_records') }}
  </div>
</template>
