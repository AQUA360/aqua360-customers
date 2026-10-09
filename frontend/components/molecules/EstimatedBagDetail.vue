<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import IBAN from '~/components/atoms/IBAN.vue';

const { $AddressHelper } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['showDetail']);
const { $EstimatedBagApiService } = useNuxtApp();

const pending = ref(false);
const localData = ref(props.data ? props.data : null);

const getData = async () => {
  pending.value = true;
  try {
    const data = await $EstimatedBagApiService.getDetail(props.id);
    localData.value = data;
  } catch (error) {
    console.error(error);
  } finally {
    pending.value = false;
  }
}

function removeUselessZero(value) {
  if (value.includes('.')) {
    return value.replace(/\.?0+$/, '');
  }
  return value;
}

onMounted(() => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.id, () => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.data, () => {
  localData.value = props.data;
}, { immediate: true, deep: true });

const showDetail = (component, id) => {
  emit('showDetail', component, id);
}


</script>
<template>
  <div id="wrapper" class="text-base">
    <div role="row" class="grid grid-cols-2 gap-3">
      <!-- <FieldDetail :label='$t("Ident.")' :value=localData.token /> -->
      <FieldDetail :label='$t("contract")' :value="localData.contract_token" class="items-center" />
      <FieldDetail :label='$t("common.short_supply")' :value="localData.supply_point.token" class="items-center" />
      <FieldDetail :label='$t("contract_block.consumption_bag_total")' :value="removeUselessZero(localData.total_consumption) + ' m3'" />
    </div>
    <hr class="my-2">
    <div class="h-[60vh] overflow-y-auto scrollbar-hide">
      <div v-for="movement in localData.movements"
        class="grid grid-cols-[50px,1fr] items-center py-1 px-2 border rounded-lg mb-2"
        :class="{ 'bg-green-50 border-green-500': movement.is_positive, 'bg-red-50 border-red-500': !movement.is_positive }">
        <Icon name="fa6-solid:angles-right" class="text-slate-400" />
        <div class="grid grid-cols-2 flex items-center mt-1">
          <FieldDetail :label='movement.is_positive ? $t("common.in_date") : $t("common.out_date")'
            :value=formatDate(movement.movement_date)></FieldDetail>
          <FieldDetail :label='movement.is_positive ? $t("billing_block.consumption_estimated") : $t("billing_block.consumption")'
            :value="removeUselessZero(movement.amount) + ' m3'"></FieldDetail>
          <FieldDetail v-if="movement.reading" :label="t('common.origin')" :value="movement.reading.origin" />
          <FieldDetail v-if="movement.reading" :label="t('billing_block.leak_estimated')" :value="movement.reading.leak_value ?
            movement.reading.leak_value + ' m³' : t('billing_block.no_leak')" />
          <FieldDetail v-if="movement.invoice" :label='$t("invoice")'>
            <button @click="showDetail('InvoiceRegion', movement.invoice.id)"
              class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">
              {{ movement.invoice.token }}
            </button>
          </FieldDetail>
          <!-- <FieldDetail v-if="!(movement.reading && movement.invoice)" :label="t('billing_block.deleted_reading')" :value="''" /> -->
        </div>
      </div>
      <div v-if="localData.movements.length === 0">
        <p class="text-center text-slate-500">{{ $t('common.no_records') }}</p>
      </div>
    </div>
  </div>
</template>
