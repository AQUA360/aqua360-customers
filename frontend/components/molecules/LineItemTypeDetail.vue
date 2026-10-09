<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import AdjustmentList from '~/components/molecules/AdjustmentList.vue';
import { AdjustmentTypeChoices } from '~/utils/pricing';

const { $LineItemTypeApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  price_rate_id: {
    type: Number,
    default: null
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  disabled: Boolean,
  hideActions: Boolean,
  variables: {
    type: Array,
    default: null
  },
  isContractSubregion: {
    type: Boolean,
    default: false
  },
  in_detail: {
    type: Boolean,
    default: false
  },
  in_adjustment: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: true
  }
});


const emit = defineEmits(['show-detail', 'edit-adjustment', 'create-adjustment']);

const localData = ref(props.data ? { ...props.data } : {});
const adjustments = ref([])
const isLoading = ref(false);
const error = ref(null);

const variables = ref([])
const adjustmentChoices = ref(AdjustmentTypeChoices);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const getData = async () => {
  isLoading.value = true;

  try {
    if (props.isContractSubregion) {
      props.variables.forEach(item => {
        variables.value.push(item.name)
      })
    }

  } catch (err) {
    console.error('Error obtenint les dades:', err);
  }

  try {
    const detail = await $LineItemTypeApiService.getDetail(props.id);
    localData.value = detail;
    localData.value.adjustments.sort((a, b) => a.position - b.position).forEach(item => {
      if (props.isContractSubregion) {
        if (!item.variable_contract) {
          adjustments.value.push(item)
        } else {
          if ((variables.value.indexOf(item.variable_contract?.name) !== -1)) {
            adjustments.value.push(item)
          }
        }
      } else {
        adjustments.value.push(item)
      }


    })
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
}

const createAdjustment = async () => {
  let price_rate_id = null;
  if (props.price_rate_id) {
    price_rate_id = props.price_rate_id
  } else if (localData.value.billing_range.price_rate) {
    price_rate_id = localData.value.billing_range.price_rate.id
  }
  const url = new URL('/pricing/adjustments/add', window.location.origin);
  url.searchParams.set('line_item_type_id', props.id);
  url.searchParams.set('price_rate_id', props.price_rate_id || localData.value.billing_range.price_rate.id);
  url.searchParams.set('interval_id', localData.value.price_interval?.id || null);
  url.searchParams.set('variable_id', localData.value.price_variable?.id || null);

  window.open(url.toString(), '_blank');
}


const editAdjustment = function (id, new_tab) {
  if (new_tab) {
  const url = new URL('/pricing/adjustments/add', window.location.origin);
    url.searchParams.set('line_item_type_id', props.id);//
    url.searchParams.set('interval_id', localData.value.price_interval?.id || null);
    url.searchParams.set('variable_id', localData.value.price_variable?.id || null);
    url.searchParams.set('price_rate_id', props.price_rate_id);//
    url.searchParams.set('adjustment_id', id);//

    window.open(url.toString(), '_blank');
  } else {
    return navigateTo(`/pricing/adjustments/add?adjustment_id=${id}&line_item_type_id=${props.id}&interval_id=${localData.value.price_interval?.id || null}&variable_id=${localData.value.price_variable?.id || null}&price_rate_id=${props.price_rate_id}`);
  }
}

const editLineItemType = function (element) {
  const url = new URL(`/pricing/line-item-types/edit/${element.id}`, window.location.origin);
  url.searchParams.set('pr_id', props?.price_rate_id);
  url.searchParams.set('br_id', element.billing_range.id);
  url.searchParams.set('inprod', true);

  window.open(url.toString(), '_blank');
}


const getPrice = function () {
  if (localData.value.price != null) {
    return localData.value.price.toFixed(2)
  } else if (localData.value.proportional_price != null) {
    return localData.value.proportional_price.toFixed(2)
  }
  return '-'
}



onMounted(() => {
  getData()
});

</script>

<template>
  <div v-if="!isLoading" id="wrapper" class="text-base py-2 px-4">
    <div v-if="!hideActions" role="row" class="">
      <FieldDetail :label='$t("pricing_block.line_item_type")'>
        <button v-if="in_detail && !in_adjustment && !isSubRegion" @click="showDetail('LineItemTypeRegion', localData.id)"
          class="text-start text-sky-500 underline">
          <span>{{ localData.name }} {{ localData.token }}</span>
        </button>
        <span v-else-if="in_adjustment">
          {{ localData.name }} {{ localData.token }}
          <button class="px-2 py-1 text-gray-500  border rounded hover:bg-slate-300 hover:border-slate-500" @click="editLineItemType(localData)">
            <Icon name="fa6-solid:pencil"/></button>
        </span>
        <span v-else>{{ localData.name }} {{ localData.token }}</span>
      </FieldDetail>
      <FieldDetail :label='$t("common.range")' :value=localData?.billing_range?.token />
    </div>
    <hr v-if="!hideActions" class="my-2" />
    <!-- <div v-if="localData.code || localData.article" role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail v-if="localData.code" :label='$t("pricing_block.article_code")' :value='localData.code' />
      <FieldDetail v-if="localData.article" :label='$t("pricing_block.account_code")' :value='localData.article.token' />
    </div> -->
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail class="italic" v-if="localData.formula" :label='$t("common.price")' :value='localData.formula' />
      <FieldDetail v-else-if="!localData.price_interval && !localData.price_variable" :label='$t("common.price")' :value='getPrice()' />
      <FieldDetail v-else :label='$t("common.price")'>
        <button
          v-if="!in_adjustment && (((localData.price_interval || localData.price_variable) && !isSubRegion) || ((localData.price_interval || localData.price_variable) && props.isContractSubregion))"
          @click="showDetail('PriceIntervalRegion', localData.price_interval.id)"
          class="text-start text-sky-500 underline">
          <span>{{ localData.price_interval ? localData.price_interval.token : localData.price_variable.token }}</span>
        </button>
        <span v-else-if="((localData.price_interval || localData.price_variable) && isSubRegion) || in_adjustment">{{ localData.price_interval ? localData.price_interval.token : localData.price_variable.token }}</span>
      </FieldDetail>
      <FieldDetail :label='$t("common.quantity")' :value=localData.quantity?.name />
    </div>

    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("billing")' :value="localData.billing_period?.name" />
      <FieldDetail v-if="localData.tax && localData.tax.percent" :label='$t("taxes")'
        :value='localData.tax.name + " (" + localData.tax.percent + "%)"' />
      <!-- <FieldDetail v-else :label='$t("taxes")'
        :value='t("billing_block.no_taxes")' /> -->
      <FieldDetail v-else :label='$t("taxes")' :value='t("billing_block.no_taxes")' />
      <FieldDetail :label='$t("pricing_block.billing_registration")' :class="{'opacity-50': !localData.active_choice}"
      :value='localData.active_choice? t(adjustmentChoices[localData.active_choice]) : "-" ' />
      <FieldDetail :label='$t("pricing_block.billing_termination")' :class="{'opacity-50': !localData.inactive_choice}"
      :value='localData.inactive_choice? t(adjustmentChoices[localData.inactive_choice]) : "-" ' />
    </div>
    <hr class="my-2" />
    
    <AdjustmentList :isContractSubregion="props.isContractSubregion" :adjustments="adjustments"
      :price_rate_id="props.price_rate_id"
      :isSubRegion="props.isSubRegion" :in_detail="props.in_detail" :hideActions="props.hideActions"
      @show-detail="showDetail" @edit-adjustment="editAdjustment" @create-adjustment="createAdjustment" :canChange="canChange" />

  </div>

</template>
