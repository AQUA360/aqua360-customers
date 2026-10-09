<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useSidebarStore } from '~/stores/useNavSideBar';
import PaymentsList from '~/components/molecules/PaymentsList.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useToast } from 'vue-toastification';

const sidebarStore = useSidebarStore();
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
    selected_item: {
        type: Object,
        default: null
    },
    selected_items: {
        type: Array,
        default: () => []
    },
    multiple: {
        type: Boolean,
        default: false
    },
    allow_select: false
});

const SubRegion = ref(false);
const emit = defineEmits(['show-subregion', 'item-clicked']);

const toggleRegion = (force) => {
    SubRegion.value = force !== undefined ? force : !SubRegion.value;
    if (SubRegion.value == false) {
        isSubRegionOpen.value = false;
        detail.value = null
        selectedItemId.value = null
        detail_data.value = {}
    }
    emit('show-subregion', SubRegion.value);
}

const route = useRoute();
const router = useRouter();
const { $SepaRemittanceApiService, $ConfiglistApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const sending = ref(false);

const selectedRemittances = ref([]);
const sent_at = ref(new Date(Date.now()).toISOString().split('T')[0])

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const filter_type = ref([]);
const selected_types = ref([]);
const types = ref([]);

const sent_token = ref(null);

const pagination = ref({
    page: 1,
    perPage: 50,
    total: 0,
    totalPages: 0,
    previous: null,
    next: null,
    isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    pending.value = true;
    error.value = null;

    try {
        const data = await $SepaRemittanceApiService.getAll(searchQuery, filters, page, sort, desc, null, types.value);

        items.value = data.results;
        // muntem la paginacio
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

const getFilterStatus = async () => {
    error.value = null;
    try {
        const data = await $ConfiglistApiService.getAll('billing/payment-remittance-status');
        filter_status.value = data.results;
    } catch (err) {
        error.value = err;
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
    selected_types.value = [];
    types.value = [];
    isFilterShown.value = [];
    isFilterOpen.value = false
    getData();
};

const onChangeRegion = (event) => {
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const selectRemittance = (item) => {
    if (props.allow_select) {
        if (props.multiple) {
            if (selectedRemittances.value.includes(item.id)) {
                selectedRemittances.value = selectedRemittances.value.filter(id => id !== item.id);
            } else {
                selectedRemittances.value.push(item.id);
            }
        }
        emit('item-clicked', item);
        return;
    }
    if (item.status_token == sent_token.value) {
        toast.warning(t('warning_block.warning_already_sent'));
        return;
    };
    if (selectedRemittances.value.includes(item.id)) {
        selectedRemittances.value = selectedRemittances.value.filter(id => id !== item.id);
    } else {
        selectedRemittances.value.push(item.id);
    }
}

const sendRemittance = async () => {
    if (!confirm(t('confirmation_text_block.confirm_send_remittance'))) return;
    sending.value = true;
    try {
        let save_data = {
            ids: selectedRemittances.value,
            sent_at: sent_at.value
        }
        const data = await $SepaRemittanceApiService.sendRemittance(save_data);
        await getData();
        selectedRemittances.value = [];
    } catch (error) {
        console.error(error);
    } finally {
        sending.value = false;
    }
}

onMounted(async () => {
    if (props.allow_select) {
        if (props.multiple) {
            selectedRemittances.value = (props.selected_items || []).map(item => item.id);
        } else if (props.selected_item) {
            selectedRemittances.value = [props.selected_item.id];
        }
    }
    sent_token.value = await $ConfigProjectApiService.get('payment_remittance_status_sent_token');
    getData();
    getFilterStatus();
});

const detail = ref(null);
const detail_data = ref({})
const selectedItemId = ref(null);
const showDetail = async (item) => {
    await toggleRegion(false);
    detail.value = item.id;
    selectedItemId.value = item.id;
    detail_data.value = { 'token': item.token, 'date': item.created_at }
    toggleRegion(true);
}

const printDocument = async (doc_id) => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(doc_id)
    let file = await $DocumentManagerApiService.viewDocument(doc_id);
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = document_file.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
    pagination.value.page = 1;
    handleSearch();
});

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

</script>

<template>
    <div class="region__content">
        <div class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
            <div class="flex justify-between items-center">
                <H1 class="">{{ $t('common.remittances') }}</H1>
            </div>
            <div v-if="!props.allow_select" class="flex items-center justify-start gap-2">
                <AtomsInputDate v-model="sent_at" :label="''" />
                <button class="button-primary mb-2"
                    :disabled="selectedRemittances.length === 0 || sent_at == null || sent_at == ''"
                    @click="sendRemittance">
                    {{ sending ? t('billing_block.marking_as_sent') + '...' : t('billing_block.mark_as_sent') }}
                </button>
                <!-- <span v-if="sending" class="text-sm text-slate-400 align-right w-full">
                    {{ t('informative_block.info_can_exit_and_work') }}
                </span> -->
            </div>
            <div>
                <span class="text-sm text-slate-400">
                    {{ t('common.select') }} {{ t('common.remittances') }}
                </span>
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

                <span class="flex gap-3" v-if="filter_status.length">
                    <label v-for="status in filter_status" :key="status.id"
                        class="text-slate-800 text-base flex items-center gap-1">
                        <input type="checkbox" v-model="selectedFilters" :value="status.id"
                            @change="handleFilterChange" /> {{
                                status.name }}
                    </label>
                </span>

                <span>
                    <button id="filterReset" name="form_filter" type="button"
                        class="px-2 py-1 hover:bg-slate-300 rounded" @click="resetFilters" title="reset">
                        <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
                    </button>
                </span>
            </form>

            <div id="list" :style="{
                overflowY: 'auto',
                width: 'calc(-295px + 100vw)',
                maxWidth: '100%',
                minHeight: 'calc(100vh - 280px)',
                maxHeight: 'calc(100vh - 280px)',
            }">
                <div
                    class="heading grid grid-cols-[5px,75px,1fr,45px,150px,75px,80px,60px] gap-3 text-base border-b items-center">
                    <span></span>
                    <TableHeader :label="$t('common.creation')" sortKey="created_at" :currentSortBy="sortBy"
                        :sortDesc="sortDesc" @sort="handleSort" />
                    <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
                        @sort="handleSort" />
                    <TableHeader :label="$t('common.total')" :sortable="false" />
                    <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
                        @sort="handleSort" />
                    <TableHeader :label="$t('customer_service_block.sent_to')" sortKey="sent_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
                        @sort="handleSort" />
                    <TableHeader :label="$t('customer_service_block.sent_by')" sortKey="sent_by" :currentSortBy="sortBy"
                        :sortDesc="sortDesc" @sort="handleSort" />
                    <TableHeader :label="$t('common.doc')" :sortable="false" />
                </div>

                <div v-if="pending">
                    <AppLoading :text="$t('common.loading')" :size="40" />
                </div>
                <div v-else-if="error">
                    <p>Error: {{ error.message }}</p>
                    <p><button @click="getData" class="underline text-sky-500 hover:no-underline">
                            {{ $t('common.load_again')
                            }}</button></p>
                </div>
                <div v-else>
                    <div v-for="item in items" :key="item.id" @click="selectRemittance(item)"
                        class="grid grid-cols-[auto,75px,1fr,45px,150px,75px,80px,60px] gap-3 text-base border-b items-center transition-all duration-300 ease cursor-pointer hover:bg-gray-50"
                        :class="{
                            'bg-yellow-50 ml-2': selectedRemittances.includes(item.id),
                            'bg-white': !selectedRemittances.includes(item.id)
                        }">
                        <span>
                            <Icon name="fa6-solid:check" class="text-sky-500 transition-all duration-300 ease" :class="{
                                'h-0 w-0': !selectedRemittances.includes(item.id),
                                'h-3.5 w-3.5 ml-2': selectedRemittances.includes(item.id),
                            }" />
                        </span>
                        <span class="p-1 text-nowrap">{{ formatDate(item.created_at) }}</span>
                        <span class="p-1 truncate">{{ item.token }}</span>
                        <span @click.stop>
                            <button
                                class="group flex justify-between w-full hover:cursor-help hover:bg-yellow-50 items-center p-1 text-sky-500 text-nowrap text-left"
                                @click="showDetail(item);">
                                <abbr :title="item.token" class="no-underline">{{ item.total_payments }}</abbr>
                                <Icon name="fa6-solid:eye"
                                    class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
                            </button>
                        </span>
                        <span class="p-1 text-nowrap">
                            <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                        </span>
                        <span class="p-1">{{ item.sent_at ? formatDate(item.sent_at) : '-' }}</span>
                        <span class="p-1">{{ item.sent_by_username ? item.sent_by_username : '-' }}</span>

                        <button @click.stop @click="printDocument(item.document)" class="w-5 h-5 rounded-full border border-orange-500 text-orange-500 bg-orange-50 hover:bg-orange-100 mx-auto">
                            <Icon name="fa6-solid:download" class="m-auto w-3 h-3" />
                        </button>

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

        <div v-if="SubRegion == true" role="region" id="subregion"
            class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
            :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
            <div id="region_nav" class="px-3">
                <button @click="toggleRegion(false)"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <PaymentsList v-if="detail" :remittance_id="detail" :info="detail_data" />
            </div>
        </div>
    </div>

</template>
