<script setup>
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';

const {t} = useI18n();

const emit = defineEmits(['show-detail']);

const props = defineProps({
  price_rate: Object,
  variables: {
    type: Array,
    default: null
  },
  isContractSubregion: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const objectPermissions = ref(null);
const { $PriceRateApiService } = useNuxtApp();

const showDetail = function (component, id) {
  emit('show-detail', component,id)
}


onMounted(async()=> {
  objectPermissions.value = await checkPermission($PriceRateApiService);
})
</script>
<template>
  <div class="py-2" v-if="price_rate">
    <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{ price_rate.product?.name || $t('pricing_block.no_product') }} - </span> 
    <button v-if="!isSubRegion && objectPermissions?.can_view" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
    @click="showDetail('PriceRateRegion', price_rate.id)">{{ price_rate.name }} </button>
    <span v-else>{{ price_rate.name }}</span>
    <div v-if="price_rate.billing_range_active" class="ml-2 text-slate-400">
      <!-- <span>{{ price_rate.billing_range_active.name }} <span class="text-slate-700 text-sm"> {{ formatDate(price_rate.billing_range_active.start) }}</span></span> -->
      <div class="ml-5 mt-2" v-if="price_rate.billing_range_active.line_item_types && price_rate.billing_range_active.line_item_types.length > 0">
        <div v-for="line_item_type in price_rate.billing_range_active.line_item_types" class="mb-2 max-w-xl text-slate-700 rounded shadow">
          <!-- {{ line_item_type.name }} -->
          <details>
            <summary class="text-sm border-b p-2 text-slate-500 hover:bg-slate-200 active:bg-slate-300 cursor-pointer">{{ line_item_type.name }}</summary>
            <MoleculesLineItemTypeDetail @show-detail="showDetail" :id="line_item_type.id" :data="line_item_type" :variables="props.variables" :isContractSubregion="props.isContractSubregion" :isSubRegion="isSubRegion" :isSubRegionOpen="true" :hideActions="true" class="mt-1 pt-2 bg-sky-50" />
          </details>
        </div>
      </div>
    </div>
  </div>
</template>