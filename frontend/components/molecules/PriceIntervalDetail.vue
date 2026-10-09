<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { $PriceIntervalApiService } = useNuxtApp();
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


const emit = defineEmits(['show-detail']);

const localData = ref(props.data ? { ...props.data } : null);
const isLoading = ref(false);
const error = ref(null);



const getData = async () => {
  isLoading.value = true;
  try {
    const detail = await $PriceIntervalApiService.getDetail(props.id);
    localData.value = detail;
    //getLineItemTypes()
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
}
const getInterval = function (element) {
  if(element.start_stretch){
    return `${t('common.from')} ${element.start_stretch} ${t('common.to')} ${element.end_stretch}`
  }
  return `${t('common.until')} ${element.end_stretch}`
}

const getPrice = function (element) {
  if(element.price){
    return element.price
  }
  return element.proportional_price
}


onMounted(() => {
  getData()
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("common.range")' :value="localData.token" />
    </div>
    <hr class="my-2" />
    <div :class="{ 'mt-1': localData.price_interval_stretches.length == 0 }" class="text-gray-900 rounded shadow">

      <table class="min-w-full text-sm text-slate-800">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ t('pricing_block.stretch') }}</th>
            <th class="p-2">{{ t('common.name') }}</th>
            <th class="p-2">{{ t('common.range') }} ({{ props.data.units }})</th>
            <th class="p-2">{{ t('common.price') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in localData.price_interval_stretches" :key="element.id" class="border-b">
            <td class="p-2">{{ element.stretch }}</td>
            <td class="p-2">{{ element.name_stretch? element.name_stretch : "-"}}</td>
            <td class="p-2">{{ props.data.units == 'dm' ? element.end_stretch : getInterval(element) }}</td>
            <td class="p-2">{{ getPrice(element) }}</td>
          </tr>
        </tbody>
      </table>
    </div>


  </div>

</template>
