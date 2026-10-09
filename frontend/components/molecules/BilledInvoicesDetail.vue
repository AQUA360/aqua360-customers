<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '../atoms/FieldDetail.vue';
import AppLoading from '../atoms/AppLoading.vue';
import ColorBadge from '../atoms/ColorBadge.vue';
import FilterSelect from '../atoms/FilterSelect.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import InvoiceRegion from '../organisms/InvoiceRegion.vue';

const { t, te } = useI18n();
const toast = useToast();
const { $InvoiceApiService, $BillingApiService, $ConfiglistApiService } = useNuxtApp();

const props = defineProps({
    billingId: [String, Number],
    type: String,
    isFinished: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['selection-change', 'reload']);

const TYPE_TITLE_KEYS = {
    all_billed: 'billing_block.billed_outside_billing',
    confirmed_invoices: 'billing_block.confirmed_invoices',
    pending_budgets: 'billing_block.pending_budgets',
    found_match: 'billing_block.found_match_invoice'
};

const loading = ref(false);
const loadingDecision = ref(false);
const invoices = ref([]);
const selectedInvoices = ref([]);

const searchQuery = ref('');
const selectedReasonFilters = ref([]);
const selectedBudgetTypeFilters = ref([]);
const selectedOtherManagementsFilters = ref([]);
const selectedInvoiceStatusFilters = ref([]);
const selectedContractStatusFilters = ref([]);
const selectedContractInBillingFilters = ref([]);

const contractStatuses = ref([]);
const invoiceStatuses = ref([]);

const BUDGET_FILTER_BUDGET = 'is_budget';
const BUDGET_FILTER_INVOICE = 'not_is_budget';
const NO_OTHER_MANAGEMENTS_FILTER = 'hide_other_managements';
const OTHER_MANAGEMENTS_TYPES = ['contract_request', 'contract_termination'];
const CONTRACT_IN_BILLING_FILTER = 'contract_in_billing';
const NOT_CONTRACT_IN_BILLING_FILTER = 'not_contract_in_billing';

const showSubRegion = ref(false);
const regionDetailId = ref(null);
const showRegionDetailComponent = ref(null);
const isSubRegionOpen = ref(false);

const title = computed(() => {
    const key = TYPE_TITLE_KEYS[props.type];
    return key ? t(key) : t('billing_block.billed_invoices');
});

const availableFilters = computed(() => {
    const reasons = new Set();

    invoices.value.forEach((invoice) => {
        if (!Array.isArray(invoice?.reasons)) return;

        invoice.reasons.forEach((reason) => {
            if (typeof reason === 'string' && reason.trim()) {
                reasons.add(reason);
            }
        });
    });

    return Array.from(reasons);
});

const hasOtherManagements = (invoice) => OTHER_MANAGEMENTS_TYPES.includes(invoice?.other_managements);

const otherManagementsTypeLabel = (value) => {
    if (value === 'contract_request') return t('contract_request');
    if (value === 'contract_termination') return t('contract_termination');
    return t('billing_block.other_managements');
};

const otherManagementsLabel = (invoice) => otherManagementsTypeLabel(invoice?.other_managements);

const hasOtherManagementsInvoices = computed(() => invoices.value.some(hasOtherManagements));

const selectedIds = (filters) => filters.map((item) => String(item.id));

const matchesSelectedIds = (filters, value) => {
    if (!filters.length) return true;
    return selectedIds(filters).includes(String(value));
};

const statusOptionsFromInvoices = (idKey, nameKey, configList) => {
    const byId = new Map();

    invoices.value.forEach((invoice) => {
        const id = invoice?.[idKey];
        if (id == null || id === '') return;
        const key = String(id);
        if (!byId.has(key)) {
            byId.set(key, { id, name: invoice[nameKey] || key });
        }
    });

    configList.forEach((status) => {
        const key = String(status.id);
        if (byId.has(key)) {
            const existing = byId.get(key);
            byId.set(key, { id: existing.id, name: status.name || existing.name });
        }
    });

    return Array.from(byId.values());
};

const budgetTypeFilterOptions = computed(() => [
    { id: BUDGET_FILTER_BUDGET, name: t('billing_block.show_budgets') },
    { id: BUDGET_FILTER_INVOICE, name: t('billing_block.show_invoices') }
]);

const contractInBillingFilterOptions = computed(() => [
    { id: CONTRACT_IN_BILLING_FILTER, name: t('billing_block.show_contract_in_billing') },
    { id: NOT_CONTRACT_IN_BILLING_FILTER, name: t('billing_block.show_not_contract_in_billing') }
]);

const otherManagementsFilterOptions = computed(() => {
    const presentTypes = new Set(
        invoices.value
            .map((invoice) => invoice?.other_managements)
            .filter((value) => OTHER_MANAGEMENTS_TYPES.includes(value))
    );

    const options = OTHER_MANAGEMENTS_TYPES
        .filter((type) => presentTypes.has(type))
        .map((type) => ({ id: type, name: otherManagementsTypeLabel(type) }));

    if (options.length) {
        options.push({
            id: NO_OTHER_MANAGEMENTS_FILTER,
            name: t('billing_block.no_other_managements')
        });
    }

    return options;
});

const reasonFilterOptions = computed(() => availableFilters.value.map((reason) => ({
    id: reason,
    name: getReasonLabel(reason)
})));

const invoiceStatusFilterOptions = computed(() =>
    statusOptionsFromInvoices('invoice_status_id', 'invoice_status_name', invoiceStatuses.value)
);

const contractStatusFilterOptions = computed(() =>
    statusOptionsFromInvoices('contract_status_id', 'contract_status_name', contractStatuses.value)
);

const displayedInvoices = computed(() => {
    const query = searchQuery.value.trim().toLowerCase();
    const hasSearch = query.length > 0;
    const reasonIds = selectedIds(selectedReasonFilters.value);
    const hasFilters = reasonIds.length > 0;
    const budgetIds = selectedIds(selectedBudgetTypeFilters.value);
    const showBudgets = budgetIds.includes(BUDGET_FILTER_BUDGET);
    const showInvoices = budgetIds.includes(BUDGET_FILTER_INVOICE);
    const hasBudgetTypeFilter = showBudgets || showInvoices;
    const otherManagementIds = selectedIds(selectedOtherManagementsFilters.value);
    const selectedOtherManagementTypes = otherManagementIds.filter((id) => OTHER_MANAGEMENTS_TYPES.includes(id));
    const hasOtherManagementTypeFilter = selectedOtherManagementTypes.length > 0;
    const hideOtherManagements = !hasOtherManagementTypeFilter && otherManagementIds.includes(NO_OTHER_MANAGEMENTS_FILTER);
    const hasInvoiceStatusFilter = selectedInvoiceStatusFilters.value.length > 0;
    const hasContractStatusFilter = selectedContractStatusFilters.value.length > 0;
    const contractInBillingIds = selectedIds(selectedContractInBillingFilters.value);
    const showContractInBilling = contractInBillingIds.includes(CONTRACT_IN_BILLING_FILTER);
    const showNotContractInBilling = contractInBillingIds.includes(NOT_CONTRACT_IN_BILLING_FILTER);
    const hasContractInBillingFilter = showContractInBilling || showNotContractInBilling;

    if (!hasSearch && !hasFilters && !hasBudgetTypeFilter && !hasOtherManagementTypeFilter && !hideOtherManagements && !hasInvoiceStatusFilter && !hasContractStatusFilter && !hasContractInBillingFilter) {
        return invoices.value;
    }

    return invoices.value.filter((invoice) => {
        if (hasSearch) {
            const serie = String(invoice?.invoice_serie_final ?? '').toLowerCase();
            const token = String(invoice?.invoice_token ?? '').toLowerCase();
            const contract_token = String(invoice?.contract_token ?? '').toLowerCase();
            const holder_name = String(invoice?.contract_holder_name ?? '').toLowerCase();
            if (!serie.includes(query) && !token.includes(query) && !contract_token.includes(query) && !holder_name.includes(query)) return false;
        }

        if (hasBudgetTypeFilter) {
            const matchesBudget = showBudgets && invoice.is_budget;
            const matchesInvoice = showInvoices && !invoice.is_budget;
            if (!matchesBudget && !matchesInvoice) return false;
        }

        if (hasOtherManagementTypeFilter && !selectedOtherManagementTypes.includes(invoice?.other_managements)) return false;
        if (hideOtherManagements && hasOtherManagements(invoice)) return false;

        if (hasInvoiceStatusFilter && !matchesSelectedIds(selectedInvoiceStatusFilters.value, invoice.invoice_status_id)) {
            return false;
        }

        if (hasContractStatusFilter && !matchesSelectedIds(selectedContractStatusFilters.value, invoice.contract_status_id)) {
            return false;
        }

        if (hasContractInBillingFilter) {
            const matchesInBilling = showContractInBilling && invoice.contract_in_billing;
            const matchesNotInBilling = showNotContractInBilling && !invoice.contract_in_billing;
            if (!matchesInBilling && !matchesNotInBilling) return false;
        }

        if (hasFilters) {
            if (!Array.isArray(invoice?.reasons)) return false;
            return invoice.reasons.some((reason) => reasonIds.includes(String(reason)));
        }

        return true;
    });
});

const hasContractInBilling = (invoice) => Boolean(props.isFinished && invoice?.contract_in_billing);

const canDeleteBudget = (invoice) => Boolean(invoice?.is_budget && invoice?.found_match);

const canConfirmBudget = (invoice) => {
    if (!invoice?.is_budget) return false;
    if (hasContractInBilling(invoice)) return false;
    if (!invoice.found_match) return true;
    return Boolean(invoice.found_match.is_preinvoice);
};

const canMoveToBilling = (invoice) => Boolean(invoice?.is_budget && !invoice.found_match && !props.isFinished);

const canMoveInvoiceToBilling = (invoice) => Boolean(!invoice?.is_budget && props.isFinished && !invoice.found_match && !invoice.contract_in_billing);

const canSelectInvoice = (invoice) => {
    return canConfirmBudget(invoice) || canDeleteBudget(invoice) || canMoveToBilling(invoice) || canMoveInvoiceToBilling(invoice);
};

const selectableInvoices = computed(() => displayedInvoices.value.filter(canSelectInvoice));

const allSelected = computed(() => {
    return selectableInvoices.value.length > 0 && selectedInvoices.value.length === selectableInvoices.value.length;
});

const selectedInvoiceObjects = computed(() => {
    const ids = new Set(selectedInvoices.value);
    return invoices.value.filter((invoice) => ids.has(invoice.invoice_id) && canSelectInvoice(invoice));
});

const selectedBulkActions = computed(() => {
    const items = selectedInvoiceObjects.value;
    return {
        confirm: items.filter(canConfirmBudget),
        moveToBilling: items.filter(canMoveToBilling),
        moveInvoiceToBilling: items.filter(canMoveInvoiceToBilling),
        deleteBudget: items.filter(canDeleteBudget)
    };
});

const showBulkActions = computed(() => {
    const actions = selectedBulkActions.value;
    return actions.confirm.length > 0 || actions.moveToBilling.length > 0 || actions.moveInvoiceToBilling.length > 0 || actions.deleteBudget.length > 0;
});

const hasMultipleBudgets = (invoice) => Boolean(invoice?.multiple_budgets && invoice?.is_budget);

const selectedDuplicateContractTokens = computed(() => {
    const byContract = new Map();

    selectedInvoiceObjects.value.forEach((invoice) => {
        const contractId = invoice?.contract_id;
        if (contractId == null) return;
        const current = byContract.get(contractId);
        if (current) {
            current.count += 1;
            return;
        }
        byContract.set(contractId, {
            token: invoice.contract_token || String(contractId),
            count: 1
        });
    });

    return Array.from(byContract.values())
        .filter((item) => item.count > 1)
        .map((item) => item.token);
});

const selectedHasDuplicateContracts = computed(() => selectedDuplicateContractTokens.value.length > 0);

const duplicateContractsWarning = computed(() => {
    if (!selectedHasDuplicateContracts.value) return '';
    return `${t('billing_block.multiple_budgets_bulk_warning')} ${selectedDuplicateContractTokens.value.join(', ')}`;
});

const bulkActionsDisabled = computed(() => loadingDecision.value || selectedHasDuplicateContracts.value);

const legendFlags = computed(() => {
    const flags = {
        deleteVsInvoice: false,
        deleteBoth: false,
        confirm: false,
        invoiceVsBudget: false,
        moveToBilling: false,
        moveInvoiceToBilling: false,
        multipleBudgets: false,
        otherManagements: false,
        contractInBilling: false
    };

    displayedInvoices.value.forEach((invoice) => {
        if (hasMultipleBudgets(invoice)) {
            flags.multipleBudgets = true;
        }
        if (hasOtherManagements(invoice)) {
            flags.otherManagements = true;
        }
        if (hasContractInBilling(invoice)) {
            flags.contractInBilling = true;
        }
        if (invoice?.found_match) {
            if (invoice.is_budget && !invoice.found_match.is_preinvoice) {
                flags.deleteVsInvoice = true;
            } else if (!invoice.is_budget && invoice.found_match.is_preinvoice) {
                flags.invoiceVsBudget = true;
            } else if (invoice.is_budget && invoice.found_match.is_preinvoice) {
                flags.deleteBoth = true;
                if (!hasContractInBilling(invoice)) {
                    flags.confirm = true;
                }
            }
        } else if (invoice.is_budget) {
            if (!hasContractInBilling(invoice)) {
                flags.confirm = true;
            }
            if (!props.isFinished) {
                flags.moveToBilling = true;
            }
        } else if (props.isFinished && !invoice.contract_in_billing) {
            flags.moveInvoiceToBilling = true;
        }
    });

    return flags;
});

const showActionsLegend = computed(() => Object.values(legendFlags.value).some(Boolean));

const getReasonLabel = (reason) => {
    if (typeof reason !== 'string') return t('common.no_data');
    const key = `billing_block.cause_${reason}`;
    return te(key) ? t(key) : reason;
};

const loadInvoices = async () => {
    if (!props.billingId) return;
    loading.value = true;
    selectedInvoices.value = [];
    selectedReasonFilters.value = [];
    selectedBudgetTypeFilters.value = [];
    selectedOtherManagementsFilters.value = [];
    selectedInvoiceStatusFilters.value = [];
    selectedContractStatusFilters.value = [];
    selectedContractInBillingFilters.value = [];
    try {
        const res = await $InvoiceApiService.getBilledInvoices(props.billingId, true, props.type);
        invoices.value = Array.isArray(res) ? res : (res?.results || res?.invoices || []);
    } catch (error) {
        console.error(error);
        invoices.value = [];
        toast.error(t('billing_block.error_load_billed_invoices'));
    } finally {
        loading.value = false;
    }
};

const handleBudgetTypeChange = (event) => {
    selectedInvoices.value = [];
    selectedBudgetTypeFilters.value = event;
};

const handleReasonChange = (event) => {
    selectedInvoices.value = [];
    selectedReasonFilters.value = event;
};

const handleInvoiceStatusChange = (event) => {
    selectedInvoices.value = [];
    selectedInvoiceStatusFilters.value = event;
};

const handleContractStatusChange = (event) => {
    selectedInvoices.value = [];
    selectedContractStatusFilters.value = event;
};

const handleOtherManagementsChange = (event) => {
    selectedInvoices.value = [];
    selectedOtherManagementsFilters.value = event;
};

const handleContractInBillingChange = (event) => {
    selectedInvoices.value = [];
    selectedContractInBillingFilters.value = event;
};

const selectAll = () => {
    if (allSelected.value) {
        selectedInvoices.value = [];
        return;
    }

    selectedInvoices.value = selectableInvoices.value.map((invoice) => invoice.invoice_id);
};

const deleteInvoice = async (invoice) => {
    await deleteInvoices([invoice]);
};

const deleteSelectedBudgets = async () => {
    if (selectedHasDuplicateContracts.value) return;
    await deleteInvoices(selectedBulkActions.value.deleteBudget);
};

const deleteInvoices = async (items) => {
    const invoicesToDelete = (items || []).filter(canDeleteBudget);
    if (!invoicesToDelete.length) return;
    if (!confirm(t('billing_block.confirm_delete_budget'))) return;
    loadingDecision.value = true;
    try {
        for (const invoice of invoicesToDelete) {
            await $InvoiceApiService.deleteInvoiceBudget(invoice.invoice_id);
        }
        toast.success(t("common.deleted_successfully"))
        loadInvoices()
    } catch (e) {
        console.error(e)
        toast.error(t("common.delete_failed"))
        loadInvoices()
    } finally {
        loadingDecision.value = false;
    }
};

const moveSelectedBudgetsToBilling = async () => {
    if (selectedHasDuplicateContracts.value) return;
    await moveBudgetToPreInvoice(selectedBulkActions.value.moveToBilling.map((invoice) => invoice.invoice_id));
};

const moveBudgetToPreInvoice = async (budget_ids) => {
    if (!budget_ids?.length) return;
    if (!confirm(t('confirmation_text_block.confirm_move_to_billing_as_preinvoice'))) return;
    loadingDecision.value = true;
    try {
        const payload = {
            budget_ids: budget_ids
        }
        const response = await $BillingApiService.moveBudgetToPreInvoice(props.billingId, payload)
        if (response) {
            toast.success(t("common.saved_successfully"))
            loadInvoices()
            emit('reload')
        }
    } catch (e) {
        console.error(e)
        toast.error(t("common.error"))
    } finally {
        loadingDecision.value = false;
    }
};

const moveSelectedInvoicesToBilling = async () => {
    if (selectedHasDuplicateContracts.value) return;
    await moveInvoiceToBilling(selectedBulkActions.value.moveInvoiceToBilling.map((invoice) => invoice.invoice_id));
};

const moveInvoiceToBilling = async (invoice_ids) => {
    const allowedIds = (invoice_ids || []).filter((id) => {
        const invoice = invoices.value.find((item) => item.invoice_id === id);
        return invoice && canMoveInvoiceToBilling(invoice);
    });
    if (!allowedIds.length) return;
    if (!confirm(t('confirmation_text_block.confirm_move_invoice_to_billing'))) return;
    loadingDecision.value = true;
    try {
        const payload = {
            invoice_ids: allowedIds
        }
        const response = await $BillingApiService.moveInvoiceToBilling(props.billingId, payload)
        if (response) {
            toast.success(t("common.saved_successfully"))
            loadInvoices()
            emit('reload')
        }
    } catch (e) {
        console.error(e)
        toast.error(t("common.error"))
    } finally {
        loadingDecision.value = false;
    }
};

const confirmInvoice = async (invoice) => {
    await confirmInvoices([invoice]);
};

const confirmSelectedBudgets = async () => {
    if (selectedHasDuplicateContracts.value) return;
    await confirmInvoices(selectedBulkActions.value.confirm);
};

const confirmInvoices = async (items) => {
    const invoicesToConfirm = (items || []).filter(canConfirmBudget);
    if (!invoicesToConfirm.length) return;
    if (!confirm(t('confirmation_text_block.confirm_invoice_budget'))) return;
    loadingDecision.value = true;
    try {
        const payload = {
            budget_ids: invoicesToConfirm.map((invoice) => invoice.invoice_id)
        }
        await $BillingApiService.generateInvoiceBudget(props.billingId, payload);
        toast.success(t("common.saved_successfully"))
        loadInvoices()
        emit('reload')
    } catch (e) {
        console.error(e)
        toast.error(t("common.error"))
        loadInvoices()
    } finally {
        loadingDecision.value = false;
    }
};

const openSubRegion = (component, id) => {
    if (!id) return;
    showSubRegion.value = true;
    regionDetailId.value = id;
    showRegionDetailComponent.value = component;
};

const closeSubRegion = () => {
    showSubRegion.value = false;
    regionDetailId.value = null;
    showRegionDetailComponent.value = null;
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const fetchConfigData = async (service, entity, targetArray, loading = null) => {
    if (loading) {
        loading.value = true;
    }
    try {
        const data = await $ConfiglistApiService.getAll(service + '/' + entity);
        targetArray.value = [];
        if (data.results) {
            data.results.forEach(item => {
                const option = {
                    id: item.id,
                    name: item.name,
                    token: item.token,
                };
                if (entity === 'vulnerability-request-type') {
                    option.variable_types = item.variable_types;
                    option.bonification_types = item.bonification_types;
                    option.duration = item.duration;
                    option.vulnerability_level = item.vulnerability_level;
                }
                if (entity === 'variable-type') {
                    option.data_type = item.data_type;
                }
                if (entity === 'bonification-type') {
                    option.variable_types = item.variable_types;
                }
                targetArray.value.push(option);
            });
        }
    } catch (error) {
        console.error(`Error fetching ${entity}:`, error);
    } finally {
        if (loading) {
            loading.value = false;
        }
    }
};

const loadConfigData = async () => {
    await fetchConfigData('contract', 'contract-status', contractStatuses);
    await fetchConfigData('billing', 'invoice-status', invoiceStatuses);
};

onMounted(() => {
    loadConfigData();
});

watch(selectedInvoices, (value) => {
    emit('selection-change', [...value]);
}, { deep: true });

watch([() => props.billingId, () => props.type], () => {
    loadInvoices();
}, { immediate: true });

</script>

<template>
    <div class="region__content h-full min-h-0">
        <!-- <div v-if="loading" class="h-full min-h-[400px] flex flex-col items-center justify-center p-6 text-center">
            <AppLoading :text="$t('common.loading')" />
        </div> -->
        <div class="pr-2 relative pb-24 h-full min-h-0 flex flex-col">
            <section class="flex flex-col h-full min-h-0">
                <header class="mb-3 flex flex-wrap items-center justify-between gap-3 pb-1">
                    <h2 class="text-lg font-semibold text-slate-900">{{ title }}</h2>
                    <div class="flex items-center gap-2">
                        <button @click="loadInvoices"
                            class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                            :title="t('common.refresh')">
                            <Icon name="fa6-solid:rotate-right" class="text-xs text-slate-500" />
                            {{ t('common.refresh') }}
                        </button>
                        <span
                            class="inline-flex items-center rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-700">
                            {{ invoices.length }}
                        </span>
                    </div>
                </header>

                <div class="my-2 flex flex-wrap items-center justify-between gap-2 relative z-20">
                    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1">
                        <span class="input-group flex flex-start items-center gap-2 w-52">
                            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                            <input v-model="searchQuery" id="searchBilledInvoices" type="text" name="search"
                                :placeholder="$t('common.start_search')"
                                class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
                                autocomplete="off" />
                        </span>
                        <FilterSelect :options="budgetTypeFilterOptions" :filters="selectedBudgetTypeFilters"
                            :multiple="true" :placeholder="t('common.type')"
                            @update:modelValue="handleBudgetTypeChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:cube" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                        <FilterSelect v-if="reasonFilterOptions.length" :options="reasonFilterOptions"
                            :filters="selectedReasonFilters" :multiple="true" :placeholder="t('common.reasons')"
                            @update:modelValue="handleReasonChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:list" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                        <FilterSelect v-if="invoiceStatusFilterOptions.length" :options="invoiceStatusFilterOptions"
                            :filters="selectedInvoiceStatusFilters" :multiple="true"
                            :placeholder="`${t('invoice')}: ${t('common.statuses')}`"
                            @update:modelValue="handleInvoiceStatusChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                        <FilterSelect v-if="contractStatusFilterOptions.length" :options="contractStatusFilterOptions"
                            :filters="selectedContractStatusFilters" :multiple="true"
                            :placeholder="`${t('contract')}: ${t('common.statuses')}`"
                            @update:modelValue="handleContractStatusChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:file-contract" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                        <FilterSelect v-if="hasOtherManagementsInvoices" :options="otherManagementsFilterOptions"
                            :filters="selectedOtherManagementsFilters" :multiple="true"
                            :placeholder="t('billing_block.other_managements')"
                            @update:modelValue="handleOtherManagementsChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:circle-info" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                        <FilterSelect v-if="props.isFinished" :options="contractInBillingFilterOptions"
                            :filters="selectedContractInBillingFilters" :multiple="true"
                            :placeholder="t('billing_block.contract_in_billing_filter')"
                            @update:modelValue="handleContractInBillingChange($event)">
                            <template #icon>
                                <Icon name="fa6-solid:file-circle-check" class="text-md ml-2 mr-1" size="10px" />
                            </template>
                        </FilterSelect>
                    </div>
                    <div class="flex items-center gap-x-2">
                        <button @click="selectAll()" :disabled="selectableInvoices.length === 0"
                            class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                            :class="{ 'cursor-not-allowed opacity-50': selectableInvoices.length === 0 }">
                            <Icon :name="allSelected ? 'fa6-solid:square-check' : 'fa6-solid:check-double'"
                                class="text-sm" />
                            {{ allSelected ? $t('common.deselect') : $t('common.select') }} {{
                                $t('common.all').toLowerCase() }}
                        </button>
                        <span class="text-xs text-slate-500">
                            {{ selectedInvoices.length }} {{ t('common.selected') }}
                        </span>
                    </div>
                </div>

                <div v-if="!loading && !loadingDecision && showActionsLegend" class="mb-3">
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">
                            {{ t('common.legend') }}
                        </span>
                        <span v-if="legendFlags.deleteVsInvoice || legendFlags.deleteBoth"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-rose-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-50 text-rose-500">
                                <Icon name="fa6-solid:trash" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none">
                                <span class="font-medium text-slate-700">{{ t('billing_block.delete_budget') }}</span>
                                <span class="mx-1.5 text-slate-300">·</span>
                                <span class="text-slate-500">{{ t('billing_block.legend_delete_budget') }}</span>
                            </span>
                        </span>
                        <span v-if="legendFlags.confirm"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-emerald-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-500">
                                <Icon name="fa6-solid:circle-check" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none">
                                <span class="font-medium text-slate-700">{{ props.isFinished ?
                                    t('billing_block.confirm_budget_add_billing') : t('billing_block.confirm_budget')
                                    }}</span>
                                <span v-if="!props.isFinished" class="mx-1.5 text-slate-300">·</span>
                                <span v-if="!props.isFinished" class="text-slate-500">{{
                                    t('billing_block.legend_confirm_budget') }}</span>
                            </span>
                        </span>
                        <span v-if="legendFlags.invoiceVsBudget"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-amber-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-500">
                                <Icon name="fa6-solid:triangle-exclamation" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none text-slate-500">
                                {{ t('billing_block.legend_invoice_vs_budget') }}
                            </span>
                        </span>
                        <span v-if="legendFlags.moveToBilling"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-sky-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-50 text-sky-500">
                                <Icon name="fa6-solid:file-invoice" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none">
                                <span class="font-medium text-slate-700">{{
                                    t('billing_block.move_to_billing_as_preinvoice') }}</span>
                                <span class="mx-1.5 text-slate-300">·</span>
                                <span class="text-slate-500">{{ t('billing_block.legend_move_to_billing') }}</span>
                            </span>
                        </span>
                        <span v-if="legendFlags.moveInvoiceToBilling"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-sky-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-50 text-sky-500">
                                <Icon name="fa6-solid:file-invoice" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none">
                                <span class="font-medium text-slate-700">{{
                                    t('billing_block.move_invoice_to_billing') }}</span>
                            </span>
                        </span>
                        <span v-if="legendFlags.multipleBudgets"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-amber-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-500">
                                <Icon name="fa6-solid:circle-info" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none text-slate-500">
                                {{ t('billing_block.multiple_budgets') }}
                            </span>
                        </span>
                        <span v-if="legendFlags.otherManagements"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-sky-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-50 text-sky-500">
                                <Icon name="fa6-solid:circle-info" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none text-slate-500">
                                {{ t('billing_block.other_managements_info') }}
                            </span>
                        </span>
                        <span v-if="legendFlags.contractInBilling"
                            class="inline-flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-2.5 ring-1 ring-inset ring-violet-300/80">
                            <span
                                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-50 text-violet-500">
                                <Icon name="fa6-solid:ban" class="text-[9px]" />
                            </span>
                            <span class="text-[11px] leading-none text-slate-500">
                                {{ t('billing_block.contract_in_billing') }}
                            </span>
                        </span>
                    </div>
                </div>


                <div v-if="showBulkActions && !loadingDecision" class="mb-2 flex flex-wrap items-center gap-2 rounded-md border px-2 py-2"
                    :class="selectedHasDuplicateContracts ? 'border-amber-300 bg-amber-50' : 'border-sky-200 bg-sky-50/70'">
                    <p v-if="selectedHasDuplicateContracts"
                        class="inline-flex w-full items-center gap-1.5 text-[11px] font-medium text-amber-800">
                        <Icon name="fa6-solid:triangle-exclamation" class="text-[10px] shrink-0" />
                        <span>
                            {{ t('billing_block.multiple_budgets_bulk_warning') }}
                            <span class="font-semibold italic">{{ selectedDuplicateContractTokens.join(', ') }}</span>
                        </span>
                    </p>
                    <button v-if="selectedBulkActions.confirm.length > 0" type="button" @click="confirmSelectedBudgets"
                        :disabled="bulkActionsDisabled" :title="duplicateContractsWarning || undefined"
                        class="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700 shadow-sm transition-colors hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50">
                        <Icon name="fa6-solid:circle-check" class="text-[10px]" />
                        {{ t('billing_block.confirm_budget') }} ({{ selectedBulkActions.confirm.length }})
                    </button>
                    <button v-if="selectedBulkActions.moveToBilling.length > 0 && !props.isFinished" type="button"
                        @click="moveSelectedBudgetsToBilling" :disabled="bulkActionsDisabled"
                        :title="duplicateContractsWarning || undefined"
                        class="inline-flex items-center gap-1.5 rounded-md border border-sky-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-700 shadow-sm transition-colors hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50">
                        <Icon name="fa6-solid:file-invoice" class="text-[10px]" />
                        {{ t('billing_block.move_to_billing_as_preinvoice') }} ({{
                            selectedBulkActions.moveToBilling.length }})
                    </button>
                    <button v-if="selectedBulkActions.moveInvoiceToBilling.length > 0" type="button"
                        :disabled="bulkActionsDisabled" @click="moveSelectedInvoicesToBilling"
                        :title="duplicateContractsWarning || undefined"
                        class="inline-flex items-center gap-1.5 rounded-md border border-sky-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-700 shadow-sm transition-colors hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50">
                        <Icon name="fa6-solid:file-invoice" class="text-[10px]" />
                        {{ t('billing_block.move_invoice_to_billing') }} ({{
                            selectedBulkActions.moveInvoiceToBilling.length }})
                    </button>
                    <button v-if="selectedBulkActions.deleteBudget.length > 0" type="button"
                        @click="deleteSelectedBudgets" :disabled="bulkActionsDisabled"
                        :title="duplicateContractsWarning || undefined"
                        class="inline-flex items-center gap-1.5 rounded-md border border-rose-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-rose-700 shadow-sm transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50">
                        <Icon name="fa6-solid:trash" class="text-[10px]" />
                        {{ t('billing_block.delete_budget') }} ({{ selectedBulkActions.deleteBudget.length }})
                    </button>
                </div>
                <hr v-if="showBulkActions && !loadingDecision" class="my-2.5 border-slate-200">


                <div v-if="loading || loadingDecision"
                    class="h-full min-h-[400px] flex flex-col items-center justify-center p-6 text-center">
                    <AppLoading :text="$t('common.loading')" />
                </div>

                <div v-else class="flex-1 overflow-y-auto min-h-0 pr-1 pb-1">
                    <div v-if="displayedInvoices.length > 0" class="space-y-2">
                        <article v-for="invoice in displayedInvoices" :key="invoice.invoice_id"
                            class="rounded-lg border shadow-sm transition-all hover:shadow-md"
                            :class="selectedInvoices.includes(invoice.invoice_id) ? 'border-sky-300 bg-sky-50/60' : 'border-slate-200'">
                            <div class="flex justify-between items-start gap-2 m-2.5">
                                <div class="min-w-0 flex flex-wrap items-center gap-2">
                                    <button @click="openSubRegion('InvoiceRegion', invoice.invoice_id)"
                                        class="text-start font-semibold text-sky-500 underline">
                                        {{ invoice.invoice_serie_final || invoice.invoice_token }}
                                    </button>
                                    <AtomsRedirectButton :id="invoice.invoice_id" :path="'/billing/invoice/'" />
                                    <ColorBadge v-if="!invoice.is_budget" :value="invoice.invoice_status_name"
                                        :color="invoice.invoice_status_color || 'gray'" />
                                    <span v-if="invoice.is_budget"
                                        class="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                                        {{ t('common.budget_detail') }}
                                    </span>
                                    <span v-if="hasMultipleBudgets(invoice)"
                                        class="inline-flex items-center gap-1 rounded-md bg-amber-50 py-1 px-2 text-[10px] font-semibold text-amber-800"
                                        :title="t('billing_block.multiple_budgets')">
                                        <Icon name="fa6-solid:circle-info" class="text-[10px]" />
                                        {{ t('billing_block.multiple_budgets') }}
                                    </span>
                                    <span v-if="hasOtherManagements(invoice)"
                                        class="inline-flex items-center gap-1 rounded-md bg-sky-50 py-1 px-2 text-[10px] font-semibold text-sky-800"
                                        :title="t('billing_block.other_managements_info')">
                                        <Icon name="fa6-solid:circle-info" class="text-[10px]" />
                                        {{ otherManagementsLabel(invoice) }}
                                    </span>
                                    <span v-if="hasContractInBilling(invoice)"
                                        class="inline-flex items-center gap-1 rounded-md bg-violet-50 py-1 px-2 text-[10px] font-semibold text-violet-800"
                                        :title="t('billing_block.contract_in_billing')">
                                        <Icon name="fa6-solid:ban" class="text-[10px]" />
                                        {{ t('billing_block.contract_in_billing') }}
                                    </span>
                                </div>
                                <input type="checkbox" v-model="selectedInvoices" :value="invoice.invoice_id"
                                    :disabled="!canSelectInvoice(invoice)"
                                    class="form-checkbox mt-1 h-4 w-4 shrink-0 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                                    :class="{ 'cursor-not-allowed opacity-40': !canSelectInvoice(invoice) }">
                            </div>

                            <div class="mt-2 grid gap-x-6 gap-y-1 border-t border-slate-100 pt-2 sm:grid-cols-2 m-2.5">
                                <FieldDetail :label="$t('billing_block.issue_date')"
                                    :value="invoice.issue_date ? formatDate(invoice.issue_date) : '-'" />
                                <FieldDetail :label="$t('billing_block.total_invoice')"
                                    :value="formatMoneyWithCurrency(invoice.total || 0)" />
                                <FieldDetail :label="$t('contract')" :value="invoice.contract_token"
                                    class="flex items-center">
                                    <div v-if="invoice.contract_id" class="flex gap-2 items-center">
                                        <button @click="openSubRegion('ContractRegion', invoice.contract_id)"
                                            class="text-start text-sky-500 underline">
                                            {{ invoice.contract_token }}
                                        </button>
                                        <AtomsRedirectButton :id="invoice.contract_id" :path="'/contract/contracts/'" />
                                        <AtomsColorBadge :color="invoice.contract_status_color"
                                            :value="invoice.contract_status_name" />
                                    </div>
                                    <div v-else class="text-slate-500">-</div>
                                </FieldDetail>
                                <FieldDetail :label="$t('common.holder')" :value="invoice.contract_holder_name" />
                            </div>

                            <div
                                class="mt-2 border-t border-slate-100 pt-2 flex flex-col gap-2 sm:flex-row sm:justify-between m-2.5">
                                <div class="flex-1">
                                    <p class="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                        {{ t('readings') }}
                                    </p>
                                    <ul v-if="Array.isArray(invoice.readings) && invoice.readings.length > 0"
                                        class="flex flex-wrap gap-1.5">
                                        <li v-for="reading in invoice.readings" :key="reading.reading_id"
                                            class="inline-flex items-center gap-1.5 rounded-md bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-slate-200">
                                            <span class="font-mono">{{ formatDate(reading.reading_date) }}</span>
                                            <span class="inline-flex items-center gap-1"
                                                :class="reading.in_billing_batch ? 'text-emerald-600' : 'text-slate-400'">
                                                <Icon
                                                    :name="reading.in_billing_batch ? 'fa6-solid:circle-check' : 'fa6-solid:circle-xmark'" />
                                                {{ t('billing_block.in_billing_batch') }}
                                            </span>
                                            <span class="inline-flex items-center gap-1"
                                                :class="reading.in_period ? 'text-emerald-600' : 'text-slate-400'">
                                                <Icon
                                                    :name="reading.in_period ? 'fa6-solid:circle-check' : 'fa6-solid:circle-xmark'" />
                                                {{ t('billing_block.in_period') }}
                                            </span>
                                        </li>
                                    </ul>
                                    <p v-else class="text-xs text-slate-500">{{ t('common.no_data') }}</p>
                                </div>
                                <div class="flex-1">
                                    <p class="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                        {{ t('common.reasons') }}
                                    </p>
                                    <ul v-if="Array.isArray(invoice.reasons) && invoice.reasons.length > 0"
                                        class="flex flex-wrap gap-1">
                                        <li v-for="(reason, idx) in invoice.reasons"
                                            :key="`${invoice.invoice_id}-${reason}-${idx}`"
                                            class="inline-flex max-w-full items-center rounded-md bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-slate-200">
                                            {{ getReasonLabel(reason) }}
                                        </li>
                                    </ul>
                                    <p v-else class="text-xs text-slate-500">{{ t('common.no_data') }}</p>
                                </div>
                            </div>
                            <div v-if="invoice.found_match"
                                class="mt-2 border-t border-slate-100 pt-2 bg-slate-100 p-2.5">
                                <p class="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                    {{ t('common.duplicate') }} ({{ invoice.found_match.is_preinvoice ?
                                        t('billing_block.pre_invoice') : t('invoice') }})
                                </p>
                                <div class="flex flex-wrap items-center gap-2">
                                    <button type="button"
                                        @click="openSubRegion('InvoiceRegion', invoice.found_match.id)"
                                        class="inline-flex max-w-full items-center gap-1.5 rounded-md border border-sky-500 bg-sky-500 px-2.5 py-1 text-[11px] font-semibold text-white shadow-sm transition-colors hover:bg-sky-700 hover:border-sky-700">
                                        <Icon name="fa6-solid:file-invoice" class="text-[10px]" />
                                        {{ invoice.found_match.serie_final }} ({{
                                            formatMoneyWithCurrency(invoice.found_match.total_final) }})
                                    </button>
                                    <span v-if="!invoice.is_budget && invoice.found_match.is_preinvoice"
                                        class="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800"
                                        :title="t('billing_block.duplicate_info_invoice_vs_budget')">
                                        <Icon name="fa6-solid:triangle-exclamation" class="text-[10px]" />
                                    </span>
                                    <button v-if="invoice.is_budget && !invoice.found_match.is_preinvoice"
                                        type="button" @click="deleteInvoice(invoice)"
                                        :title="t('billing_block.duplicate_info_budget_vs_invoice')"
                                        class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-rose-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-rose-700 shadow-sm transition-colors hover:bg-rose-50">
                                        <Icon name="fa6-solid:trash" class="text-[10px]" />
                                        {{ t('billing_block.delete_budget') }}
                                    </button>
                                    <template v-else-if="invoice.is_budget && invoice.found_match.is_preinvoice">
                                        <button type="button" @click="deleteInvoice(invoice)"
                                            :title="t('billing_block.duplicate_info_delete_both_budgets')"
                                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-rose-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-rose-700 shadow-sm transition-colors hover:bg-rose-50">
                                            <Icon name="fa6-solid:trash" class="text-[10px]" />
                                            {{ t('billing_block.delete_budget') }}
                                        </button>
                                        <button v-if="canConfirmBudget(invoice)" type="button" @click="confirmInvoice(invoice)"
                                            :title="t('billing_block.duplicate_info_confirm_both_budgets')"
                                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700 shadow-sm transition-colors hover:bg-emerald-50">
                                            <Icon name="fa6-solid:circle-check" class="text-[10px]" />
                                            {{ t('billing_block.confirm_budget') }}
                                        </button>
                                    </template>
                                </div>
                            </div>
                            <div v-else-if="(invoice.is_budget && canConfirmBudget(invoice)) || canMoveInvoiceToBilling(invoice)">
                                <hr class="mt-1.5 border-slate-200">
                                <div class="mt-2 p-2.5">
                                    <div v-if="invoice.is_budget && canConfirmBudget(invoice)" class="flex flex-wrap items-center gap-2">
                                        <button type="button" @click="confirmInvoice(invoice)"
                                            :title="t('billing_block.duplicate_info_confirm_both_budgets')"
                                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700 shadow-sm transition-colors hover:bg-emerald-50">
                                            <Icon name="fa6-solid:circle-check" class="text-[10px]" />
                                            {{ props.isFinished ? t('billing_block.confirm_budget_add_billing') :
                                                t('billing_block.confirm_budget') }}
                                        </button>
                                        <button v-if="!props.isFinished" type="button"
                                            @click="moveBudgetToPreInvoice([invoice.invoice_id])"
                                            :title="t('billing_block.move_to_billing_as_preinvoice_info')"
                                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-sky-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-700 shadow-sm transition-colors hover:bg-sky-50">
                                            <Icon name="fa6-solid:file-invoice" class="text-[10px]" />
                                            {{ t('billing_block.move_to_billing_as_preinvoice') }}
                                        </button>
                                    </div>
                                    <div v-else-if="canMoveInvoiceToBilling(invoice)"
                                        class="flex flex-wrap items-center gap-2">
                                        <button type="button"
                                            @click="moveInvoiceToBilling([invoice.invoice_id])"
                                            :title="t('billing_block.move_invoice_to_billing')"
                                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-sky-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-700 shadow-sm transition-colors hover:bg-sky-50">
                                            <Icon name="fa6-solid:file-invoice" class="text-[10px]" />
                                            {{ t('billing_block.move_invoice_to_billing') }}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </article>
                    </div>

                    <div v-else
                        class="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500">
                        {{ t('common.no_results') }}
                    </div>
                </div>
            </section>
        </div>
        <div role="region" id="right_over_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-30 shadow overflow-y-auto scrollbar-hide"
            :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion, 'w-[98%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen}">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
                <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
                    :isSubRegion="true" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
                <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
                    :isSubRegion="true" />
            </div>
        </div>
    </div>
</template>
