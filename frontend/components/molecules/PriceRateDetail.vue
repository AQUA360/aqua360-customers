<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

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
  disabled: Boolean,
});

const emit = defineEmits(['show-detail', 'clickChangeStatus']);

const activeBillingRange = ref(null);
const activeBillingRangeId = ref(null);

const showDetail = function (component, id) {
  emit('show-detail', { component: component, id: id })
}

onMounted(() => {
  activeBillingRange.value = props.data.billing_range_active|| null;
  activeBillingRangeId.value = activeBillingRange.value?.id || null;
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("common.name")' :value=data.name />
    </div>
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("product")'>
        <span v-if="isSubRegion && data.product">{{ data.product.token }}</span>
        <button v-else-if="!isSubRegion && data.product" @click="showDetail('ProductRegion', data.product.id)" class="text-start text-sky-500 underline">
          <span >{{ data.product.name }}</span>
        </button>
      </FieldDetail>
    </div>

  </div>


  <div v-if="activeBillingRange"  class="mt-4">
    <div>
      <legend class="px-3 font-semibold bg-white shadow w-40">{{ $t('pricing_block.current_billing_range') }}</legend>
      <!-- <div v-for="br in data.billing_ranges" :key="br.id">
        <div v-if="!br.end" class="w-full border border-gray-300 rounded p-4  bg-white mb-2">
          <MoleculesBillingRangeDetail :id="br.id" :data="br" @show-detail="showDetail" :isSubRegion="true" :isDetail="true" />
        </div>
      </div> -->
      <div class="w-full border border-gray-300 rounded p-4  bg-white mb-2">
          <MoleculesBillingRangeDetail :id="activeBillingRangeId" :data="activeBillingRange" @show-detail="showDetail" :isSubRegion="true" :isDetail="true" />
        </div>
    </div>
  </div>


</template>
