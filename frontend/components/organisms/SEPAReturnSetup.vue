<script setup>
import { ca } from 'date-fns/locale';
import { useI18n } from 'vue-i18n';


const props = defineProps({
    save_response: {
        type: Boolean,
        default: false
    },
    returned_data: {
        type: Array,
        default: () => []
    }
});

const { t } = useI18n();
const { $PaymentApiService } = useNuxtApp();
const pending = ref(true);
const loading_rejections = ref(false);
const error_rejections = ref(false);
const error = ref(null);

const selectedReturnPayments = ref([])
const selectedClaimPayments = ref([])
const openClientIdDropdown = ref(null)

const totalInvoices = ref(0)
const totalCommitments = ref(0)

const sepaFile = ref(null);
const rejections = ref(null);
const ogMsgId = ref(null);
const not_found_rejections = ref(null);
const save = ref(false)

const allSelectedReturnPayments = computed(() => {
    return rejections.value.every(rejection => selectedReturnPayments.value.includes(rejection.payment_id))
})
const allSelectedClaimPayments = computed(() => {
    return rejections.value.every(rejection => selectedClaimPayments.value.includes(rejection.payment_id))
})

const emit = defineEmits(['changed', 'show-detail', 'update-file']);


const getData = async (filters = []) => {
    pending.value = true;
    error.value = null;
    try {

    } catch (err) {
        error.value = err;
    } finally {
        pending.value = false;
    }
}

const getRejections = async (file) => {
    loading_rejections.value = true;
    rejections.value = []
    // La selecció és sempre del fitxer que s'està carregant. Si no es buida,
    // carregar un segon fitxer sense recarregar la pàgina arrossega els
    // pagaments marcats del fitxer anterior i la gestió d'impagats que es crea
    // al desar surt acumulada (els de la devolució nova + els de les anteriors).
    selectedClaimPayments.value = []
    selectedReturnPayments.value = []
    try {
        sepaFile.value = file;
        emit('update-file', file);
        let save_data = {
            file: file,
        };
        let response = await $PaymentApiService.returnSEPA(save_data);
        ogMsgId.value = response.og_msg_id;
        rejections.value = response.rejections.filter(rejection => !rejection.not_found);
        not_found_rejections.value = response.rejections.filter(rejection => rejection.not_found);
        totalInvoices.value = response.rejections.reduce((sum, rejection) => {
            if (rejection.invoice) {
                sum += 1;
            }
            return sum;
        }, 0);
        totalCommitments.value = response.rejections.reduce((sum, rejection) => {
            if (rejection.commitment_deposit) {
                sum += 1;
            }
            return sum;
        }, 0);
        const mapped_rejections = mapRejections(rejections.value);
        console.log('mapped_rejections', mapped_rejections);
        console.log('selectedReturnPayments', selectedReturnPayments.value);
        console.log('selectedClaimPayments', selectedClaimPayments.value);
        emit('changed', mapped_rejections, selectedReturnPayments.value, selectedClaimPayments.value, ogMsgId.value);

    } catch (error) {
        console.error('Error saving document:', error);
        error_rejections.value = true;
    } finally {
        loading_rejections.value = false;
        error_rejections.value = false;
    }
}

const mapRejections = (rejections) => {
    const mapped_rejections = rejections.map(rejection => ({
        'id': rejection.payment_id,
        'motive_id': rejection.motive_id,
        'motive':rejection.motive,
        'skip_return': rejection.skip_return,
        'rjt_dt': rejection.rjt_dt
    }));
    return mapped_rejections;
}

// En canviar la selecció s'ha de reenviar el mateix que en carregar el fitxer (rjt_dt i og_msg_id
// inclosos): si no, el pare es queda sense data de retorn i el backend no té cap data per filtrar.
const emitSelectionChanged = () => {
    const mapped_rejections = mapRejections(rejections.value.filter(rejection => !rejection.skip_return));
    emit('changed', mapped_rejections, selectedReturnPayments.value, selectedClaimPayments.value, ogMsgId.value);
}

const selectAllForInvoices = () => {
    if (allSelectedReturnPayments.value) {
        selectedReturnPayments.value = [];
    } else {
        selectedReturnPayments.value = rejections.value.map(rejection => rejection.payment_id);
        if (selectedClaimPayments.value.length > 0) {
            selectedClaimPayments.value = [];
        }
    }
    emitSelectionChanged();
}

const addOrRemoveReturnPayment = (payment_id) => {
    if (selectedReturnPayments.value.includes(payment_id)) {
        selectedReturnPayments.value = selectedReturnPayments.value.filter(id => id !== payment_id);
    } else {
        selectedReturnPayments.value.push(payment_id);
        if (selectedClaimPayments.value.includes(payment_id)) {
            selectedClaimPayments.value = selectedClaimPayments.value.filter(id => id !== payment_id);
        }
    }
    emitSelectionChanged();
}

const addOrRemoveClaimPayment = (payment_id) => {
    if (selectedClaimPayments.value.includes(payment_id)) {
        selectedClaimPayments.value = selectedClaimPayments.value.filter(id => id !== payment_id);
    } else {
        selectedClaimPayments.value.push(payment_id);
        if (selectedReturnPayments.value.includes(payment_id)) {
            selectedReturnPayments.value = selectedReturnPayments.value.filter(id => id !== payment_id);
        }
    }
    emitSelectionChanged();
}

const selectAllForClaims = () => {
    if (allSelectedClaimPayments.value) {
        selectedClaimPayments.value = [];
    } else {
        selectedClaimPayments.value = rejections.value.map(rejection => rejection.payment_id);
        if (selectedReturnPayments.value.length > 0) {
            selectedReturnPayments.value = [];
        }
    }
    emitSelectionChanged();
}

const showDetail = (region, id) => {
    emit('show-detail', region, id);
}

const toggleClientIdDropdown = (clientId) => {
    if (openClientIdDropdown.value === clientId) {
        openClientIdDropdown.value = null;
    } else {
        openClientIdDropdown.value = clientId;
    }
}

const closeClientIdDropdown = () => {
    openClientIdDropdown.value = null;
}


onMounted(() => {
    getData();
});

watch(() => props.save_response, (newValue) => {
    if (newValue !== save.value && props.returned_data) {
        save.value = newValue;
        rejections.value = props.returned_data;
        mapRejections(props.returned_data);
        // Un cop desat, la selecció ja s'ha aplicat: buidar-la (i avisar-ne el
        // pare) perquè tornar a prémer Desar no creï una segona gestió
        // d'impagats amb els mateixos pagaments.
        selectedClaimPayments.value = [];
        selectedReturnPayments.value = [];
        emit('changed', mapRejections(rejections.value), selectedReturnPayments.value, selectedClaimPayments.value, ogMsgId.value);
    }
});


</script>

<template>
    <div class="px-4 py-2" @click="closeClientIdDropdown">
        <div class="flex items-center gap-3 mb-4 pb-3 border-b border-slate-200">
            <div>
                <h1 class="text-xl font-bold text-slate-800">
                    {{ t("billing_block.return_sepa") }}
                </h1>
                <p class="text-slate-500 text-sm">
                    {{ t("billing_block.enter_return_bank_doc") }}
                </p>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <div class="mb-4 px-4 py-2 bg-slate-50 rounded-lg border border-slate-200">
                <div class="flex items-center gap-2 mb-2">
                    <Icon name="fa6-solid:upload" class="text-sky-600 text-sm" />
                    <span class="text-sm font-medium text-slate-700">{{ t("common.doc_sepa") }}</span>
                </div>
                <AtomsInputFile @update="getRejections" :name="'sepaFile'" :uploaded="null" :fullWidth="true"
                    class="w-full" />
            </div>

            <div v-if="rejections && rejections.length > 0" class="grid grid-cols-2 gap-3 mb-3">
                <!-- Caixeta unificada: invoices + commitments + total -->
                <div class="bg-sky-50 border border-sky-200 rounded-lg p-3">
                    <div v-if="totalInvoices > 0" class="flex items-center justify-between mb-1">
                        <span class="text-sm text-sky-700 font-medium">{{ t("invoices") }}</span>
                        <span class="text-lg font-bold text-sky-800">{{ totalInvoices }}</span>
                    </div>
                    <div v-if="totalCommitments > 0" class="flex items-center justify-between mb-1">
                        <span class="text-sm text-sky-700 font-medium">{{ t("claim_block.commitments") }}</span>
                        <span class="text-lg font-bold text-sky-800">{{ totalCommitments }}</span>
                    </div>
                    <div class="flex items-center justify-between border-t border-sky-200 pt-1 mt-1">
                        <span class="text-sm text-red-700 font-medium">{{ t("common.total") }}</span>
                        <span class="text-lg font-bold text-red-800">{{ rejections.length }}</span>
                    </div>
                </div>
                <!-- Caixeta data de retorn SEPA -->
                <div class="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <div class="flex items-center gap-2 mb-1">
                        <Icon name="fa6-solid:calendar-xmark" class="text-amber-600 text-sm" />
                        <span class="text-sm text-amber-700 font-medium">{{ t("billing_block.sepa_return_date") }}</span>
                    </div>
                    <span class="text-lg font-bold text-amber-800">
                        {{ rejections[0]?.rjt_dt ? formatDate(rejections[0].rjt_dt) : "-" }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Compact Results -->
        <div v-if="!loading_rejections && !error_rejections" class="space-y-3">

            <!-- Compact Table -->
            <div v-if="rejections && rejections.length > 0">
                <div class="bg-white border border-slate-200 rounded-lg overflow-hidden">
                    <div class="px-4 py-2 bg-slate-50 border-b border-slate-200">
                        <div class="flex items-center justify-between">
                            <h3 class="text-sm font-semibold text-slate-700">{{ t("common.return_multiple") }}</h3>
                            <span class="px-2 py-1 bg-red-100 text-red-700 text-sm font-medium rounded">
                                {{ rejections.length }}
                            </span>
                        </div>
                    </div>

                    <div class="overflow-x-auto max-h-96">
                        <table class="w-full text-sm">
                            <thead class="bg-slate-50 border-b border-slate-200">
                                <tr>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("contract") }}
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("billing_block.payment") }}
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        <span v-if="totalInvoices > 0 && totalCommitments > 0">{{ t("invoice") }} / {{ t("claim_block.commitment") }}</span>
                                        <span v-else-if="totalInvoices > 0">{{ t("invoice") }}</span>
                                        <span v-else>{{ t("claim_block.commitment") }}</span>
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("billing_block.payment_date") }}
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("common.amount") }}
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("common.previous_status") }}
                                    </th>
                                    <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        {{ t("order_block.reason") }}
                                    </th>
                                    <th class="px-1 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        <abbr
                                            :title="`${t('informative_block.info_select_claim_invoice')} (${t('common.select')} ${t('common.all')})`"
                                            class="group">
                                            <button :class="{
                                                'bg-white border-slate-500': !allSelectedReturnPayments,
                                                'bg-orange-50 border-orange-500': allSelectedReturnPayments
                                            }" class="h-6 w-6 rounded border group-hover:bg-slate-100 group-hover:border-sky-500"
                                                @click="selectAllForInvoices">
                                                <Icon :class="{
                                                    'text-slate-500': !allSelectedReturnPayments,
                                                    'text-orange-600': allSelectedReturnPayments
                                                }" class="h-3 w-3 group-hover:text-sky-500"
                                                    :name="allSelectedReturnPayments ? 'fa6-solid:check-double' : 'fa6-solid:file-invoice'" />
                                            </button>
                                        </abbr>
                                    </th>
                                    <th class="px-1 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        <abbr
                                            :title="`${t('informative_block.info_select_claim_mng')} (${t('common.select')} ${t('common.all')})`"
                                            class="group">
                                            <button :class="{
                                                'bg-white border-slate-500': !allSelectedClaimPayments,
                                                'bg-orange-50 border-orange-500': allSelectedClaimPayments
                                            }" class="h-6 w-6 rounded border group-hover:bg-slate-100 group-hover:border-sky-500"
                                                @click="selectAllForClaims">
                                                <Icon class="h-3 w-3 group-hover:text-sky-500" :class="{
                                                    'text-slate-500': !allSelectedClaimPayments,
                                                    'text-orange-600': allSelectedClaimPayments
                                                }"
                                                    :name="allSelectedClaimPayments ? 'fa6-solid:check-double' : 'fa-solid:exclamation-circle'" />
                                            </button>
                                        </abbr>
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100">
                                <tr v-for="(element, index) in rejections" :key="index"
                                    class="hover:bg-slate-50 transition-colors">
                                    <td class="px-3 py-2 text-slate-900 font-medium text-sm">
                                        <button v-if="element.contract_id"
                                            class="text-sky-600 hover:text-sky-800 text-sm underline font-medium"
                                            @click="showDetail('ContractRegion', element.contract_id)">
                                            {{ element.contract }}
                                        </button>
                                        <span v-else class="text-slate-400">-</span>
                                    </td>
                                    <td class="px-3 py-2">
                                        <button class="text-sky-600 hover:text-sky-800 text-sm underline"
                                            @click="showDetail('PaymentRegion', element.payment_id)">
                                            {{ element.payment_token || "-" }}
                                        </button>
                                    </td>
                                    <td class="px-3 py-2">
                                        <span v-if="element.invoice"
                                            class="inline-flex items-center px-1.5 py-0.5 rounded text-sm font-medium bg-sky-100 text-sky-800">
                                            {{ element.invoice }}
                                        </span>
                                        <span v-else-if="element.commitment_deposit"
                                            class="inline-flex items-center px-1.5 py-0.5 rounded text-sm font-medium bg-green-100 text-green-800">
                                            {{ element.commitment_deposit }}
                                        </span>
                                        <span v-else class="text-slate-400">-</span>
                                    </td>
                                    <td class="px-3 py-2 text-slate-700 text-sm">
                                        {{ element.payment_date ? formatDate(element.payment_date) : "-" }}
                                    </td>
                                    <td class="px-3 py-2 text-sm font-semibold text-slate-900">
                                        {{ formatMoneyWithCurrency(element.amount) || "-" }}
                                    </td>
                                    <td class="px-3 py-2">
                                        <AtomsColorBadge v-if="element.prev_status" :value="element.prev_status"
                                            :color="element.prev_status_color" />
                                        <span v-else class="text-slate-400 text-sm">-</span>
                                    </td>
                                    <td class="px-3 py-2">
                                        <span
                                            class="inline-flex items-center px-1.5 py-0.5 rounded text-sm font-medium bg-red-100 text-red-800">
                                            {{ element.motive || "-" }}
                                        </span>
                                    </td>
                                    <td class="px-1 py-2">
                                        <abbr :title="`${t('informative_block.info_select_claim_invoice')}`"
                                            class="group">
                                            <button :class="{
                                                'bg-white border-slate-500': !selectedReturnPayments.includes(element.payment_id),
                                                'bg-orange-50 border-orange-500': selectedReturnPayments.includes(element.payment_id)
                                            }" class="rounded border text-sky-600 hover:text-sky-800 h-6 w-6 group-hover:bg-slate-100 group-hover:border-sky-500"
                                                @click="addOrRemoveReturnPayment(element.payment_id)">
                                                <Icon v-if="selectedReturnPayments.includes(element.payment_id)"
                                                    name="fa6-solid:check"
                                                    class="text-orange-600 group-hover:text-sky-800 h-3 w-3" />
                                            </button>
                                        </abbr>
                                    </td>
                                    <td class="px-1 py-2">
                                        <abbr :title="`${t('informative_block.info_select_claim_mng')}`" class="group">
                                            <button :class="{
                                                'bg-white border-slate-500': !selectedClaimPayments.includes(element.payment_id),
                                                'bg-orange-50 border-orange-500': selectedClaimPayments.includes(element.payment_id)
                                            }" class="rounded border text-sky-600 hover:text-sky-800 h-6 w-6 group-hover:bg-slate-100 group-hover:border-sky-500"
                                                @click="addOrRemoveClaimPayment(element.payment_id)">
                                                <Icon v-if="selectedClaimPayments.includes(element.payment_id)"
                                                    name="fa6-solid:check"
                                                    class="text-orange-600 group-hover:text-sky-800 h-3 w-3" />
                                            </button>
                                        </abbr>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="px-2 mt-2">
                    <span class="flex items-center gap-2">
                        <span class="text-slate-400 font-medium">
                            {{ t("billing_block.payments_to_return") }}:
                        </span>
                        {{ rejections.length }}
                    </span>
                    <span class="flex items-center gap-2">
                        <span class="text-slate-400 font-medium">
                            {{ t("billing_block.claim_expenses") }}:
                        </span>
                        {{ selectedReturnPayments.length }}
                    </span>
                    <span class="flex items-center gap-2">
                        <span class="text-slate-400 font-medium">
                            {{ t("claim_block.claim_payments") }}:
                        </span>
                        {{ selectedClaimPayments.length }}
                    </span>
                </div>
            </div>




            <!-- Not Found Rejections - Attention Alert -->
            <details open v-if="not_found_rejections && not_found_rejections.length > 0"
                class="mt-4 border border-red-400 rounded-lg overflow-hidden [&[open]>summary_.arrow]:rotate-180">
                <summary
                    class="px-4 py-3 bg-red-500 cursor-pointer hover:bg-red-600 transition-colors list-none [&::-webkit-details-marker]:hidden">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-white rounded-full flex items-center justify-center animate-pulse">
                                <Icon name="fa6-solid:triangle-exclamation" class="text-red-600 text-lg" />
                            </div>
                            <div>
                                <h3 class="font-bold text-white">
                                    {{ t("common.return_multiple_not_found") }}
                                </h3>
                                <p class="font-medium text-sm text-red-100">{{ t("informative_block.info_manual_review")
                                }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="px-3 py-1.5 bg-white text-red-700 text-sm font-bold rounded-full shadow-md">
                                {{ not_found_rejections.length }}
                            </span>
                            <Icon name="fa6-solid:chevron-down"
                                class="arrow text-white text-sm transition-transform duration-300" />
                        </div>
                    </div>
                </summary>

                <div class="bg-white border-t-4 border-red-500">
                    <div class="overflow-x-auto max-h-80">
                        <table class="w-full text-sm">
                            <thead class="bg-red-50 border-b-2 border-red-200 sticky top-0">
                                <tr>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("contract_block.holder") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("common.amount") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("common.bank_data") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("billing_block.payment_date") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("common.identification") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("order_block.reason") }}
                                    </th>
                                    <th
                                        class="px-3 py-2.5 text-left text-xs font-bold text-red-900 uppercase tracking-wide">
                                        {{ t("invoices") }}
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-red-100">
                                <tr v-for="(element, index) in not_found_rejections" :key="index"
                                    class="hover:bg-red-50 transition-colors border-l-4 border-red-400">
                                    <td class="px-3 py-2.5 text-slate-900 font-semibold text-sm">
                                        {{ element.holder_name || "-" }}
                                    </td>
                                    <td class="px-3 py-2.5 text-sm font-bold text-red-700">
                                        {{ formatMoneyWithCurrency(element.amount) || "-" }}
                                    </td>
                                    <td class="px-3 py-2.5">
                                        <AtomsIBAN :value="element.holder_iban" />
                                    </td>
                                    <td class="px-3 py-2.5 text-slate-700 text-sm font-medium">
                                        {{ formatDate(element.payment_date) || "-" }}
                                    </td>
                                    <td @click.stop class="px-3 py-2.5">
                                        <div class="relative inline-flex items-center gap-2" v-if="element.client_id"
                                            @click.stop>
                                            <button @click="toggleClientIdDropdown(element.client_id)"
                                                class="inline-flex items-center px-2 py-1 text-xs font-medium rounded border-2 border-red-300 bg-white text-red-700 hover:bg-red-50 hover:border-red-500 transition-all">
                                                <Icon name="fa6-solid:file-invoice" class="h-3.5 w-3.5" />
                                            </button>
                                            <div v-if="openClientIdDropdown === element.client_id"
                                                class="absolute z-[50] px-3 py-2 ml-10 bg-slate-900 text-white text-xs rounded-md whitespace-nowrap">
                                                {{ element.client_id }}
                                            </div>
                                        </div>
                                        <span v-else class="text-slate-400 font-medium">-</span>
                                    </td>
                                    <td class="px-3 py-2.5">
                                        <span
                                            class="inline-flex items-center px-2 py-1 rounded-md text-xs font-bold bg-red-500 text-white">
                                            {{ element.motive || "-" }}
                                        </span>
                                    </td>
                                    <td class="px-3 py-2.5 flex items-center justify-center">
                                        <button
                                            class="inline-flex items-center justify-center h-7 w-7 text-xs font-medium rounded-full border-2 border-red-300 bg-white text-red-700 hover:bg-sky-50 hover:border-red-500"
                                            @click="showDetail('AddInvoices', element.holder_iban)">
                                            <Icon name="fa6-solid:eye" class="h-3.5 w-3.5" />
                                        </button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>

            <!-- No Rejections State -->
            <div v-if="rejections && rejections.length === 0 && not_found_rejections && not_found_rejections.length === 0"
                class="text-center py-8">
                <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Icon name="fa6-solid:circle-check" class="text-green-600" />
                </div>
                <h3 class="text-sm font-semibold text-slate-800 mb-1">
                    {{ t("common.no_data_found") }}
                </h3>
                <p class="text-slate-500 text-xs">
                    {{ t("informative_block.info_doc_no_return") }}
                </p>
            </div>

        </div>

        <!-- Loading State -->
        <div v-if="loading_rejections" class="text-center py-8">
            <div class="w-12 h-12 bg-sky-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Icon name="fa6-solid:spinner" class="text-sky-600 animate-spin" />
            </div>
            <h3 class="text-sm font-semibold text-slate-800 mb-1">
                {{ t("common.loading") }}...
            </h3>
        </div>

        <!-- Error State -->
        <div v-if="error_rejections" class="text-center py-8">
            <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Icon name="fa6-solid:exclamation-triangle" class="text-red-600" />
            </div>
            <h3 class="text-sm font-semibold text-red-800 mb-1">
                {{ t("common.error") }}
            </h3>
            <p class="text-red-600 text-xs mb-3">
                {{ t("common.error_load") }}
            </p>
            <button @click="getRejections(sepaFile)"
                class="inline-flex items-center px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors">
                <Icon name="fa6-solid:rotate-right" class="mr-1" />
                {{ t("common.load_again") }}
            </button>
        </div>
    </div>
</template>
