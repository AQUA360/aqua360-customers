<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';

const { $AddressHelper, $BillingRangeApiService, $LineItemTypeApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isDetail: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  data: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['show-detail']);

// Variables locals
const localData = ref(props.data ? { ...props.data } : null);
const lineItems = ref([]);
const isLoading = ref(false);
const error = ref(null);

// Funció per mostrar detalls
const showDetail = (component, id) => {
  emit('show-detail', { component: component, id: id });
};

// Funció per obtenir les dades des de l'API
const fetchData = async () => {
  isLoading.value = true;
  try {
    if (props.id) {
      const detail = await $BillingRangeApiService.getDetail(props.id);
      localData.value = detail;
    } else {
      localData.value = null;
    }

    //getLineItemTypes()
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }


};

const getLineItemTypes = async () => {
  const response = await $LineItemTypeApiService.getByBillingRange(props.id)
  lineItems.value = response.results
}

// Executar la funció quan el component es munta
onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
  getLineItemTypes()

});

// Observa canvis en l'id per tornar a carregar les dades si cal
watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2"> {{ $t('common.loading') }}... </span>
  </div>

  <div v-else-if="error" class="error">
    <!-- Gestiona l'error segons sigui necessari -->
    {{ $t('common.error_load') }}
  </div>
  <div v-else-if="localData && !isDetail">
    <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
      <FieldDetail :label="t('common.name')" :value="localData.name"></FieldDetail>
      
    </div>
    
    <hr class="mb-2" />
    <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
      <FieldDetail :label='$t("price_rate")'>
        <span v-if="localData.price_rate && isSubRegion">{{ localData.price_rate.name }}</span>
        <div v-if="!isSubRegion && localData.price_rate" class="flex gap-2">
          <button @click="showDetail('PriceRateRegion', localData.price_rate.id)"
          class="text-start text-sky-500 underline">
          <span v-if="localData.price_rate.id">{{ localData.price_rate.name }}</span>
        </button>
        <AtomsRedirectButton :id="localData.price_rate.id" :path="'/pricing/price-rates/'" />
      </div>
    </FieldDetail>
    <FieldDetail :label="$t('common.start_date')" :value="formatDate(localData.start)"></FieldDetail>
    
    </div>
    <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
      <FieldDetail :label='$t("pricing_block.publication_detail")'>
        <span v-if="isSubRegion">{{ localData.publication ? localData.publication.name : '-' }}</span>
        <button v-else @click="showDetail('PublicationRegion', localData.publication.id)"
        class="text-start text-sky-500 underline">
        <span>{{ localData.publication ? localData.publication.name : '-' }}</span>
      </button>
    </FieldDetail>
    <FieldDetail :label="$t('common.end_date')" :value="localData.end ? formatDate(localData.end) : '-'"></FieldDetail>
  </div>
  
  <!--Concepts-->
  <!-- <div v-if="lineItems && lineItems.length>0">
    <fieldset class="mb-3 border px-3 py-2 bg-sky-50">
      <legend class="px-3 font-semibold bg-white shadow">{{ t('Conceptes Tipus') }}</legend>
      <div v-for="lineItem in lineItems" :key="lineItem.id">
          <FieldDetail :label="lineItem.name"
            :value="lineItem.price ? lineItem.price.toFixed(2) : lineItem.proportional_price.toFixed(2)"></FieldDetail>
          </div>
        </fieldset>
        
        
      </div> -->
      
    </div>
    <div v-else-if="localData && isDetail">
      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label="t('common.name')" :value="localData.name"></FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label='$t("pricing_block.publication_detail")'>
          <span v-if="isSubRegion">{{ localData.publication ? localData.publication.name.substring(0, 25) + '...' : '-'
          }}</span>
        <button v-else @click="showDetail('PublicationRegion', localData.publication.id)"
        class="text-start text-sky-500 underline">
        <span>{{ localData.publication ? localData.publication.name : '-' }}</span>
      </button>
    </FieldDetail>
    <FieldDetail :label="$t('common.start_date')" :value="formatDate(localData.start)"></FieldDetail>
  </div>
</div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
