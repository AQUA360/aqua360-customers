<script setup>
import { ref, onMounted, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

// Llista de retorns SEPA per triar-ne un o diversos (p. ex. com a origen d'un procés de comunicació).
const props = defineProps({
    selected_ids: {
        type: Array,
        default: () => []
    },
});
const emit = defineEmits(['item-clicked']);

const { t } = useI18n();
const { $SepaRemittanceReturnApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('created_at');
const sortDesc = ref(true);
const pagination = ref({
    page: 1,
    perPage: 50,
    total: 0,
    totalPages: 0,
    previous: null,
    next: null,
    isFiltered: false
});

const getData = async () => {
    pending.value = true;
    error.value = null;
    try {
        const data = await $SepaRemittanceReturnApiService.getAll(
            searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value
        );
        items.value = data.results;
        Object.assign(pagination.value, {
            total: data.count,
            totalPages: Math.ceil(data.count / pagination.value.perPage),
            previous: data.previous,
            next: data.next,
            isFiltered: String(searchInput.value).trim() !== ''
        });
    } catch (err) {
        error.value = err;
    } finally {
        pending.value = false;
    }
}

const debouncedGetData = debounce(getData, 300);

const handleSort = (key) => {
    if (sortBy.value === key) {
        sortDesc.value = !sortDesc.value;
    } else {
        sortBy.value = key;
        sortDesc.value = false;
    }
    getData();
}

const handlePageChange = (newPage) => {
    pagination.value.page = newPage;
    getData();
}

watch(searchInput, () => {
    pagination.value.page = 1;
    debouncedGetData();
});

onMounted(getData);
</script>

<template>
    <div>
        <H1Region class="mb-2">{{ $t('reports_block.select_sepa_return') }}</H1Region>
        <div class="mb-3 text-base border-b border-gray-400 flex items-center gap-2 w-80">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" type="text" :placeholder="$t('dashboard.search')"
                class="w-full p-1 rounded-md focus:outline-none" autocomplete="off" />
        </div>

        <div class="grid gap-3 text-base border-b items-center"
            style="grid-template-columns: 24px 90px 1fr 80px 100px 90px;">
            <span></span>
            <TableHeader :label="$t('common.creation')" sortKey="created_at" :currentSortBy="sortBy"
                :sortDesc="sortDesc" @sort="handleSort" />
            <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy"
                :sortDesc="sortDesc" @sort="handleSort" />
            <TableHeader :label="$t('billing_block.payments')" :sortable="false" />
            <TableHeader :label="$t('billing_block.total_amount')" :sortable="false" />
            <TableHeader :label="$t('common.returned')" sortKey="return_date" :currentSortBy="sortBy"
                :sortDesc="sortDesc" @sort="handleSort" />
        </div>
        <div v-if="pending">
            <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
        </div>
        <div v-else>
            <button v-for="item in items" :key="item.id" type="button"
                class="grid gap-3 w-full text-left text-base border-b items-center hover:bg-slate-100"
                :class="{ 'bg-yellow-50': selected_ids.includes(item.id) }"
                style="grid-template-columns: 24px 90px 1fr 80px 100px 90px;"
                @click="emit('item-clicked', item)">
                <span class="p-1 flex items-center">
                    <input type="checkbox" :checked="selected_ids.includes(item.id)" class="pointer-events-none" tabindex="-1" />
                </span>
                <span class="p-1 text-nowrap">{{ formatDate(item.created_at) }}</span>
                <span class="p-1 text-sky-500 truncate" :title="item.token">{{ item.token }}</span>
                <span class="p-1">{{ item.total_payments }}</span>
                <span class="p-1">{{ formatMoneyWithCurrency(item.total_amount) }}</span>
                <span class="p-1">{{ item.return_date ? formatDate(item.return_date) : '-' }}</span>
            </button>
            <div v-if="items.length === 0" class="my-3">
                <p>{{ $t('common.no_records') }}</p>
            </div>
        </div>
        <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
</template>
