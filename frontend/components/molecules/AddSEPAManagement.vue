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
const { $PaymentApiService, $ProductApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_origin = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const selectedPayments = ref([]);

const emits = defineEmits(['item-clicked']);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});


const getData = async (page = 1, filters = []) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PaymentApiService.getAll('', [], page, null, false, null, true, true, true, filters);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
    });

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getFilterOrigin = async () => {
  error.value = null;
  try {
    filter_origin.value = [];
    const result = await $ProductApiService.getOrigins();
    filter_origin.value = result.results
    
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((filters) => {
  getData(pagination.value.page,filters);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(selectedFilters.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(newPage, selectedFilters.value);
}


const paymentClicked = ((payment) => {
  if (selectedPayments.value.includes(payment.id)) {
    var index = selectedPayments.value.indexOf(payment.id);
    if (index > -1) {
      selectedPayments.value.splice(index, 1);
    }
  } else {
    selectedPayments.value.push(payment.id)
  }
})


const resetFilters = () => {
  selectedFilters.value = [];
  pagination.value.page = 1;
  getData();
};


onMounted(() => {
  getData();
  getFilterOrigin()
});



watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});


</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('billing_block.mng_sepa') }} </H1>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="flex gap-3" v-if="filter_origin.length">
        <label v-for="origin in filter_origin" :key="origin.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="origin.id" @change="handleFilterChange" /> {{
            origin.name }}
        </label>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div class="heading grid grid-cols-[200px,250px,50px,15px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" :sortable="false" />
        <TableHeader :label="$t('invoice')" :sortable="false" />
        <TableHeader :label="$t('common.total')" :sortable="false" />
        <TableHeader :label="$t('billing_block.fractionated')" :sortable="false" />
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
        <div v-for="item in items" :key="item.id" @click="paymentClicked(item)"
          class="grid grid-cols-[200px,250px,50px,15px] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50': selectedPayments.includes(item.id) }">

          <span :class="{ 'selected': selectedPayments.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.token }}</span>
          <span :class="{ 'selected': selectedPayments.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.invoice.title_final + ' ' + item.invoice.token
            }}</span>
          <span :class="{ 'selected': selectedPayments.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.amount }}</span>
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