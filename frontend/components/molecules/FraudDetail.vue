<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $FraudApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $FraudApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.identification")' :value=localData.token />
      <FieldDetail :label='$t("customer_service_block.detection")' :value="formatDate(localData.detection_date)" />
      
      <FieldDetail class="col-span-2" :label='$t("common.type")' :value="localData.type.name">
        <!-- <AtomsColorBadge :value=localData.type.name :color=localData.type.color /> -->
      </FieldDetail>
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <div v-if="localData.is_dismissed" class="col-span-2 mb-1 text-right">
        <AtomsColorBadge :value="t('common.dismissed')" :color="null" />
      </div>

      <hr class="my-2 col-span-2" />

      <FieldDetail :label="$t('contract')">
        <div v-if="!isSubRegion && localData.contract" class="flex gap-2">
          <button @click="showDetail('ContractRegion', localData.contract.id)"
            class="text-start text-sky-500 underline">{{ localData.contract.token }}</button>
          <AtomsRedirectButton :id="parseInt(localData.contract.id)" :path="'/contract/contracts/'" />
        </div>
        <span v-else>{{ localData.contract ? localData.contract.token : '-' }}</span>
      </FieldDetail>
      <FieldDetail :label="$t('common.short_supply')">
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('SupplyPointRegion', localData.supply_point.id)"
            class="text-start text-sky-500 underline">
            {{ localData.supply_point.address_complete ? localData.supply_point.address_complete :
              localData.supply_point.token }}
          </button>
          <AtomsRedirectButton :id="parseInt(localData.supply_point.id)" :path="'/service/supplypoints/'" />
        </div>
        <span v-else>
          {{ localData.supply_point.address_complete ? localData.supply_point.address_complete :
            localData.supply_point.token }}
        </span>
      </FieldDetail>

      <FieldDetail class="col-span-2" v-if="localData.contract" :label="$t('contract_block.holder')">
        <div v-if="!isSubRegion && localData.contract" class="flex gap-2">
          <button @click="showDetail('PersonRegion', localData.contract.holder_id)"
            class="text-start text-sky-500 underline">{{
              localData.contract.holder }} ({{ localData.contract.holder_token }})</button>
          <AtomsRedirectButton :id="parseInt(localData.contract.holder_id)" :path="'/contract/persons/'" />
        </div>
        <span v-else>{{ localData.contract.holder }} ({{ localData.contract.holder_token }})</span>
      </FieldDetail>


    </div>

  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
