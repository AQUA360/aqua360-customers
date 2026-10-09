<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ContractRequestRegion from '~/components/organisms/ContractRequestRegion.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import JoinedPaymentRegion from '~/components/organisms/JoinedPaymentRegion.vue';
import AddInvoices from '~/components/molecules/AddInvoices.vue';
import SearchWalletMovements from '../molecules/SearchWalletMovements.vue';

const toast = useToast();
const { t } = useI18n();
const { $PaymentApiService } = useNuxtApp();
const loading_data = ref(false);
const error_data = ref(false);

const props = defineProps({
    save_data: {
        type: Boolean,
        default: false
    }
});

const totalInvoices = ref(0)
const totalCommitments = ref(0)
const totalJoinedPayments = ref(0)

const sepaFile = ref(null);
const allPayments = ref([]);
const data = ref(null);
const dataNoInfo = ref(null);
const expandedJoinedPayments = ref(new Set());

const paid_payments = ref(false);
const showRegionDetailComponent = ref(null)
const regionDetailId = ref(null)
const SubRegion = ref(false)

const documentExists = ref(false);
const paymentOrigin = ref(null);
const paymentOrigins = [
    { id: 'box_office', name: t('billing_block.box_office') },
    { id: 'post_office', name: t('billing_block.post_office') }
];

const emit = defineEmits(['changed', 'doc_exists']);

const isPaymentVisible = (item) => {
    if (item.joined_payment_id && !item.is_joined) return false;
    return item.contract || item.contract_request || item.invoice || item.commitment_deposit || item.is_joined;
};

const getChildPayments = (joinedPaymentId) => {
    return allPayments.value.filter(
        item => item.joined_payment_id === joinedPaymentId && !item.is_joined
    );
};

const getJoinedChildCount = (joinedPaymentId) => getChildPayments(joinedPaymentId).length;

const toggleJoinedPayment = (joinedPaymentId) => {
    const next = new Set(expandedJoinedPayments.value);
    if (next.has(joinedPaymentId)) {
        next.delete(joinedPaymentId);
    } else {
        next.add(joinedPaymentId);
    }
    expandedJoinedPayments.value = next;
};

const isJoinedExpanded = (joinedPaymentId) => expandedJoinedPayments.value.has(joinedPaymentId);

const isChildPayment = (payment) => Boolean(payment.joined_payment_id && !payment.is_joined);

const isJoinedParent = (payment) => Boolean(payment.is_joined && !isChildPayment(payment));

const getJoinedGroupMeta = (payment) => {
    if (!isChildPayment(payment)) return { isFirst: false, isLast: false, isOnly: false };
    const children = getChildPayments(payment.joined_payment_id);
    const idx = children.findIndex(c => c.payment_id === payment.payment_id);
    return {
        isFirst: idx === 0,
        isLast: idx === children.length - 1,
        isOnly: children.length === 1,
    };
};

const getRowClasses = (element) => {
    if (isChildPayment(element)) {
        const { isFirst, isLast } = getJoinedGroupMeta(element);
        return [
            'bg-slate-50/95',
            isFirst ? 'shadow-[inset_2px_0_0_0_rgb(148_163_184)]' : 'shadow-[inset_2px_0_0_0_rgb(203_213_225)]',
            isLast ? 'border-b border-slate-200/90' : '',
        ];
    }
    if (isJoinedParent(element) && isJoinedExpanded(element.joined_payment_id)) {
        return ['bg-white border-b-0 shadow-[inset_2px_0_0_0_rgb(100_116_139)]'];
    }
    if (isJoinedParent(element)) {
        return ['bg-white shadow-[inset_2px_0_0_0_rgb(148_163_184)]'];
    }
    return ['bg-white'];
};

const linkBtnClass = 'inline-flex items-center gap-1 text-sm font-medium text-sky-600 hover:text-sky-800 hover:underline underline-offset-2 max-w-full truncate';

const displayRows = computed(() => {
    if (!data.value) return [];
    const rows = [];
    for (const item of data.value) {
        rows.push(item);
        if (item.is_joined && item.joined_payment_id && isJoinedExpanded(item.joined_payment_id)) {
            rows.push(...getChildPayments(item.joined_payment_id));
        }
    }
    return rows;
});

const getData = async (file, is_saving = false) => {
    if (!paymentOrigin.value && is_saving) {
        toast.error(t('billing_block.payment_origin_required'));
        return;
    }
    loading_data.value = true;
    error_data.value = false;
    if (is_saving) saveBalance();
    data.value = []
    allPayments.value = []
    expandedJoinedPayments.value = new Set();
    paid_payments.value = false;
    try {

        sepaFile.value = file;
        let save_data = {
            file: file,
            is_saving: is_saving,
            payment_origin: paymentOrigin.value,
        };
        
        let response = await $PaymentApiService.returnBank(save_data);
        documentExists.value = response.document_exists;
        allPayments.value = response.data.map(item => ({ ...item, save_balance: false }));
        data.value = allPayments.value.filter(isPaymentVisible);
        dataNoInfo.value = response.data.filter(item =>
            !item.contract && !item.contract_request && !item.invoice && !item.commitment_deposit && !item.is_joined
        );
        totalInvoices.value = response.data.reduce((sum, invoice) => {
            if (invoice.invoice) {
                sum += 1;
            }
            return sum;
        }, 0);
        totalCommitments.value = response.data.reduce((sum, invoice) => {
            if (invoice.commitment_deposit) {
                sum += 1;
            }
            return sum;
        }, 0);
        totalJoinedPayments.value = response.data.reduce((sum, item) => {
            if (item.is_joined) {
                sum += 1;
            }
            return sum;
        }, 0);
        if (response.data.some(item => item.is_paid)) {
            paid_payments.value = true;
        }
        emit('doc_exists', response.document_exists);
    } catch (error) {
        console.error('Error saving document:', error);
        error_data.value = true;
    } finally {
        loading_data.value = false;
    }
}

const saveBalance = async () => {
    

    const save_balance_data = allPayments.value.filter(item => item.save_balance);

    /* if (save_balance_data.length === 0) {
        toast.error(t('billing_block.no_payments_selected'));
        return;
    } */

    try {
        const save_data = {
            payments: save_balance_data.map(item => item.payment_id),
            payment_origin: paymentOrigin.value,
        };

        let response = await $PaymentApiService.saveBankBalance(save_data);
        if (response) {
            toast.success(t('common.correct_save'));
            getData(sepaFile.value, false);
        } else {
            toast.error(t('common.error'));
            getData(sepaFile.value, false);
        }
    } catch (error) {
        console.error('Error saving balance:', error);
    }
}

const openRegion = (component, id) => {
    closeSubRegion();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showSubRegion();
}

const closeSubRegion = function () {
    SubRegion.value = false;
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    emit('show-subregion', false);
}
const showSubRegion = function () {
    SubRegion.value = true;
    emit('show-subregion', true);
}

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

const formatPaymentDate = (dateStr) => {
    if (!dateStr || dateStr.length !== 6) return dateStr || "-";

    const day = dateStr.substring(0, 2);
    const month = dateStr.substring(2, 4);
    const year = dateStr.substring(4, 6);

    // Assuming 20XX for the year
    return `${day}/${month}/20${year}`;
}

watch(() => props.save_data, (newValue) => {
    getData(sepaFile.value, true);
});

</script>

<template>
    <div class="px-4 py-2">
        <div class="flex items-center gap-3 mb-3 pb-2 border-b border-slate-200">
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-sky-600">
                <Icon name="fa6-solid:arrow-rotate-left" class="h-4 w-4" />
            </div>
            <div class="flex-1 min-w-0">
                <h1 class="text-lg font-semibold text-slate-900 tracking-tight">
                    {{ t("billing_block.return_bank") }}
                </h1>
                <p class="mt-0.5 text-xs text-slate-500 truncate">
                    {{ t("billing_block.enter_return_bank_doc") }}
                    <span class="font-medium text-slate-600">
                        <em>{{ $t('billing_block.n57') }}</em> · <em>RND</em>
                    </span>
                </p>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-2">
            <div class="px-4 py-3 bg-slate-50 rounded-xl border border-slate-200/80 shadow-sm">
                <div class="flex items-center justify-between gap-3 mb-3">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:upload" class="text-sky-600 text-sm" />
                        <span class="text-sm font-medium text-slate-700">{{ t("common.doc") }}</span>
                    </div>
                </div>
                <div class="mb-4">
                    <label class="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1 px-1">
                        {{ t('billing_block.payment_origin') }}
                    </label>
                    <div class="relative group">
                        <select v-model="paymentOrigin" 
                            class="w-full pl-3 pr-10 py-2 text-sm bg-white border border-slate-200 rounded-xl shadow-sm appearance-none focus:border-sky-500 focus:ring-4 focus:ring-sky-500/10 transition-all cursor-pointer hover:border-slate-300">
                            <option :value="null" disabled>{{ t('common.select') }}...</option>
                            <option v-for="origin in paymentOrigins" :key="origin.id" :value="origin.id">
                                {{ origin.name }}
                            </option>
                        </select>
                        <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400 group-hover:text-slate-500">
                            <Icon name="fa6-solid:chevron-down" class="h-3 w-3" />
                        </div>
                    </div>
                </div>

                <AtomsInputFile @update="getData" :name="'sepaFile'" :uploaded="null" :fullWidth="true"
                    class="w-full" />
                <p class="mt-2 text-[11px] leading-snug text-slate-500">
                    {{ t("billing_block.enter_return_bank_doc") }}
                </p>
            </div>

            <div v-if="data && data.length > 0" class="flex flex-col items-end gap-2 text-xs">
                <div class="flex flex-wrap justify-end gap-2">
                    <div
                        class="inline-flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1 border border-slate-200">
                        <span class="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                            {{ t("common.total") }}
                        </span>
                        <span class="text-sm font-semibold text-slate-900">
                            {{ data.length }}
                        </span>
                    </div>
                    <div v-if="totalInvoices > 0"
                        class="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 border border-sky-100">
                        <span class="text-[11px] font-medium uppercase tracking-wide text-sky-700">
                            {{ t("invoices") }}
                        </span>
                        <span class="text-sm font-semibold text-sky-800">
                            {{ totalInvoices }}
                        </span>
                    </div>
                    <div v-if="totalCommitments > 0"
                        class="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 border border-sky-100">
                        <span class="text-[11px] font-medium uppercase tracking-wide text-sky-700">
                            {{ t("claim_block.commitments") }}
                        </span>
                        <span class="text-sm font-semibold text-sky-800">
                            {{ totalCommitments }}
                        </span>
                    </div>
                    <div v-if="totalJoinedPayments > 0"
                        class="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 border border-sky-100">
                        <span class="text-[11px] font-medium uppercase tracking-wide text-sky-700">
                            {{ t("billing_block.joined_payments") }}
                        </span>
                        <span class="text-sm font-semibold text-sky-800">
                            {{ totalJoinedPayments }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Compact Results -->
        <div v-if="!loading_data && !error_data" class="space-y-3">

            <div v-if="paid_payments || documentExists"
                class="flex items-start gap-2 rounded-lg border border-amber-200/80 bg-amber-50/80 px-3 py-2">
                <Icon name="fa6-solid:circle-info" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                <ul class="min-w-0 space-y-0.5 text-xs font-medium text-amber-900/90">
                    <li v-if="paid_payments">{{ t("informative_block.info_paid_payments") }}</li>
                    <li v-if="documentExists">{{ t("informative_block.info_document_exists") }}</li>
                </ul>
            </div>

            <!-- Payments table -->
            <div v-if="data && data.length > 0"
                class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <div class="overflow-x-auto max-h-[28rem]">
                    <table class="w-full border-collapse text-sm">
                        <thead class="sticky top-0 border-b border-slate-200 bg-slate-100/95 backdrop-blur-sm">
                            <tr class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                                <th v-if="totalJoinedPayments > 0" class="w-8 px-1 py-1.5" :aria-label="t('common.expand')" />
                                <th class="px-2 py-1.5 text-left">{{ t("contract") }}</th>
                                <th v-if="totalInvoices > 0 || totalJoinedPayments > 0" class="px-2 py-1.5 text-left">
                                    <template v-if="totalInvoices > 0 && totalJoinedPayments > 0">
                                        {{ t('invoice') }} / {{ t('billing_block.joined_payment') }}
                                    </template>
                                    <template v-else-if="totalJoinedPayments > 0">
                                        {{ t('billing_block.joined_payment') }}
                                    </template>
                                    <template v-else>
                                        {{ t('common.identification') }} {{ t('invoice') }}
                                    </template>
                                </th>
                                <th v-if="totalCommitments > 0" class="px-2 py-1.5 text-left">
                                    {{ t("claim_block.commitment") }}
                                </th>
                                <th class="px-2 py-1.5 text-left">{{ t("common.actual_status") }}</th>
                                <th class="px-2 w-32 py-1.5 text-left">{{ t("contract_block.owner") }}</th>
                                <th class="px-2 py-1.5 text-left whitespace-nowrap">{{ t("common.amount") }}</th>
                                <th class="w-32 px-2 py-1.5 text-right">{{ t("contract_block.save_balance") }}</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100/90">
                            <tr v-for="(element, index) in displayRows" :key="`${element.payment_id}-${index}`"
                                class="transition-colors hover:bg-slate-50/70"
                                :class="getRowClasses(element)">
                                <td v-if="totalJoinedPayments > 0" class="w-8 px-1 py-1 align-middle">
                                    <button
                                        v-if="isJoinedParent(element)"
                                        type="button"
                                        class="flex h-6 w-6 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700"
                                        :title="`${$t('common.expand')}/${$t('common.collapse')}`"
                                        :aria-expanded="isJoinedExpanded(element.joined_payment_id)"
                                        @click="toggleJoinedPayment(element.joined_payment_id)">
                                        <Icon
                                            :name="isJoinedExpanded(element.joined_payment_id) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'"
                                            class="h-2.5 w-2.5" />
                                    </button>
                                    <div v-else-if="isChildPayment(element)"
                                        class="flex h-6 w-6 items-center justify-center pl-2.5"
                                        aria-hidden="true">
                                        <span class="block h-3 w-px bg-slate-300" />
                                    </div>
                                </td>
                                <td class="px-2 py-1.5 align-middle">
                                    <button v-if="element?.contract?.token" type="button" :class="linkBtnClass"
                                        @click="openRegion('ContractRegion', element.contract.id)">
                                        {{ element.contract.token }}
                                    </button>
                                    <button v-else-if="element?.contract_request?.token" type="button" :class="linkBtnClass"
                                        @click="openRegion('ContractRequestRegion', element.contract_request.id)">
                                        {{ element.contract_request.token }}
                                    </button>
                                    <span v-else class="text-slate-400 text-sm">—</span>
                                </td>
                                <td v-if="totalInvoices > 0 || totalJoinedPayments > 0"
                                    class="px-2 py-1.5 align-middle max-w-[12rem]">
                                    <button
                                        v-if="isJoinedParent(element)"
                                        type="button"
                                        :class="linkBtnClass"
                                        @click="openRegion('JoinedPaymentRegion', element.joined_payment_id)">
                                        <Icon name="fa6-solid:layer-group" class="shrink-0 text-[10px] text-slate-400" />
                                        <span class="truncate">{{ element.reference || "—" }}</span>
                                        <span
                                            v-if="getJoinedChildCount(element.joined_payment_id)"
                                            class="shrink-0 rounded bg-slate-100 px-1 py-px text-[10px] font-semibold tabular-nums text-slate-600">
                                            {{ getJoinedChildCount(element.joined_payment_id) }}
                                        </span>
                                    </button>
                                    <button v-else-if="element?.invoice?.token" type="button" :class="linkBtnClass"
                                        @click="openRegion('InvoiceRegion', element.invoice.id)">
                                        {{ element.invoice.token }}
                                    </button>
                                    <span v-else class="text-slate-400 text-sm">—</span>
                                </td>
                                <td v-if="totalCommitments > 0" class="px-2 py-1.5 align-middle">
                                    <button v-if="element?.commitment_deposit?.token" type="button" :class="linkBtnClass"
                                        @click="openRegion('CommitmentDepositRegion', element?.commitment_deposit?.id)">
                                        {{ element.commitment_deposit.token }}
                                    </button>
                                    <span v-else class="text-slate-400 text-sm">—</span>
                                </td>
                                <td class="px-2 py-1.5 align-middle">
                                    <AtomsColorBadge :value="element.status_name" :color="element.status_color" />
                                </td>
                                <td class="px-2 py-1.5 text-sm text-slate-700 max-w-[10rem] truncate"
                                    :title="element?.contract?.holder || undefined">
                                    {{ element?.contract?.holder || "—" }}
                                </td>
                                <td class="px-2 py-1.5 text-sm font-semibold tabular-nums text-slate-900 whitespace-nowrap">
                                    {{ formatMoneyWithCurrency(element.amount) || "—" }}
                                </td>
                                <td class="px-2 py-1.5 text-center align-middle">
                                    <button
                                        v-if="element.is_paid"
                                        type="button"
                                        :class="[
                                            'inline-flex h-6 w-6 items-center justify-center rounded border transition-colors',
                                            element.save_balance
                                                ? 'border-orange-400 bg-orange-50 text-orange-600'
                                                : 'border-slate-200 bg-white text-slate-400 hover:border-sky-400 hover:text-sky-600',
                                        ]"
                                        @click="element.save_balance = !element.save_balance">
                                        <Icon v-if="element.save_balance" name="fa6-solid:check" class="h-3 w-3" />
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>


            <div v-if="dataNoInfo && dataNoInfo.length > 0"
                class="overflow-hidden rounded-lg border border-red-200/90 bg-white shadow-sm">
                <div class="flex items-center justify-between gap-3 border-b border-red-200/80 bg-red-50/90 px-3 py-2">
                    <div>
                        <h3 class="text-xs font-semibold text-red-800">{{ t("reports_block.paid_payments_no_info") }}</h3>
                        <p class="text-[11px] text-red-600/90">{{ t("informative_block.info_manual_review") }}</p>
                    </div>
                    <span class="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold tabular-nums text-red-800">
                        {{ dataNoInfo.length }}
                    </span>
                </div>

                <div class="overflow-x-auto max-h-64">
                    <table class="w-full border-collapse text-sm">
                        <thead class="sticky top-0 border-b border-red-200/80 bg-red-50/95">
                            <tr class="text-[11px] font-semibold uppercase tracking-wider text-red-800/80">
                                <th class="px-2 py-1.5 text-left">{{ t('common.reference') }}</th>
                                <th class="px-2 py-1.5 text-left">{{ t("billing_block.payment_date") }}</th>
                                <th class="px-2 py-1.5 text-left">{{ t("common.amount") }}</th>
                                <th class="w-10 px-2 py-1.5" />
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100/90">
                            <tr v-for="(element, index) in dataNoInfo" :key="index"
                                class="transition-colors hover:bg-red-50/60">
                                <td class="px-2 py-1.5 text-sm text-slate-800">{{ element.reference || "—" }}</td>
                                <td class="px-2 py-1.5 text-sm text-slate-600 tabular-nums">
                                    {{ formatPaymentDate(element.payment_date) }}
                                </td>
                                <td class="px-2 py-1.5 text-sm font-semibold tabular-nums text-slate-900 whitespace-nowrap">
                                    {{ formatMoneyWithCurrency(element.amount) || "—" }}
                                </td>
                                <td class="px-2 py-1.5 text-right">
                                    <button
                                        type="button"
                                        class="inline-flex h-6 w-6 items-center justify-center rounded border border-red-200 bg-white text-red-600 hover:border-red-400 hover:bg-red-50"
                                        @click="openRegion('SearchWalletMovements', element.amount)">
                                        <Icon name="fa6-solid:eye" class="h-3 w-3" />
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- No Data State -->
            <div v-else-if="data && data.length === 0 && dataNoInfo && dataNoInfo.length === 0"
                class="text-center py-8">
                <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Icon name="fa6-solid:circle-check" class="text-green-600" />
                </div>
                <h3 class="text-sm font-semibold text-slate-800 mb-1">
                    {{ t("common.no_records") }}
                </h3>
                <p class="text-slate-500 text-xs">
                    {{ t("informative_block.info_doc_no_payments") }}
                </p>
            </div>
        </div>

        <!-- Loading State -->
        <div v-if="loading_data" class="text-center py-8">
            <div class="w-12 h-12 bg-sky-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Icon name="fa6-solid:spinner" class="text-sky-600 animate-spin" />
            </div>
            <h3 class="text-sm font-semibold text-slate-800 mb-1">
                {{ t("customer_service_block.in_process") }}
            </h3>
            <p class="text-slate-500 text-xs">
                {{ t("common.loading") }}...
            </p>
        </div>

        <!-- Error State -->
        <div v-if="error_data" class="text-center py-8">
            <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Icon name="fa6-solid:exclamation-triangle" class="text-red-600" />
            </div>
            <h3 class="text-sm font-semibold text-red-800 mb-1">
                {{ t("common.error") }}
            </h3>
            <p class="text-red-600 text-xs mb-3">
                {{ t("common.error_load") }}
            </p>
            <button @click="getData(sepaFile)"
                class="inline-flex items-center px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors">
                <Icon name="fa6-solid:rotate-right" class="mr-1" />
                {{ t("common.load_again") }}
            </button>
        </div>
    </div>

    <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
        :class="{ 'translate-x-0': SubRegion, 'translate-x-[2000px]': !SubRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
        <div id="region_nav" class="mb-3 px-3">
            <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                <Icon name="fa6-solid:angles-right" class="text-slate-500" />
            </button>
        </div>
        <div class="px-10">
            <!-- Subregions aqui -->
            <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
                :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
            <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
                :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
            <ContractRequestRegion v-if="showRegionDetailComponent === 'ContractRequestRegion'" :id="regionDetailId"
                :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
            <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
                :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
            <JoinedPaymentRegion v-if="showRegionDetailComponent === 'JoinedPaymentRegion'" :id="regionDetailId"
                :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
            <AddInvoices v-if="showRegionDetailComponent == 'AddInvoices'" :info="true" :total_final="regionDetailId"
                :selected_items="[]" />
            <SearchWalletMovements v-if="showRegionDetailComponent == 'SearchWalletMovements'"
                :total_final="regionDetailId" />
        </div>
    </div>
</template>
