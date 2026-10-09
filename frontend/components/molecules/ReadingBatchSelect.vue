<script setup>
import { ref, onMounted, nextTick, getCurrentInstance , watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ExploitationRegion from '~/components/organisms/ExploitationRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';


const router = useRouter();
const {  $ConfigProjectApiService, $ReadingBatchApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('token');
const sortDesc = ref(false);

const pendingBillingToken = ref(null)

const emit = defineEmits(['item-clicked']);

const props = defineProps({
  modelValue: {
    type: Array,
    default: []
  },
  multiple: {
    type: Boolean,
    default: true
  },
  show: {
    type: Boolean,
    default: true
  },
  blockDelete: {
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

const itemClicked = ((c) => {
  var index = props.modelValue.map( i => i.id).indexOf(c.id);
  if (props.blockDelete && index > -1)
    return;
  if (props.multiple) {
    if (props.modelValue.map( i => i.id).includes(c.id)) {
      if (index > -1) {
        props.modelValue.splice(index, 1);
      }
    }
    else
    props.modelValue.push(c)
  }
  else {
    props.modelValue = [c]
  }

  emit('item-clicked', c);
})

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false,) => {
  pending.value = true;
  error.value = null;
  try {


    pendingBillingToken.value = await $ConfigProjectApiService.get('batch_status_finish_token');


    const data = await $ReadingBatchApiService.getAll(searchQuery, [ pendingBillingToken.value ], page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const debouncedGetData = debounce((query, [], sort, desc) => {
  getData(query, [], pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, [], sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, [], newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(() => {
  getData();
  loadSelected();
});

const loadSelected = () => {
  // props.selected_items.forEach(item => {
  //   if (!cnaes.includes(item.id)) {
  //     cnaes.value.push(item.id)
  //   }
  // });
};

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.show, (newValue, oldValue) => {
  getData();
});

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('billing_block.batches_to_bill') }} </H1>
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
      <div
        class="heading grid grid-cols-[1fr,1fr,1fr] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.code')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.date')" sortKey="description" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('readings')" sortKey="description" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
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
        <div v-for="item in items" @click="itemClicked(item)"
          class="grid grid-cols-[1fr,1fr,1fr] gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50':modelValue ? modelValue.map( i => i.id).includes(item.id) : false, 'cursor-default': props.blockDelete && modelValue.map( i => i.id).includes(item.id), 'cursor-pointer': !props.blockDelete || !modelValue.map( i => i.id).includes(item.id) }">
          <span :class="{'selected':modelValue ? modelValue.map( i => i.id).includes(item.id) : false}" class="p-1 transition-all duration-200">{{ item.token }}</span>
          <span :class="{'selected':modelValue ? modelValue.map( i => i.id).includes(item.id) : false}" class="p-1 text-nowrap transition-all duration-200">{{ formatDate(item.created_at) }}</span>
          <span :class="{'selected':modelValue ? modelValue.map( i => i.id).includes(item.id) : false}" class="p-1 text-nowrap transition-all duration-200">{{ item.num_readings }}</span>
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