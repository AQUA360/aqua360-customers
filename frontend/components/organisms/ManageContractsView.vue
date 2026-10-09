<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import ContractRegion from './ContractRegion.vue';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  contract_ids: Object,
  value: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(['save']);
const { $ContractApiService } = useNuxtApp();

const pending = ref(false);
const error = ref(null);
const data = ref([]);
const contracts = ref([]);
const total_contracts = ref(0);


const page = ref(1);
const pageSize = 20;
const hasNextPage = ref(true)
const loadingMore = ref(false);
const allDataLoaded = ref(false);
const debt_management = ref(null)

const showRegion = ref(false);
const showRegionDetailComponent = ref(null);
const showRegionDetail = ref(null);
const isSubRegionOpen = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    showRegionDetailComponent.value = null
    showRegionDetail.value = null
  }
}

const showDetail = (entity, id) => {
  showRegionDetailComponent.value = entity;
  showRegionDetail.value = id;
  toggleRegion(true);
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}


const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleDateString();
};

const getData = async () => {
  if (loadingMore.value || allDataLoaded.value) return;

  pending.value = true;
  error.value = null;
  loadingMore.value = true;

  try {
    const response = await $ContractApiService.getAll(
      '',
      [],
      page.value,
      null,
      false,
      props.value.variable_type_ids,
      props.value.bonification_type_ids,
      props.value.client_type_ids,
      props.value.use_type_ids,
      props.value.category_ids,
      props.value.product_ids
    );


    if (response.results && response.results.length > 0) {
      if (response.next == null) {
        hasNextPage.value = false;
      }
      data.value = data.value.concat(response.results);
      if (response.results.length < pageSize || !hasNextPage.value) {
        allDataLoaded.value = true;
      } else {
        page.value++;
      }
    } else {
      allDataLoaded.value = true;
    }
  } catch (err) {
    error.value = err;
    toast.error(t('common.error_load'));
  } finally {
    pending.value = false;
    loadingMore.value = false;
  }
};

const save = async () => {
  if (!confirm(t('confirmation_text_block.confirm_save'))) return
  emit('save', true);
};

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollHeight - scrollTop <= clientHeight + 50) {
    getData();
  }
};


onMounted(() => {
  debt_management.value = props.contract_ids.debt_management
  total_contracts.value = props.contract_ids.contract_ids.length;
  getData(); // Initial data load
});
</script>

<template>
  <div class="region__content w-[85vw] h-[90vh]">
    <div v-if="pending && !loadingMore">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="relative h-full">
      <H1Region class="m-3 flex items-center">
        {{ t('contract_block.loaded_contracts_info') }}
      </H1Region>
      <div class="flex gap-3 relative">
        <div class="border border-slate-600 bg-slate-50 rounded-md px-2 py-1  gap-2">
          <span>
            {{ $t('common.contracts') }} - {{ total_contracts }}
          </span>
        </div>
        <!-- POSSIBLE IMPORTANT INFO -->
        <!-- <div class="border border-slate-600 bg-slate-50 rounded-md px-2 py-1  gap-2">
          <details class="relative">
            <summary class="cursor-pointer">
              {{ t('Gestió del deute') }}
            </summary>
            <div
              class="absolute top-full left-0 bg-white border border-gray-300 rounded-md shadow-md z-20 w-[250px] h-[500px] overflow-y-auto scrollbar-hide"
            >
              <div v-for="(count, name, index) in debt_management" :key="index" 
              class="px-4 py-2 grid grid-cols-[1fr,50px] border-b">
                <span>{{ name }}</span> 
                <span class="text-right">{{ count }}</span>
              </div>
            </div>
          </details>

        </div> -->
      </div>

      <!--CONTRACTS CONTENT-->

      <div id="list" class="rounded-lg overflow-auto" :style="{
        width: 'calc(100%)',
        maxWidth: '100%',
        minHeight: 'calc(100vh - 225px)',
        maxHeight: 'calc(100vh - 225px)',
      }" @scroll="onScroll">
        <table class="min-w-full table-auto">
          <thead class="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('common.date') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('common.identification') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('supply_point') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('contract_block.holder') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('common.status') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('contract_block.client_type') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('contract_block.category') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('common.type') }}
              </th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('contract_block.debt_management_type') }}
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="item in data" :key="item.id">
              <td class="px-4 py-2 whitespace-nowrap">
                {{ formatDate(item.created_at) }}
              </td>
              <td class="px-4 py-2 whitespace-nowrap">
                <abbr :title="item.id" class="text-sky-500 no-underline hover:underline hover:text-sky-600">
                  <button @click="showDetail('ContractRegion', item.id)">
                    {{ item.token }}
                  </button>
                </abbr>
              </td>
              <td class="px-4 py-2 whitespace-nowrap">{{ item.supply_point }}</td>
              <td class="px-4 py-2 whitespace-nowrap">
                {{ item.holder_name }} {{ item.holder_surname }}
              </td>
              <td class="px-4 py-2 whitespace-nowrap">
                <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
              </td>
              <td class="px-4 py-2 whitespace-nowrap">{{ item.client_type }}</td>
              <td class="px-4 py-2 whitespace-nowrap">{{ item.category_name }}</td>
              <td class="px-4 py-2 whitespace-nowrap">{{ item.use_type_name }}</td>
              <td class="px-4 py-2 whitespace-nowrap">{{ item.debt_management_name }}</td>
            </tr>
            <tr v-if="data?.length === 0 && !pending">
              <td colspan="8" class="px-4 py-2 text-center">
                {{ $t('common.no_records') }}
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="loadingMore" class="text-center py-4">
          {{ $t('common.loading') }}...
        </div>
        <div v-if="allDataLoaded && data?.length > 0" class="text-center py-4 text-gray-500">
          {{ $t('common.all_data_loaded') }}
        </div>
      </div>

      <div class="absolute bottom-0 right-0 flex flex-row-reverse mt-4 text-base gap-3">
        <button @click="save" :disabled="false" class="button-secondary">
          {{ $t('common.save') }}
        </button>
        <button @click="emit('save', false)" :disabled="false" class="button-default">
          {{ $t('common.cancel') }}
        </button>
      </div>
    </div>
    <div v-if="showRegion" role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRegion v-if="showRegionDetailComponent == 'ContractRegion'" :id="showRegionDetail" :isSubRegionOpen="isSubRegionOpen"
          @show-subregion="handleSubRegionEvent"></ContractRegion>
      </div>
    </div>
  </div>
  <!-- end region__content -->
</template>
