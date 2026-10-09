<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { AdjustmentConditionOperationChoices, AdjustmentConditionQuantityDefaultChoices } from '~/utils/adjustment-condition';
import H1Region from '../atoms/H1Region.vue';

const props = defineProps({
  onlyNumeric: Boolean,
});
const emit = defineEmits(['save']);

const { t } = useI18n();
const { $VariableTypeApiService } = useNuxtApp();

const variables_types = ref([]);
const searchQuery = ref('');

const filteredVariables = computed(() => {
  if (!searchQuery.value) return variables_types.value;
  
  const query = searchQuery.value.toLowerCase();
  return variables_types.value.filter(v => 
    v.name.toLowerCase().includes(query) || 
    v.token.toLowerCase().includes(query) ||
    v.data_type.toLowerCase().includes(query)
  );
});

const getData = async () => {
  const response = await $VariableTypeApiService.getAllUnpaginated();
  // si no hi ha response.results retornar error
  if (!response) return;
  if (response.error) {
    console.error('error getAllVariableTypes', response.error);
    return;
  }
  variables_types.value = response;  
}

onMounted(() => {
  getData();
});
</script>

<template>
   
  <div class="mb-3">
    <details>
      <summary class="flex items-center gap-x-2 py-2 hover:bg-gray-100 cursor-pointer">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        <p class="font-semibold">{{ t('pricing_block.variables_formula') }}</p>
      </summary>
      
      <div class="mt-3 space-y-4">
        <!-- Search -->
        <div class="relative">
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('dashboard.search')"
            class="w-full px-3 py-2 pl-10 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
          />
          <Icon 
            name="fa6-solid:magnifying-glass" 
            class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm" 
          />
        </div>

        <!-- Variables -->
        <div v-if="variables_types.length > 0">
          <h4 class="text-sm font-medium text-gray-700 mb-2">
            {{ t('variables') }} 
            <span v-if="searchQuery" class="text-gray-500 font-normal">
              ({{ filteredVariables.length }} {{ t('common.from') }} {{ variables_types.length }})
            </span>
          </h4>
          <div class="flex flex-wrap gap-2">
            <span 
              v-for="v in filteredVariables" 
              :key="v.token" 
              :title="`${v.name} (${v.data_type})`"
              class="inline-flex items-center gap-2 px-3 py-2 bg-sky-50 text-sky-700 text-sm rounded-md border border-sky-200 hover:bg-sky-100 transition-colors"
            >
              <span class="text-sky-500 font-mono">{{ v.name }}</span>
              <span class="font-medium">%variable.{{ v.token }}</span>
            </span>
          </div>
          <div v-if="searchQuery && filteredVariables.length === 0" class="text-gray-500 text-sm py-2">
            {{ t('common.no_search_results') }}: "{{ searchQuery }}"
          </div>
        </div>

        <!-- Contract -->
        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">{{t('contract')}}</h4>
          <div class="flex flex-wrap gap-2">
            <span class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors">
              <span class="text-green-500">%</span>
              contract.persons
            </span>
            <span class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors">
              <span class="text-green-500">%</span>
              contract.use_type
            </span>
            <span class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors">
              <span class="text-green-500">%</span>
              contract.client_type
            </span>
          </div>
        </div>

        <!-- Supply Point -->
        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">{{t('supply_point')}}</h4>
          <div class="flex flex-wrap gap-2">
            <span class="inline-flex items-center gap-1 px-2 py-1 bg-purple-50 text-purple-700 text-xs font-mono rounded-md border border-purple-200 hover:bg-purple-100 transition-colors">
              <span class="text-purple-500">%</span>
              supplypoint.type
            </span>
          </div>
        </div>
      </div>
    </details>
  </div>

</template>
