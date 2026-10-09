<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { $PersonApiService } = useNuxtApp();
const { t } = useI18n();

const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const selectedPersons = ref([]);

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

const personClicked = ((person) => {
  if (props.multiple) {
    if (selectedPersons.value.includes(person.id)) {
      var index = selectedPersons.value.indexOf(person.id);
      if (index > -1) {
        selectedPersons.value.splice(index, 1);
      }
    }
    else
      selectedPersons.value.push(person.id)
  }
  else {
    selectedPersons.value = [person.id]
  }

  emits('item-clicked', person);
})

const getData = async (searchQuery = searchInput.value, page = pagination.value.page, sort = sortBy.value, desc = sortDesc.value) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PersonApiService.getAll(searchQuery, [], page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      document.getElementById('searchInput')?.focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const debouncedGetData = debounce((query, sort, desc) => {
  getData(query, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedPersons.value.includes(item?.id)) {
      selectedPersons.value.push(item?.id)
    }
  });
};

onMounted(async () => {
  await getData();
  loadSelected();
});

watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.show, () => {
  getData();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('person') }}</H1>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div class="heading grid grid-cols-[120px,150px,1fr,10px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="is_juridic" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="full_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
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
        <div v-for="item in items" :key="item.id" @click="personClicked(item)"
          class="grid grid-cols-[120px,150px,1fr,10px] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50': selectedPersons.includes(item.id) }">
          <span :class="{ 'selected': selectedPersons.includes(item.id) }" class="p-1 text-nowrap transition-all duration-200">{{ item.token }}</span>
          <span :class="{ 'selected': selectedPersons.includes(item.id) }" class="p-1 text-nowrap transition-all duration-200">{{ item.is_juridic ? $t('common.juridic') : $t('common.physical') }}</span>
          <span :class="{ 'selected': selectedPersons.includes(item.id) }" class="p-1 transition-all duration-200 truncate">{{ item.full_name || (item.name + ' ' + (item.surname || '')) }}</span>
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
