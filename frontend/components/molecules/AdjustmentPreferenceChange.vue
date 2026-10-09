<script setup>
// components/organisms/ClusterDetail.vue
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';
const { $LineItemTypeApiService, $AdjustmentApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isContractSubregion: {
    type: Boolean,
    default: false
  },
  in_detail: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['change']);

const localData = ref(props.data ? { ...props.data } : {});
const adjustments = ref([]);
const isLoading = ref(false);
const error = ref(null);
const adjustmentPreferences = ref([]);

const getData = async () => {
  isLoading.value = true;
  adjustments.value = [];
  adjustmentPreferences.value = [];
  try {
    const detail = await $LineItemTypeApiService.getDetail(props.id);
    localData.value = detail;
    localData.value.adjustments.sort((a, b) => a.position - b.position).forEach(item => {
      adjustments.value.push(item);
    });
    adjustments.value.forEach(item => {
      adjustmentPreferences.value.push({
        id: item.id,
        position: item.position,
      });
    });
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};

const save = async () => {
  try {
    // Prepare the data to be sent to the API
    const dataToSave = adjustmentPreferences.value.map(pref => ({
      id: pref.id,
      position: parseInt(pref.position)
    }));
    for (let i = 0; i < dataToSave.length; i++) {
      const response = await $AdjustmentApiService.save(dataToSave[i]);
    }
    emit('change', localData.value);
    // Call the API to save all preferences
    /* const response = await $AdjustmentApiService.saveAll(dataToSave);
    console.log('Preferences saved successfully:', response);
    // Optionally, refresh the data after saving
    await getData();
    emit('change', localData.value); */
  } catch (err) {
    console.error('Error saving preferences:', err);
  }
};

onMounted(() => {
  getData();
});
</script>



<template>
  <div v-if="!isLoading" id="wrapper" class="py-4 px-6">
    <H1Region class="mb-5">{{ $t('pricing_block.edit_adj_pref') }}</H1Region>
    <table v-if="adjustments.length > 0" class="min-w-full table-auto text-sm text-gray-800 border rounded-lg">
      <thead>
        <tr class="bg-gray-100 text-left border-b">
          <th class="px-4 py-2 font-semibold">{{ $t('common.preference') }}</th>
          <th class="px-4 py-2 font-semibold">{{ $t('common.name') }}</th>
          <th class="px-4 py-2 font-semibold">{{ $t('common.operation') }}</th>
          <th class="px-4 py-2 font-semibold">{{ $t('pricing_block.short_var_cal') }}</th>
          <th class="px-4 py-2 font-semibold">{{ $t('common.quantity') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(element, index) in adjustments" :key="element.id"
          class="border-b hover:bg-gray-50 transition duration-150 ease-in-out">
          <td class="px-4 py-3">
            <input
              class="w-[50%] bg-transparent border text-center rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300"
              v-model="adjustmentPreferences[index].position" />
          </td>
          <td class="px-4 py-3">{{ element.name }}</td>
          <td class="px-4 py-3">{{ element.operation.name }}</td>
          <td class="px-4 py-3">{{ element.variable_calculation.name }}</td>
          <td class="px-4 py-3">
            <span v-if="element.adjustment_interval_stretches && element.adjustment_interval_stretches.length > 0"
              class="text-gray-500">
              <em>{{ $t('common.range') }}</em>
            </span>
            <span v-else>{{ element.quantity }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
      </button>
    </div>
  </div>
</template>
