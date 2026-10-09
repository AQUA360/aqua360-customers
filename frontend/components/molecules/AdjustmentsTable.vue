<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { $AdjustmentApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    default: false,
  }, // ID de l'element
  pr_id: {
    type: Number,
    default: false,
  },
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

const adjustments = ref([])
const isLoading = ref(false);
const error = ref(null);


const showDetail = function (component, id) {
  emit('show-detail', { component: component, id: id })
}


const getData = async () => {
  isLoading.value = true;
  try {
    if (props.pr_id) {
      const detail = await $AdjustmentApiService.getAll('', [], 1, null, false, props.pr_id);
      detail.results.forEach(item => {
        adjustments.value.push(item)
      })
    }

  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => {
  getData()
});

</script>

<template>
  <div id="wrapper" class="text-base">

    <div v-if="adjustments.length > 0" :class="{ 'mt-1': adjustments.length == 0 }"
      class="text-gray-900 rounded shadow">

      <table class="min-w-full text-sm text-slate-800">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ t('common.identification') }}</th>
            <th class="p-2">{{ t('common.operation') }}</th>
            <th class="p-2">{{ t('pricing_block.short_var_cal') }}</th>
            <th class="p-2">{{ t('common.quantity') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in adjustments" :key="element.id" class="border-b"
            :class="element.end ? 'bg-slate-50' : 'bg-slate-50 font-bold'">
            <td v-if="!isSubRegion" class="p-2">
              <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                @click="showDetail('AdjustmentRegion', element.id)">{{ element.token }}</button>
            </td>
            <td v-else class="p-2">{{ element.token }}</td>
            <td class="p-2">{{ element.operation.name }}</td>
            <td class="p-2">{{ element.variable_calculation.name }}</td>
            <td v-if="!element.adjustment_interval" class="p-2">{{ element.quantity }}</td>
            <td v-else class="p-2">{{ element.adjustment_interval.coefficient }}</td>
          </tr>
        </tbody>

      </table>
    </div>

    <div v-else>
      <div class="footering text-slate-500 p-2">
        <p>{{ $t('common.no_data') }}</p>
      </div>
    </div>

  </div>

</template>
