<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed']);
const { $AdjustmentApiService, $BonificationApiService, $PriceIntervalStretchApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const bonification = ref(null);
const stretch = ref(null);
const SubRegion = ref(props.isSubRegionOpen);


const getData = async () => {
  pending.value = true;
  try {
    const result = await $AdjustmentApiService.getDetail(props.id);
    data.value = result;
    getBonification();
    getStretch();
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const getStretch = async () => {
  try {
    if (data.value.adjustment_interval) {
      const result = await $PriceIntervalStretchApiService.getDetail(data.value.adjustment_interval.price_interval_stretch);
      stretch.value = { value: result.id, name: result.token }
    }
  } catch (err) {
    console.error(err);
  }
}

const getBonification = async () => {
  try {
    if (data.value.bonification) {
      const result = await $BonificationApiService.getDetail(data.value.bonification);
      bonification.value = { value: result.id, name: result.bonification_type.name }
    }
  } catch (err) {
    console.error(err);
  }
}



watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

getData();

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component.component;
  regionDetailId.value = component.id;
  showSubRegion();
}


</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion }">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('pricing_block.adjustment_detail') + ': ' + data.token }}</H1Region>
      </div>

      <div v-if="data" id="item_data" :data-rel=id class="my-3">

        <div id="wrapper" class="text-base">
          <div role="row" class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("common.range")' :value=data.line_item_type_name />
          </div>
          <div role="row" class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("common.operation")' :value=data.operation.name />
            <FieldDetail v-if="data.variable_calculation.name != ''" :label='$t("variable")'
              :value=data.variable_calculation.name />
          </div>

          <div v-if="data.adjustment_interval || data.quantity" role="row" class="grid grid-cols-2 gap-3">
            <FieldDetail v-if="!data.adjustment_interval" :label='$t("common.total")' :value=data.quantity />
            <FieldDetail v-else :label='$t("common.total")' :value=data.adjustment_interval.coefficient />
            <FieldDetail v-if="data.adjustment_interval" :label='$t("pricing_block.stretch")' :value=stretch.name />
          </div>

          <hr v-if="data.bonification" class="my-2" />
          <div role="row" v-if="data.bonification" class="grid gap-3">
            <FieldDetail :label='$t("contract_block.bonification")' :value=bonification?.name />
          </div>

          <hr v-if="data.variable_contract" class="my-2" />
          <div role="row" v-if="data.variable_contract" class="grid gap-3">
            <FieldDetail :label='$t("variable")' :value=data.variable_contract?.name />
          </div>

          <hr v-if="data.conditions && data.conditions.length > 0" class="my-2" />
          <div role="row" v-if="data.conditions && data.conditions.length > 0" class="grid gap-3">
            <fieldset class="border border-gray-300 rounded p-4 bg-gray-50 mb-3">
              <legend class="px-2 font-medium text-slate-800">{{ $t('common.conditionals') }}:</legend>
              <AtomsAdjustmentConditionDetail v-for="condition in data.conditions" 
              :key="condition.id" :item="condition" :allowEdit="false"/>
            </fieldset>
          </div>

        </div>

      </div><!-- end if data -->



    </div><!-- end if pending -->

  </div><!-- end region__content -->
</template>
