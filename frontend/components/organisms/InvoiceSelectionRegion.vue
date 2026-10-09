<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';

const props = defineProps({
    selectedInvoices: {
        type: Array,
        default: () => []
    },
    checked_invoices: {
        type: Array,
        default: () => []
    },
    as_region: {
        type: Boolean,
        default: false
    },
    disabled: {
        type: Boolean,
        default: false
    }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['update:selected', 'close', 'show-detail']);
const { $ClaimRequestApiService } = useNuxtApp();

const loading = ref(false);
const invoices = ref([]);
const localSelectedInvoices = ref([...props.selectedInvoices]);
const searchQuery = ref('');
const searchInput = ref(null);

const filteredInvoices = computed(() => {
    if (!searchQuery.value) return invoices.value;

    const query = searchQuery.value.toLowerCase();
    return invoices.value.filter(invoice => {
        const token = invoice.token?.toLowerCase() || '';
        const contract_token = invoice.contract?.token?.toLowerCase() || '';
        const contract_request_token = invoice.contract_request?.token?.toLowerCase() || '';
        return token.includes(query) || contract_token.includes(query) || contract_request_token.includes(query);
        
        /* const fullName = `${contract.holder_name} ${contract.holder_surname}`.toLowerCase();
        const holderToken = contract.holder_token?.toLowerCase() || '';
        const contractToken = contract.token?.toLowerCase() || ''; 
    
        return fullName.includes(query) || 
               holderToken.includes(query) || 
               contractToken.includes(query);*/
    });
});

const showDetail = function (component, id) {
    emit('show-detail', component, id);
}

const loadInvoices = async () => {
    loading.value = true;
    invoices.value = props.selectedInvoices;
    localSelectedInvoices.value = props.selectedInvoices.filter(invoice => props.checked_invoices.includes(invoice)).map(invoice => invoice.id);
    await nextTick()
    loading.value = false;
};

const updateSelected = () => {
    emit('update:selected', localSelectedInvoices.value);
};

const closeRegion = () => {
    emit('close');
};

const toggleSelection = (id) => {
    const index = localSelectedInvoices.value.indexOf(id);
    if (index === -1) {
        localSelectedInvoices.value.push(id);
    } else {
        localSelectedInvoices.value.splice(index, 1);
    }
    updateSelected();
};

onMounted(async () => {
    await loadInvoices();
    searchInput.value?.focus();
});

watch(() => props.selectedInvoices, async (newValue) => {
    await loadInvoices();
});

</script>

<template>
    <div class="h-[60vh] overflow-y-auto flex flex-col">
        <div v-if="as_region" class="flex justify-between items-center mb-4">
            <button @click="closeRegion" class="text-gray-500 hover:text-gray-700">
                <Icon name="fa6-solid:xmark" class="text-xl" />
            </button>
        </div>

        <div class="mb-4">

            <div v-if="!disabled" class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
                </div>
                <input ref="searchInput" v-model="searchQuery" type="text" :disabled="disabled"
                    :placeholder="`${$t('dashboard.search')} ${$t('common.identificator')}, ${$t('invoice')}  ${$t('common.or')} ${$t('contract')}`"
                    class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
            </div>
        </div>

        <div class="flex-1 overflow-y-auto">
            <div v-if="loading" class="flex justify-center items-center h-full">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
            </div>
            <div v-else>
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50 sticky top-0">
                        <tr>
                            <th v-if="!disabled" scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('common.selection') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('common.identificator') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('common.status') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('contract') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('billing_block.total_invoice') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('billing_block.total_to_pay') }}
                            </th>
                            <th scope="col"
                                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                {{ $t('common.due_date') }}
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">

                        <tr v-for="invoice in filteredInvoices" :key="invoice.id" class="cursor-pointer" :class="[
                            localSelectedInvoices.includes(invoice.id) && !disabled
                                ? 'bg-yellow-100 bg-opacity-75'
                                : 'hover:bg-gray-50'
                        ]" @click="!disabled ? toggleSelection(invoice.id) : null">
                            <td v-if="!disabled" class="px-6 py-4 whitespace-nowrap">
                                <input type="checkbox" v-model="localSelectedInvoices" :value="invoice.id"
                                    class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                                    @change="updateSelected" @click.stop :disabled="disabled" />
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <!-- ADD OPEN REGION BUTTON -->
                                 <button class="text-sm text-sky-500 underline" @click.stop
                                 @click="showDetail('InvoiceRegion', invoice.id)">
                                    <span>{{ invoice.serie_final }}</span>
                                 </button>
                                <!-- <div class="text-sm text-gray-500">{{ invoice.token }}</div> -->
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="font-medium">
                                    <AtomsColorBadge :value="invoice.status?.name?invoice.status.name:invoice?.status_name" :color="invoice.status?.color? invoice.status.color: invoice?.status_color" />
                                </div>
                            </td>
                            
                            <td v-if="invoice.contract" class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">{{ invoice.contract.token }}</div>
                            </td>
                            <td v-else-if="invoice.contract_request" class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">{{ invoice.contract_request.token }}</div>
                            </td>
                            <td v-else class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">-</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">{{ formatMoneyWithCurrency(invoice.total_final) }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">{{ formatMoneyWithCurrency(invoice.left_to_pay) }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-500">{{ formatDate(invoice.due_date) }}</div>
                            </td>

                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>