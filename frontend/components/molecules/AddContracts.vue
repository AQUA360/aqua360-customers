<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';


const router = useRouter();
const { $ContractApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const selectedContracts = ref([]);

const emits = defineEmits(['item-clicked']);

const props = defineProps({
  selected_items: {
    type: Array,
    default: () => []
  },
  multiple: {
    type: Boolean,
    default: true
  },
  show: {
    type: Boolean,
    default: false
  },
  person_ids: {
    type: Array,
    default: () => []
  },
  // Espai (px) que s'ha de descomptar de l'alçada de la finestra per calcular
  // l'alçada del llistat. Les pantalles amb barra fixa inferior (p.ex. la de
  // remeses SEPA) hi han de sumar l'alçada d'aquesta barra, si no la paginació
  // queda tapada i no es pot canviar de pàgina.
  height_offset: {
    type: Number,
    default: 200
  }
});

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const contractClicked = ((contract) => {
  if (props.multiple) {
    if (selectedContracts.value.includes(contract.id)) {
      var index = selectedContracts.value.indexOf(contract.id);
      if (index > -1) {
        selectedContracts.value.splice(index, 1);
      }
    }
    else
      selectedContracts.value.push(contract.id)
  }
  else {
    selectedContracts.value = [contract.id]
  }

  emits('item-clicked', contract);

})

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false,) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $ContractApiService.getAll(searchQuery, filters, page, sort,
      desc, [], [], [],
      [], [], [], [], false,
      [], '', [], props.person_ids
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
    });

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    console.error('Error obtenint les dades:', err);
  } finally {
    pending.value = false;
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ContractApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    const data = await $ConfigProjectApiService.get('contract_active_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    }
  } catch (err) {
    console.error(err)
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  await getFilterStatus();
  await getData('', selectedFilters.value);
  loadSelected();
});


const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedContracts.value.includes(item?.id)) {
      selectedContracts.value.push(item?.id)
    }
  });
};

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.show, (newValue, oldValue) => {
  getData();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('common.contracts') }} </H1>
    
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <div id="list" style="overflow-y: auto; width: 100%; max-width: 100%;" :style="{
      minHeight: `calc(100vh - ${height_offset}px)`,
      maxHeight: `calc(100vh - ${height_offset}px)`
    }">
      <div
        class="heading grid grid-cols-[80px,100px,250px,200px,75px,150px,150px,150px,10px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('supply_point')" sortKey="supply_point" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('contract_block.holder')" sortKey="holder" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract_block.client_type')" sortKey="client_type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract_block.category')" sortKey="category" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="use_type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
          <span>&nbsp;</span>
      </div>

      <div v-if="pending">
        <p>{{ $t('common.loading') }}...</p>
      </div>
      <div v-else-if="error">
        <p>Error: {{ error.message }}</p>
        <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
      </div>
      <div v-else>
        <div v-for="item in items" :key="item.id" @click="contractClicked(item)"
          class="grid grid-cols-[80px,100px,250px,200px,75px,150px,150px,150px,10px] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50':selectedContracts.includes(item.id) }">
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ formatDate(item.created_at) }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.token }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 transition-all duration-200 truncate">{{ item.supply_point }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 transition-all duration-200 truncate">{{ item.holder_name }} {{ item.holder_surname }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
          </span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.client_type }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.category_name }}</span>
          <span :class="{'selected':selectedContracts.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.use_type_name }}</span>
          <span>&nbsp;</span>
        </div><!-- end for items -->

        <div v-if="items.length === 0" class="my-3">
          <p class="text-">{{ $t('common.no_records') }}</p>
        </div>

      </div><!-- else no-error no-pending -->
    </div><!-- end list -->
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->
</template>

<style scoped>
  .selected {
    margin-left: 15px
  }
</style>