<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import Pagination from '~/components/molecules/Pagination.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const { $ContractApiService } = useNuxtApp();

const props = defineProps({
    isSubRegion: Boolean,
    personId: {
        type: Number,
        required: true
    },
    // Show a "Download XLSX" button that exports exactly the rows/columns shown.
    exportable: {
        type: Boolean,
        default: true
    },
    exportFileName: {
        type: String,
        default: 'person_contracts'
    }
});

const emit = defineEmits(['show-detail']);

const showDetail = (component, id) => {
    emit('show-detail', component, id);
}

const allContracts = ref([]);
const loading = ref(false);

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
    { header: t('common.role'), value: (row) => row.person_role?.map(r => t('common.roles.' + r)).join(', ') || '-' },
    { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
    { header: t('contract'), value: (row) => row.token, key: 'token' },
    { header: t('supply_point'), value: (row) => row.supply_point, key: 'supply_point' },
    { header: t('common.debt'), value: (row) => Number(row.debt_amount ?? 0), key: 'debt_amount' },
]);

const pagination = ref({
    page: 1,
    perPage: 50,
    total: 0,
    totalPages: 0,
    isFiltered: false
});

const fetchContracts = async () => {
    loading.value = true;
    try {
        const res = await $ContractApiService.getAll(
            '', // query
            [], // filters
            pagination.value.page, 
            null, // sort
            false, // desc
            [], // variable_type_id
            [], // bonification_type_id
            [], // client_type_ids
            [], // use_type_ids
            [], // category_ids
            [], // product_ids
            [], // debt_management_types
            false, // is_checked
            [], // comm_types
            '', // search_all_address
            [], // payment_type_ids
            [props.personId], // person_ids
            '', // search_by_address
            null, // total_persons_min
            null, // holder
            'all' // role
        );
        
        allContracts.value = res.results;
        pagination.value.total = res.count;
        pagination.value.totalPages = Math.ceil(res.count / pagination.value.perPage);
    } catch (err) {
        console.error("Error fetching contracts:", err);
    } finally {
        loading.value = false;
    }
}

const onPageChange = (newPage) => {
    pagination.value.page = newPage;
    fetchContracts();
}

onMounted(() => {
    fetchContracts();
});

watch(() => props.personId, () => {
    pagination.value.page = 1;
    fetchContracts();
});

</script>

<template>
    <div class="contracts-list-container">
        <div v-if="loading" class="flex justify-center p-8">
            <AppLoading :text="t('common.loading')" />
        </div>
        <div v-else>
            <div v-if="exportable && allContracts?.length > 0" class="flex justify-end mb-1">
                <AtomsDownloadXlsxButton :rows="allContracts" :columns="exportColumns" :file-name="exportFileName" />
            </div>
            <div class="m-4 rounded-md border border-gray-300 divide-y bg-white overflow-hidden">
                <div class="group grid grid-cols-[1fr,1fr,2fr,2fr,1fr] divide-x text-sm leading-4 bg-gray-50 border-b">
                    <span class="p-3 font-semibold text-slate-600"> {{ t('common.role') }} </span>
                    <span class="p-3 font-semibold text-slate-600"> {{ t('common.status') }} </span>
                    <span class="p-3 font-semibold text-slate-600 flex items-center"> {{ t('contract') }} </span>
                    <span class="p-3 font-semibold text-slate-600 flex items-center"> {{ t('supply_point') }} </span>
                    <span class="p-3 font-semibold text-slate-600 flex items-center"> {{ t('common.debt') }} </span>
                </div>
                
                <div v-if="allContracts.length === 0" class="p-8 text-center text-gray-500 italic">
                    {{ t('common.no_records') }}
                </div>
                
                <div v-for="item in allContracts" :key="item.id"
                    class="group grid grid-cols-[1fr,1fr,2fr,2fr,1fr] divide-x text-sm leading-4 transition-all duration-100 hover:bg-slate-50 border-b last:border-b-0">
                    <div class="p-3 text-slate-500">
                        {{ item.person_role?.map(r => t('common.roles.' + r)).join(', ') || '-' }}
                    </div>
                    <div class="p-3">
                        <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                    </div>
                    <div class="p-3">
                        <button v-if="!props.isSubRegion" @click="showDetail('ContractRegion', item.id)"
                            class="text-start text-sky-500 underline font-medium hover:text-sky-700 transition-colors">
                            {{ item.token }}
                        </button>
                        <span v-else class="font-medium text-slate-700">{{ item.token }}</span>
                    </div>
                    <div class="p-3">
                        <button v-if="!props.isSubRegion" @click="showDetail('SupplyPointRegion', item.supply_point_id)"
                            class="text-start text-sky-500 underline hover:text-sky-700 transition-colors">
                            {{ item.supply_point }}
                        </button>
                        <span v-else class="text-slate-600">{{ item.supply_point }}</span>
                    </div>
                    <div class="p-3">
                        <span :class="{ 
                            'text-green-600 font-medium': item.debt_amount === 0,
                            'text-red-600 font-bold': item.debt_amount > 0
                            }">
                            {{ formatMoneyWithCurrency(item.debt_amount) }}
                        </span>
                    </div>
                </div>
                
                <div class="p-2 bg-gray-50 border-t" v-if="pagination.totalPages > 1">
                    <Pagination :pagination="pagination" @update:page="onPageChange" />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.contracts-list-container {
    width: 100%;
}
</style>