<script setup>
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import ReadingMiniDetail from '~/components/molecules/ReadingMiniDetail.vue';
import ReadingDetail from '~/components/molecules/ReadingDetail.vue';

const props = defineProps({
  data: {
    type: Object,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  showContractReadings: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['show-detail']);

const { t } = useI18n();

const formatConsumption = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `${new Intl.NumberFormat('ca-ES', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(number)} m³`;
};

const contractIds = computed(() => {
  if (props.data?.is_general) {
    return (props.data.general_contracts || []).map((contract) => contract.id).filter(Boolean);
  }
  if (props.data?.contract?.id) {
    return [props.data.contract.id];
  }
  if (props.data?.contract_termination?.contract?.id) {
    return [props.data.contract_termination.contract.id];
  }
  return [];
});

const invoiceReadings = computed(() => props.data?.readings || []);

const contractsForReadings = computed(() => {
  if (props.data?.is_general) {
    return props.data.general_contracts || [];
  }
  if (props.data?.contract) {
    return [props.data.contract];
  }
  if (props.data?.contract_termination?.contract) {
    return [props.data.contract_termination.contract];
  }
  return [];
});

const showDetail = (component, id) => {
  emit('show-detail', component, id);
};
</script>

<template>
  <div class="consumption-detail mt-2 space-y-6">
    <!-- Consum de la factura -->
    <section>
      <h3 class="text-sm font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-200">
        {{ t('billing_block.info_consumption') }}
      </h3>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-1">
        <FieldDetail
          :label="t('billing_block.consumption')"
          :value="formatConsumption(data.consumption)"
        />
        <FieldDetail
          :label="t('billing_block.real_consumption')"
          :value="formatConsumption(data.real_consumption)"
        />
        <FieldDetail
          :label="t('billing_block.consumption_days')"
          :value="data.consumption_days ?? '-'"
        />
      </div>
    </section>

    <!-- Lectures utilitzades a la factura -->
    <section>
      <h3 class="text-sm font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-200">
        {{ t('billing_block.invoice_readings') }}
      </h3>
      <ReadingMiniDetail
        :item="invoiceReadings"
        :contracts="contractsForReadings"
        :isSubRegion="isSubRegion"
        @show-detail="showDetail"
      />
    </section>

    <!-- Historial de lectures del contracte -->
    <section v-if="showContractReadings && contractIds.length">
      <h3 class="text-sm font-semibold text-slate-700 mb-1 pb-1 border-b border-slate-200">
        {{ t('billing_block.contract_readings') }}
      </h3>
      <p class="text-xs text-slate-500 mb-2">
        {{ t('billing_block.contract_readings_help') }}
      </p>
      <div class="h-[40vh] overflow-y-auto border border-slate-100 rounded">
        <ReadingDetail
          :contract_ids="contractIds"
          :isSubRegion="isSubRegion"
          @show-detail="showDetail"
        />
      </div>
    </section>
  </div>
</template>
