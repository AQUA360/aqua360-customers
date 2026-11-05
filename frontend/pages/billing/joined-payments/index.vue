<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import JoinedPaymentRegion from '~/components/organisms/JoinedPaymentRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
    showRegion.value = force !== undefined ? force : !showRegion.value;
    if (showRegion.value == false) {
        isSubRegionOpen.value = false;
        detail.value = null
        selectedItemId.value = null
    }
}

const route = useRoute();
const { $JoinedPaymentApiService, $PaymentApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchInputTotalFinal = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const activeSearchInput = ref('searchInput');
const sortDesc = ref(false);
const objectPermissions = ref(null);
const statuses = ref([])
const selected_payment_types = ref([])
const payment_types = ref([])
const filter_payment_type = ref([])
const selectedPaymentDate = ref([])
const selectedDueDate = ref([])
const payment_date = ref(null);
const due_date = ref(null);

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const pagination = ref({
    page: 1,
    perPage: 50,
    total: 0,
    totalPages: 0,
    previous: null,
    next: null,
    isFiltered: false
});

// Converteix l'import escrit per l'usuari (p. ex. "12,50" o "1.234,50") al format
// numèric que espera el filtre `total_final` del backend. Si no és un número vàlid
// no s'envia, per evitar un error 400.
const normalizedTotal = () => {
    let value = String(searchInputTotalFinal.value || '').trim();
    if (!value) return null;
    if (value.includes(',')) {
        value = value.replace(/\./g, '').replace(',', '.');
    }
    return /^\d+(\.\d+)?$/.test(value) ? value : null;
}

// Llegeix sempre l'estat actual de cerca, filtres i ordenació, de manera que
// cap crida pugui perdre'n una part.
const getData = async (page = pagination.value.page) => {
    if (!objectPermissions.value?.can_view) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    pending.value = true;
    error.value = null;
    try {
        const data = await $JoinedPaymentApiService.getAll(
            searchInput.value, statuses.value, page, sortBy.value, sortDesc.value,
            payment_date.value, due_date.value, normalizedTotal(), payment_types.value
        );

        items.value = data.results;
        Object.assign(pagination.value, {
            total: data.count,
            totalPages: Math.ceil(data.count / pagination.value.perPage),
            previous: data.previous,
            next: data.next,
            isFiltered: String(searchInput.value).trim() !== ''
        });

        nextTick(() => {
            const activeInput = document.getElementById(activeSearchInput.value);
            if (activeInput) {
                activeInput.focus();
            }
        });
    } catch (err) {
        error.value = err;
    } finally {
        pending.value = false;
    }
}

const getFilterStatus = async () => {
    error.value = null;
    try {
        const data = await $ConfiglistApiService.getAll('billing/joined-payment-status')
        filter_status.value = data.results;
    } catch (err) {
        error.value = err;
    }
}

const getFilterPaymentType = async () => {
    error.value = null;
    try {
        const data = await $ConfiglistApiService.getAll('contract/contract-payment-type');
        filter_payment_type.value = [
            {
                id: 'null',
                token: '',
                name: t('None'),
            },
            ...(data.results || []),
        ];
    } catch (err) {
        error.value = err;
    }
}

const debouncedGetData = debounce(() => getData(1), 300);

const handleSearch = () => {
    pagination.value.page = 1;
    debouncedGetData();
}

const handleTotalFinalInput = (event) => {
    const value = event.target.value;
    // Only allow numbers, dots, and commas
    const filtered = value.replace(/[^0-9.,]/g, '');
    searchInputTotalFinal.value = filtered;
    handleSearch();
}

const handleFiltersChange = (event) => {
    let newFilters = event
        .filter(el => !isFilterShown.value.includes(el.id));

    checkInAdvacedFilters(newFilters)
    isFilterShown.value = [];
    isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

// Quan es treu un filtre addicional, en buida el valor i torna a carregar
// mantenint la cerca, l'ordenació i la resta de filtres.
const checkInAdvacedFilters = (newFilters) => {
    const removed = (id) => isFilterShown.value.some(filter => filter.id === id) && !newFilters.some(filter => filter.id === id);
    let changed = false;
    if (removed('payment_type')) {
        payment_types.value = [];
        selected_payment_types.value = [];
        changed = true;
    }
    if (removed('status')) {
        statuses.value = [];
        selectedFilters.value = [];
        changed = true;
    }
    if (removed('payment_date')) {
        payment_date.value = null;
        selectedPaymentDate.value = [];
        changed = true;
    }
    if (removed('due_date')) {
        due_date.value = null;
        selectedDueDate.value = [];
        changed = true;
    }
    if (changed) {
        handleSearch();
    }
}

const handlePayTypeChange = (event) => {
    selected_payment_types.value = event;
    payment_types.value = selected_payment_types.value.map(element => element.id);
    handleSearch();
}

const handleStatusChange = (event) => {
    selectedFilters.value = event;
    statuses.value = selectedFilters.value.map(element => element.id);
    handleSearch();
}

const handlePaymentDateChange = (event) => {
    payment_date.value = event;
    handleSearch();
}

const handleDueDateChange = (event) => {
    due_date.value = event;
    handleSearch();
}

const handlePageChange = (newPage) => {
    pagination.value.page = newPage;
    getData(newPage);
}

const handleSort = (key) => {
    if (sortBy.value === key) {
        sortDesc.value = !sortDesc.value;
    } else {
        sortBy.value = key;
        sortDesc.value = false;
    }
    pagination.value.page = 1;
    getData(1);
}

const resetFilters = () => {
    debouncedGetData.cancel();
    searchInput.value = '';
    searchInputTotalFinal.value = '';
    sortBy.value = null;
    sortDesc.value = false;
    selectedFilters.value = [];
    statuses.value = [];
    selected_payment_types.value = [];
    payment_types.value = [];
    payment_date.value = null;
    selectedPaymentDate.value = [];
    due_date.value = null;
    selectedDueDate.value = [];
    isFilterShown.value = [];
    isFilterOpen.value = false;
    pagination.value.page = 1;
    getData(1);
};


const showDetail = async (id) => {
    await toggleRegion(false);
    detail.value = id;
    selectedItemId.value = id;
    toggleRegion(true);
}

const exportColumns = computed(() => [
    { header: t('common.creation_date'), value: (row) => row.created_at ? formatDate(row.created_at) : '' },
    { header: t('common.identification'), value: (row) => row.token },
    { header: t('common.client'), value: (row) => [row.customer_final, row.customer_token_final ? `(${row.customer_token_final})` : ''].filter(Boolean).join(' ') },
    { header: t('common.amount'), value: (row) => Number(row.total_final ?? 0) },
    { header: t('common.status'), value: (row) => row.status_name },
    { header: t('common.payment_method'), value: (row) => row.payment_type_name },
    { header: t('billing_block.payment'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '' },
    { header: t('common.limit'), value: (row) => row.due_date ? formatDate(row.due_date) : '' },
]);
const exportJoinedPayments = () => $JoinedPaymentApiService.exportData(
    searchInput.value, statuses.value, sortBy.value, sortDesc.value,
    payment_date.value, due_date.value, normalizedTotal(), payment_types.value
);

/**
 * Columnes de la taula (vegeu `useTableColumns`). Les claus d'ordenació han de
 * coincidir amb `ordering_fields` de `JoinedPaymentViewSet`.
 */
const tableColumns = computed(() => [
    { key: 'created_at', label: t('common.creation_date'), sortKey: 'created_at', width: 90, min: 82, priority: 3 },
    { key: 'token', label: t('common.identification'), sortKey: 'number', width: 130, min: 110, priority: 1, removable: false },
    { key: 'customer', label: t('common.client'), sortKey: 'customer_final', width: 260, grow: 4, min: 160, priority: 1, removable: false },
    { key: 'total_final', label: t('common.amount'), sortKey: 'total_final', width: 110, min: 90, priority: 1 },
    {
        key: 'status', label: t('common.status'), sortKey: 'status__position',
        width: 130, min: 100, priority: 1, cellClass: 'inline-flex gap-1 items-center',
    },
    { key: 'payment_type', label: t('common.payment_method'), sortKey: 'payment_type_name', width: 180, grow: 2, min: 120, priority: 2 },
    { key: 'payment_date', label: t('billing_block.payment'), sortKey: 'payment_date', width: 90, min: 82, priority: 3 },
    { key: 'due_date', label: t('common.limit'), sortKey: 'due_date', width: 90, min: 82, priority: 3 },
]);

const customerLabel = (item) => [
    item.customer_final,
    item.customer_token_final ? `(${item.customer_token_final})` : '',
].filter(Boolean).join(' ');

const rowClass = (item) => ({
    'bg-yellow-50': item.id === selectedItemId.value,
});

onMounted(async () => {
    objectPermissions.value = await checkPermission($PaymentApiService);
    if (objectPermissions.value?.can_view) {
        filtersExtra.value.push(
            { name: t('common.status'), id: "status" },
            { name: t('common.payment_method'), id: "payment_type" },
            { name: t('billing_block.payment_date'), id: "payment_date" },
            { name: t('common.due_date'), id: "due_date" },
        );
        getData();
        getFilterStatus();
        getFilterPaymentType();
        checkRouteQuery()
    } else {
        toast.error(t('common.no_permissions'));
        pending.value = false;
        return navigateTo('/');
    }
});

const checkRouteQuery = () => {
    if (route?.query?.id) {
        showDetail(route.query.id);
    }
};

watch([searchInput], (newValue) => {
    pagination.value.page = 1;
    handleSearch();
    if (newValue) {
    searchInputTotalFinal.value = '';
    activeSearchInput.value = 'searchInput';
  }
});
watch(searchInputTotalFinal, (newValue) => {
  if (newValue) {
    searchInput.value = '';
    activeSearchInput.value = 'searchInputTotalFinal';
  }
});

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}
watch(() => route.query, () => {
    checkRouteQuery()
}, { immediate: true })
</script>

<template>
    <div id="wrapper" class="text-base">
        <div class="flex justify-between items-center mb-2">
            <H1 class="mb-2">{{ $t('billing_block.joined_payments') }}</H1>
            <NuxtLink v-if="objectPermissions?.can_change" to="/billing/joined-payments/add" class="button-primary">{{
                $t('billing_block.new_joined_payment') }}</NuxtLink>
        </div>
        <form id="form_filter" role="search"
            class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
            @submit.prevent="handleSearch">

            <span class="input-group flex flex-start items-center gap-2 w-80">
                <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
                    :placeholder="$t('dashboard.search')"
                    class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
            </span>

            <div class="h-8 w-px bg-gray-300"></div>

            <span class="input-group flex flex-start items-center gap-2 w-80">
                <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                <input v-model="searchInputTotalFinal" @input="handleTotalFinalInput" id="searchInputTotalFinal"
                    type="text" name="search" :placeholder="$t('search_block.search_total_final')"
                    class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
            </span>

            <span>
                <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
                    @click="isFilterOpen = !isFilterOpen" title="show">
                    <Icon name="fa:filter" class="text-slate-500" />
                </button>
            </span>

            <span>
                <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
                    @click="resetFilters" title="reset">
                    <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
                </button>
            </span>
        </form>

        <div class="px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

            <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
                :filters="selectedFilters" :multiple="true" :placeholder="t(`common.statuses`)"
                @update:modelValue="handleStatusChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
                </template>
            </FilterSelect>

            <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_type')"
                :options="filter_payment_type" :filters="selected_payment_types" :multiple="false"
                :placeholder="t(`common.payment_method`)" @update:modelValue="handlePayTypeChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:cube" class="text-slate-500 " />
                </template>
            </FilterSelect>

            <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_date')" :datePick="true"
                :filters="selectedPaymentDate" :placeholder="t(`billing_block.sel_payment_date`)"
                @update:modelValue="handlePaymentDateChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:calendar" class="text-md ml-2 mr-1" size="10px" />
                </template>
            </FilterSelect>

            <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'due_date')" :datePick="true"
                :filters="selectedDueDate" :placeholder="t(`billing_block.sel_due_date`)"
                @update:modelValue="handleDueDateChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:calendar-xmark" class="text-md ml-2 mr-1" size="10px" />
                </template>
            </FilterSelect>

            <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
                :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
                <template #icon>
                    <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
                </template>
            </FilterSelect>

        </div>
        <DataTable
            table-key="joined-payments"
            :columns="tableColumns"
            :items="objectPermissions?.can_view ? items : []"
            :row-class="rowClass"
            :current-sort-by="sortBy"
            :sort-desc="sortDesc"
            :pending="pending"
            :error="error"
            :is-empty="items.length === 0"
            @sort="handleSort"
            @retry="getData()">
            <template #cell-created_at="{ item }">{{ formatDate(item.created_at) }}</template>

            <template #cell-token="{ item }">
                <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
                    @click="showDetail(item.id);">
                    <abbr :title="item.id" class="no-underline truncate">{{ item.token }}</abbr>
                    <Icon name="fa6-solid:eye"
                        class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
                </button>
            </template>

            <template #cell-customer="{ item }">
                <span class="truncate" :title="customerLabel(item)">{{ customerLabel(item) }}</span>
            </template>

            <template #cell-total_final="{ item }">{{ formatMoneyWithCurrency(item.total_final) }}</template>

            <template #cell-status="{ item }">
                <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
            </template>

            <template #cell-payment_type="{ item }">
                <span class="truncate" :title="item.payment_type_name">{{ item.payment_type_name || '-' }}</span>
            </template>

            <template #cell-payment_date="{ item }">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</template>
            <template #cell-due_date="{ item }">{{ item.due_date ? formatDate(item.due_date) : '-' }}</template>
        </DataTable>
        <div id="list__footer">
            <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
        </div>
    </div><!-- end wrapper -->

    <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
        :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
        <div id="region_nav" class="mb-3 px-3">
            <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                <Icon name="fa6-solid:angles-right" class="text-slate-500" />
            </button>
        </div>
        <div v-if="showRegion" class="pl-10" :style="{ minHeight: 'calc(100vh - 100px)', maxHeight: 'calc(100vh - 100px)' }">
            <JoinedPaymentRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
                @show-subregion="handleSubRegionEvent" @changed="getData" @close-subregion="toggleRegion(false)" />
        </div>
    </div>

</template>
