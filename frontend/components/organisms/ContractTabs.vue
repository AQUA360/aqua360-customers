<script setup>

import { ref, computed, onMounted } from 'vue';

import { useRouter } from 'vue-router';

import { useI18n } from 'vue-i18n';

import { useToast } from 'vue-toastification';

import BonificationDetail from '~/components/molecules/BonificationDetail.vue';

import ReadingDetail from '~/components/molecules/ReadingDetail.vue';

import BailDetail from '~/components/molecules/BailDetail.vue';

import VulnerabilityRequestList from '~/components/molecules/VulnerabilityRequestList.vue';

import CommitmentDepositList from '~/components/molecules/CommitmentDepositList.vue';

import ClaimRequestList from '~/components/molecules/ClaimRequestList.vue';

import IncidentList from '~/components/molecules/IncidentList.vue';

import CommunicationMiniDetail from '~/components/molecules/CommunicationMiniDetail.vue';

import OrderMiniDetail from '~/components/molecules/OrderMiniDetail.vue';

import CalendarTaskList from '~/components/molecules/CalendarTaskList.vue';

import VariablesBonificationsChange from '~/components/atoms/VariablesBonificationsChange.vue';

import InvoiceMiniDetail from '~/components/molecules/InvoiceMiniDetail.vue';

import Pagination from '~/components/molecules/Pagination.vue';

import { formatDate } from '~/utils/date';

import { formatMoneyWithCurrency } from '~/utils/money';

import HolderChange from '~/components/atoms/HolderChange.vue';

import TenantChange from '~/components/atoms/TenantChange.vue';

import DataChange from '~/components/atoms/DataChange.vue';

import TimeRelative from '~/components/atoms/TimeRelative.vue';

import FieldDetail from '~/components/atoms/FieldDetail.vue';

const props = defineProps({

    contract: Object,

    isPinned: Boolean,

    isSubRegion: Boolean,

    activeTab: String,

    observationNumber: Number,

    callRegisterNumber: Number,

    // Toggled by the parent after reloading the contract, so lists kept alive by v-show refetch
    reload: Boolean,

    incidentNumber: Number,

    communicationNumber: Number,

    orderNumber: Number,

    bonVarChangesNumber: Number,

    changesNumber: Number,

    contractChangeNumber: Number,

    surrogations: Array,

    tenant_changes: Array,

    data_changes: Array,

    members_change: Array,

    allModifications: {
        type: Array,
        default: () => [],
    },

    contract_logs: {
        type: Array,
        default: () => [],
    },

    expired_variables: Array,

    expired_bonifications: Array,

    invoices: Array,

    invoices_count: Number,

    general_invoices: Array,

    invoicesLoading: {
        type: Boolean,
        default: false,
    },

    invoicesPagination: {
        type: Object,
        default: () => ({
            page: 1,
            perPage: 50,
            total: 0,
            totalPages: 0,
            isFiltered: true
        }),
    },

    person_ids: Array,

    permissions: Object,

    canChange: Boolean,

});

const emit = defineEmits([
    'show-detail',
    'change',
    'update-active-tab',
    'update:observation-count',
    'update:call-register-count',
    'update:incident-count',
    'update:communication-count',
    'update:order-count',
    'update:bonification-variable-change-count',
    'update-invoices-page',
]);

const { t } = useI18n();

const { $ConfigProjectApiService, $InvoiceApiService } = useNuxtApp();

const router = useRouter();

const toast = useToast();

const invoiceActiveTab = ref('invoice_invoices');

const groupedInvoiceMode = ref(false);

const toggleGroupedInvoiceMode = () => {
    groupedInvoiceMode.value = !groupedInvoiceMode.value;
};

const invoiceTypeToken = ref(null);

// Group invoices of the group, one entry per billing run, newest run first.
const generalInvoiceRuns = computed(() => {
    const runs = new Map();
    for (const invoice of props.general_invoices || []) {
        if (invoice.type_final !== invoiceTypeToken.value) continue;
        const key = invoice.billing
            ? `b${invoice.billing}`
            : `p${invoice.billing_period_year}-${invoice.billing_period_month}`;
        if (!runs.has(key)) {
            runs.set(key, {
                key,
                // Any invoice of the run identifies it for the summary PDF.
                invoice_id: invoice.id,
                label: invoice.title_final || invoice.issue_date || invoice.token,
                issue_date: invoice.issue_date,
                total: 0,
                invoices: [],
            });
        }
        const run = runs.get(key);
        run.invoices.push(invoice);
        run.total += Number(invoice.total_final ?? 0);
        if (invoice.issue_date && (!run.issue_date || invoice.issue_date > run.issue_date)) {
            run.issue_date = invoice.issue_date;
        }
    }
    return [...runs.values()].sort((a, b) =>
        (b.issue_date || '').localeCompare(a.issue_date || '')
    );
});

// Runs toggled by the user; until then only the newest run is expanded.
const toggledRuns = ref({});

const isRunExpanded = (run, index) =>
    toggledRuns.value[run.key] ?? index === 0;

const toggleRun = (run, index) => {
    toggledRuns.value[run.key] = !isRunExpanded(run, index);
};

const downloadingSummaryId = ref(null);

const downloadGeneralSummary = async (invoiceId) => {
    downloadingSummaryId.value = invoiceId;
    try {
        await $InvoiceApiService.downloadGeneralSummaryPdf(invoiceId);
    } catch (error) {
        console.error(error);
        toast.error(error.message);
    } finally {
        downloadingSummaryId.value = null;
    }
};

const setInvoiceActiveTab = (tab) => {
    invoiceActiveTab.value = tab;
}

const setActiveTab = (tab) => {
    emit('update-active-tab', tab);
}

/**
 * Contextual tab actions - related contract actions
 * available directly from their corresponding tab
 */

const modifyReadings = () => {
    return router.push(`/contract/contracts/${props.contract.id}/reading-change`);
}

const changeBonifications = () => {
    return router.push(`/contract/contracts/${props.contract.id}/bonifications`);
}

/** El llapis d'una variable porta a la mateixa pantalla que el botó «Modificar
 * variables», però amb el formulari d'aquella variable ja obert. Aquí la fitxa del
 * contracte és només de consulta i no té el panell lateral d'edició. */
const editVariable = (variable) => {
    return router.push(`/contract/contracts/${props.contract.id}/bonifications?variable=${variable.id}`);
}

const changePriceRates = () => {
    return router.push(`/contract/contracts/${props.contract.id}/price-rates`);
}

const dataChangeAction = () => {
    return router.push(`/contract/contracts/${props.contract.id}/data-change`);
}

const surrogate = () => {
    return router.push(`/contract/contracts/${props.contract.id}/surrogate`);
}

const tenantChange = () => {
    return router.push(`/contract/contracts/${props.contract.id}/change-tenant`);
}

const newOrder = () => {
    return navigateTo({
        path: '/order/orders/add',
        query: { contract_id: props.contract.id }
    })
}

const newCommunicationProcess = () => {
    return navigateTo({
        path: '/communication/process-communications/add',
        query: { contract_id: props.contract.id }
    })
}

const newClaimRequest = () => {
    return navigateTo({
        path: '/billing/claim-managements/add',
        query: {
            contract_id: props.contract.id,
            contract_token: props.contract.token
        }
    })
}

const manageGeneralInvoices = () => {

    let gen_id = props.contract.general_invoice?.id ||
        props.contract.general_invoice ||
        '';

    return navigateTo(
        `/contract/contracts/${props.contract.id}/general-invoices/?id=${gen_id}`
    );

}

const allHistoryEntries = computed(() => {

    const modifications = (props.allModifications || [])
        .map(e => ({
            ...e,
            _type: 'datachange'
        }));

    // getLogs ja inclou data_changes transformats:
    // només mostrem logs crus (ContractLog)
    // per no duplicar "Método de pago" / payment_type.

    // També amaguem el log tècnic `payment`
    // (FK GeneralPayment) si ja hi ha un datachange
    // de mètode de pagament o IBAN al mateix guardat.

    const modificationTimes = modifications
        .filter((m) =>
            m.new_payment_type != null ||
            m.previous_payment_type != null ||
            m.new_payment != null ||
            m.previous_payment != null
        )
        .map((m) =>
            new Date(m.created_at || m.approved_at).getTime()
        );

    const logs = (props.contract_logs || [])
        .filter((e) => e.source !== 'data_change')
        .filter((e) => {

            if (e.field_name !== 'payment') return true;

            const logTime = new Date(e.created_at).getTime();

            return !modificationTimes.some(
                (t) => Math.abs(t - logTime) <= 5000
            );

        })
        .map(e => ({
            ...e,
            _type: 'log'
        }));

    return [
        ...modifications,
        ...logs
    ].sort(
        (a, b) =>
            new Date(b.created_at) -
            new Date(a.created_at)
    );

});

const showDetail = (component, id) => {
    emit('show-detail', component, id);
}

const handleChange = () => {
    emit('change');
}

const updateObservationCount = (num) =>
    emit('update:observation-count', num);

const updateCallRegisterCount = (num) =>
    emit('update:call-register-count', num);

const updateIncidentCount = (num) =>
    emit('update:incident-count', num);

const updateCommunicationCount = (num) =>
    emit('update:communication-count', num);

const updateOrderCount = (num) =>
    emit('update:order-count', num);

const updateBonificationVariableChangeCount = (num) =>
    emit('update:bonification-variable-change-count', num);

const onInvoicesPageChange = (newPage) =>
    emit('update-invoices-page', newPage);

onMounted(async () => {

    try {

        invoiceTypeToken.value =
            await $ConfigProjectApiService.get('invoice_type_invoice_token');

    } catch (e) {

        console.error(e);

    }

});

const groupedPriceRates = computed(() => {

    if (
        !props.contract ||
        !props.contract.show_price_rates
    ) {
        return {};
    }

    return props.contract.show_price_rates.reduce(
        (acc, rate) => {

            let spToken = 'N/A';

            if (
                rate.supply_point &&
                rate.supply_point.token
            ) {
                spToken = rate.supply_point.token;

            } else if (
                rate.product &&
                rate.product.supply_point &&
                rate.product.supply_point.token
            ) {
                spToken =
                    rate.product.supply_point.token;

            } else if (
                rate.supply_point_token
            ) {
                spToken =
                    rate.supply_point_token;

            } else if (
                props.contract &&
                props.contract.supply_point &&
                props.contract.supply_point.token
            ) {
                spToken =
                    props.contract.supply_point.token;

            } else if (
                props.contract &&
                props.contract.supply_point_default &&
                props.contract.supply_point_default.token
            ) {
                spToken =
                    props.contract.supply_point_default.token;

            } else {

                spToken =
                    t('common.unknown') ||
                    'Sense punt de subministrament';

            }

            if (!acc[spToken]) {
                acc[spToken] = [];
            }

            acc[spToken].push(rate);

            return acc;

        },
        {}
    );

});

</script>

<template>

    <AtomsTabs>

        <li class="me-2">

            <a
                href="#tab_observations"
                @click.prevent="setActiveTab('observations')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'observations',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations'
                }"
            >

                <Icon
                    name="fa6-solid:note-sticky"
                    class="display-inline mr-2"
                />

                {{ $t("common.observations") }}
                ({{ observationNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_call_register"
                @click.prevent="setActiveTab('call_register')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'call_register',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'call_register'
                }"
            >

                <Icon
                    name="fa6-solid:phone"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.call_register") }}
                ({{ callRegisterNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_incident"
                @click.prevent="setActiveTab('incident')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'incident',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'incident'
                }"
            >

                <Icon
                    name="fa6-solid:bug"
                    class="display-inline mr-2"
                />

                {{ $t("common.incidents") }}
                ({{ incidentNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_documents"
                @click.prevent="setActiveTab('documents')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'documents',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'documents'
                }"
            >

                <Icon
                    name="fa6-solid:file"
                    class="display-inline mr-2"
                />

                {{ $t("common.docs") }}
                (
                {{
                    (contract.contract_file &&
                    contract.contract_file.is_active !== false
                        ? 1
                        : 0) +
                    (
                        contract?.documentation_files
                            ?.filter(d => d.is_active !== false)
                            ?.length || 0
                    )
                }}
                )

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_communication"
                @click.prevent="setActiveTab('communication')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'communication',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'communication'
                }"
            >

                <Icon
                    name="fa6-solid:envelope"
                    class="display-inline mr-2"
                />

                {{ $t("common.comms") }}
                ({{ communicationNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_tasks"
                @click.prevent="setActiveTab('tasks')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'tasks',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'tasks'
                }"
            >

                <Icon
                    name="fa6-solid:calendar"
                    class="display-inline mr-2"
                />

                {{ $t("dashboard.tasks") }}
                ({{ contract.calendar_tasks?.length || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_billing_reading"
                @click.prevent="setActiveTab('billing_reading')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'billing_reading',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'billing_reading'
                }"
            >

                <Icon
                    name="fa6-solid:list"
                    class="display-inline mr-2"
                />

                {{ $t("readings") }}

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_invoices"
                @click.prevent="setActiveTab('invoices')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'invoices',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'invoices'
                }"
            >

                <Icon
                    name="fa6-solid:file-invoice"
                    class="display-inline mr-2"
                />

                {{ $t("invoices") }}
                ({{ invoices_count || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_bonifications"
                @click.prevent="setActiveTab('bonifications')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'bonifications',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'bonifications'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa6-solid:percent"
                    class="display-inline mr-2"
                />

                {{ $t("bonifications") }}
                ({{ contract.bonifications?.length || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_variables"
                @click.prevent="setActiveTab('variables')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'variables',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'variables'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa6-solid:shuffle"
                    class="display-inline mr-2"
                />

                {{ $t("variables") }}
                ({{ contract.variables?.length || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_price_rate"
                @click.prevent="setActiveTab('price_rate')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'price_rate',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'price_rate'
                }"
            >

                <Icon
                    name="fa6-solid:tag"
                    class="display-inline mr-2"
                />

                {{ $t("price_rate") }}
                ({{ contract?.price_rates?.length || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_bails"
                @click.prevent="setActiveTab('bails')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'bails',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'bails'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa6-solid:users"
                    class="display-inline mr-2"
                />

                {{ $t("common.bails") }}
                ({{ contract?.bails ? contract.bails.length : 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_debt_mng"
                @click.prevent="setActiveTab('debt_mng')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'debt_mng',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'debt_mng'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa-solid:exclamation-circle"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.debt_management") }}

            </a>

        </li>

        <li
            v-if="isPinned && contract?.supply_points?.length > 0"
            class="me-2"
        >

            <a
                href="#tab_supply_point"
                @click.prevent="setActiveTab('supply_point')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'supply_point',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_point'
                }"
            >

                <Icon
                    name="fa6-solid:street-view"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.additional_supply_points") }}
                ({{ contract?.supply_points?.length - 1 || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_orders"
                @click.prevent="setActiveTab('orders')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'orders',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders'
                }"
            >

                <Icon
                    name="fa6-solid:screwdriver-wrench"
                    class="display-inline mr-2"
                />

                {{ $t("work_orders") }}
                ({{ orderNumber || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_dataChange"
                @click.prevent="setActiveTab('dataChange')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'dataChange',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'dataChange'
                }"
            >

                <Icon
                    name="fa6-solid:address-card"
                    class="display-inline mr-2"
                />

                {{ $t("common.modifications") }}
                ({{ contractChangeNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_surrogation"
                @click.prevent="setActiveTab('surrogation')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'surrogation',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'surrogation'
                }"
            >

                <Icon
                    name="fa6-solid:person-walking-arrow-right"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.surrogations") }}
                ({{ surrogations?.length || 0 }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_tenantChange"
                @click.prevent="setActiveTab('tenantChanges')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'tenantChanges',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'tenantChanges'
                }"
            >

                <Icon
                    name="fa6-solid:people-arrows"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.tenant_changes") }}
                ({{ tenant_changes?.length || 0 }})

            </a>

        </li>

        <li
            v-if="contract?.contract_request_type?.has_persons"
            class="me-2"
        >

            <a
                href="#tab_change_var"
                @click.prevent="setActiveTab('change_var')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'change_var',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'change_var'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa6-solid:users"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.bon_var_changes") }}
                ({{ bonVarChangesNumber }})

            </a>

        </li>

        <li class="me-2">

            <a
                href="#tab_clauses"
                @click.prevent="setActiveTab('clauses')"
                :class="{
                    'text-sky-600 border-sky-600': activeTab === 'clauses',
                    'hover:text-gray-600 hover:border-gray-300': activeTab !== 'clauses'
                }"
                aria-current="page"
            >

                <Icon
                    name="fa6-solid:file-signature"
                    class="display-inline mr-2"
                />

                {{ $t("contract_block.clauses") }}
                ({{ contract.clauses?.length || 0 }})

            </a>

        </li>

    </AtomsTabs>

    <div
        id="contract_tabpanels"
        class="overflow-y-auto scrollbar-hide pb-20"
    >

        <section
            v-show="activeTab === 'observations'"
            role="tabpanel"
            id="tab_observations"
            class="bg-white antialiased"
        >

            <MoleculesObservationList
                v-if="contract"
                @update:observation-count="updateObservationCount"
                parent_entity="contract"
                url_entity="contract"
                :id="contract.id"
                module="contract"
                :allow_mark="true"
                @update:important-observations="handleChange"
            />

        </section>

        <section
            v-show="activeTab === 'call_register'"
            role="tabpanel"
            id="tab_call_register"
            class="bg-white antialiased"
        >

            <div class="h-content max-h-[40vh] overflow-y-auto mb-10">

                <MoleculesCallRegisterList
                    v-if="contract"
                    @update:count="updateCallRegisterCount"
                    :contract_id="contract.id"
                    :reload="reload"
                />

            </div>

        </section>

        <section
            v-show="activeTab === 'incident'"
            role="tabpanel"
            id="tab_incident"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="showDetail('IncidentEdit', contract.id)"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:bug" />

                    <span class="ml-1">
                        {{ t('customer_service_block.new_incident') }}
                    </span>

                </button>

            </div>

            <div class="mb-10">

                <IncidentList
                    v-if="contract"
                    :contract_id="contract.id"
                    @show-detail="showDetail"
                    :isSubRegion="isSubRegion"
                />

            </div>

        </section>

        <section
            v-show="activeTab === 'communication'"
            role="tabpanel"
            id="tab_communication"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="newCommunicationProcess"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:envelopes-bulk" />

                    <span class="ml-1">
                        {{ t('customer_service_block.new_comms_process') }}
                    </span>

                </button>

            </div>

            <div class="h-content max-h-[40vh] overflow-y-auto mb-10">

                <CommunicationMiniDetail
                    :person_ids="person_ids"
                    @update:count="updateCommunicationCount"
                    @show-detail="showDetail"
                    :contract_id="contract.id"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'price_rate'"
            role="tabpanel"
            id="tab_price_rate"
            class="bg-white antialiased py-2 mb-10"
        >

            <div class="flex items-center justify-between mt-2 mb-4 gap-2 flex-wrap">

                <p class="text-sm text-slate-600">

                    {{ $t('contract_block.bop_tariff') }}:

                    <span class="font-semibold text-slate-900">

                        {{
                            contract?.tarifa_bop ||
                            $t('contract_block.bop_tariff_no_date')
                        }}

                    </span>

                </p>

                <button
                    v-if="canChange"
                    @click="changePriceRates"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:tag" />

                    <span class="ml-1">
                        {{ t('common.modify') }}
                        {{ t('common.price_rates') }}
                    </span>

                </button>

            </div>

            <div
                v-for="(rates, spToken) in groupedPriceRates"
                :key="spToken"
                class="mb-4"
            >

                <details
                    class="bg-slate-50 border rounded-md"
                    open
                >

                    <summary
                        class="font-semibold text-slate-700 p-2 cursor-pointer hover:bg-slate-100"
                    >

                        <Icon
                            name="fa6-solid:location-dot"
                            class="mr-2 text-slate-500"
                        />

                        {{
                            spToken !== 'N/A' &&
                            spToken !== t('common.unknown')
                                ? t('supply_point') + ': ' + spToken
                                : spToken
                        }}

                    </summary>

                    <div class="p-2 bg-white">

                        <div
                            v-for="rate in rates"
                            :key="rate.id"
                            class="mb-2"
                        >

                            <span
                                v-if="rate.is_bop_reference"
                                class="inline-flex items-center gap-1 mb-1 px-2 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-300"
                            >

                                <Icon name="fa6-solid:circle-check" />

                                {{ $t('contract_block.bop_tariff_reference') }}

                            </span>

                            <MoleculesPriceRateListItem
                                :isContractSubregion="true"
                                :price_rate="rate.price_rate"
                                :variables="contract.variables"
                                :contract="contract.id"
                                @show-detail="showDetail"
                                :isSubRegion="isSubRegion"
                            />

                        </div>

                    </div>

                </details>

            </div>

        </section>

        <section
            v-if="activeTab === 'billing_reading'"
            role="tabpanel"
            id="tab_billing_reading"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    :disabled="
                        !contract?.supply_point_default ||
                        !contract?.supply_point_default?.meter_code
                    "
                    @click="modifyReadings"
                    class="button-primary !px-2.5 !py-1 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                >

                    <Icon name="fa6-solid:droplet" />

                    <span class="ml-1">
                        {{ t('common.modify') }}
                        {{ t('readings') }}
                    </span>

                </button>

            </div>

            <div class="h-[40vh] overflow-y-auto mb-10">

                <ReadingDetail
                    :contract_ids="[contract.id]"
                    :isSubRegion="isSubRegion"
                    @show-detail="showDetail"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'tasks'"
            role="tabpanel"
            id="tab_tasks"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="showDetail('CalendarTaskEdit', null)"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:calendar" />

                    <span class="ml-1">
                        {{ t('common.add') }}
                        {{ t('dashboard.task') }}
                    </span>

                </button>

            </div>

            <CalendarTaskList
                :id="null"
                :data="contract.calendar_tasks"
                :isSubRegion="isSubRegion"
                @show-detail="showDetail"
                @refresh="handleChange"
            />

        </section>

        <!-- ========================================================= -->
        <!-- FACTURES -->
        <!-- ========================================================= -->

        <section
            v-if="activeTab === 'invoices'"
            role="tabpanel"
            id="tab_invoices"
            class="bg-white antialiased"
        >

        <div v-if="canChange" class="flex justify-end flex-wrap mt-2 mb-4 gap-2">
            <button
              type="button"
              @click="toggleGroupedInvoiceMode"
              class="button-primary !px-2.5 !py-1 text-xs flex items-center justify-center"
            >
              <Icon
                :name="groupedInvoiceMode ? 'fa6-solid:xmark' : 'reicon:envelopes-filled'"
                class="text-white"
              />
              <span class="ml-1">
                {{
                  groupedInvoiceMode
                    ? t('contract_block.cancel_grouped_sends')
                    : t('contract_block.grouped_sends')
                }}
              </span>
            </button>
      
          <button
            @click="manageGeneralInvoices"
            class="button-primary !px-2.5 !py-1 text-xs"
          >
            <Icon name="fa6-solid:layer-group" />
            <span class="ml-1">{{ t('contract_block.general_invoices') }}</span>
          </button>
      
          <button
            @click="showDetail('MassiveInvoiceDownload', null)"
            class="button-primary !px-2.5 !py-1 text-xs"
          >
            <Icon name="fa6-solid:download" />
            <span class="ml-1">{{ t('common.massive_invoice_download') }}</span>
          </button>
      
          <button
            @click="showDetail('AddInvoiceBudget', null)"
            class="button-primary !px-2.5 !py-1 text-xs"
          >
            <Icon name="fa6-solid:coins" />
            <span class="ml-1">
              {{ t('common.add') }} {{ t('billing_block.custom_invoice') }}
            </span>
          </button>
        </div>

            <div
                v-if="invoicesLoading"
                class="flex justify-center items-center mt-5 mb-10"
            >

                <Icon
                    name="fa6-solid:spinner"
                    class="animate-spin text-2xl text-slate-500"
                />

                <span class="ml-2">
                    {{ $t('common.loading') }}...
                </span>

            </div>

            <template v-else>

                <AtomsTabs v-if="contract.general_invoice">

                    <li class="me-2">

                        <a
                            href="#tab_invoice_invoices"
                            @click.prevent="
                                setInvoiceActiveTab('invoice_invoices')
                            "
                            :class="{
                                'text-sky-600 border-sky-600':
                                    invoiceActiveTab === 'invoice_invoices',
                                'hover:text-gray-600 hover:border-gray-300':
                                    invoiceActiveTab !== 'invoice_invoices'
                            }"
                        >

                            {{ $t("invoices") }}
                            ({{ invoices_count }})

                        </a>

                    </li>

                    <li class="me-2">

                        <a
                            href="#tab_invoice_generals"
                            @click.prevent="
                                setInvoiceActiveTab('invoice_generals')
                            "
                            :class="{
                                'text-sky-600 border-sky-600':
                                    invoiceActiveTab === 'invoice_generals',
                                'hover:text-gray-600 hover:border-gray-300':
                                    invoiceActiveTab !== 'invoice_generals'
                            }"
                        >

                            {{ $t("billing_block.general_invoices") }}

                            (
                            {{
                                general_invoices
                                    ? general_invoices.filter(
                                        invoice =>
                                            invoice.type_final === invoiceTypeToken
                                    ).length
                                    : 0
                            }}
                            )

                        </a>

                    </li>

                </AtomsTabs>

                <section
                    v-if="invoiceActiveTab === 'invoice_invoices'"
                    class="mb-10 mt-2"
                >

                <InvoiceMiniDetail
                  :item="invoices"
                  :contract="contract"
                  @show-detail="showDetail"
                  :isSubRegion="isSubRegion"
                  :autoCols="true"
                  :exportable="true"
                  :export-file-name="`factures_${contract?.token || contract?.id || ''}`"
                  :grouped-invoice-mode="groupedInvoiceMode"
                />

                    <div
                        class="border-t border-gray-100 p-2"
                        v-if="invoicesPagination.totalPages > 1"
                    >

                        <Pagination
                            :pagination="invoicesPagination"
                            @update:page="onInvoicesPageChange"
                        />

                    </div>

                </section>

                <section
                    v-if="invoiceActiveTab === 'invoice_generals'"
                    class="mb-10 mt-2"
                >

                    <div
                        v-for="(run, index) in generalInvoiceRuns"
                        :key="run.key"
                        class="mb-3 border border-slate-200 rounded"
                    >

                        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 bg-slate-50">

                            <button
                                type="button"
                                @click="toggleRun(run, index)"
                                class="flex flex-1 min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-left text-sm"
                            >
                                <Icon
                                    name="fa6-solid:angle-down"
                                    class="text-slate-500 transition-transform duration-200"
                                    :class="{ '-rotate-90': !isRunExpanded(run, index) }"
                                />
                                <span class="font-semibold text-slate-900">{{ run.label }}</span>
                                <span v-if="run.issue_date" class="text-slate-500">{{ formatDate(run.issue_date) }}</span>
                                <span class="text-slate-500">{{ run.invoices.length }} {{ $t('invoices').toLowerCase() }}</span>
                                <span class="font-semibold text-slate-700">{{ formatMoneyWithCurrency(run.total) }}</span>
                            </button>

                            <button
                                type="button"
                                @click="downloadGeneralSummary(run.invoice_id)"
                                :disabled="downloadingSummaryId === run.invoice_id"
                                class="button-default-xs flex items-center gap-1"
                            >
                                <Icon
                                    :name="downloadingSummaryId === run.invoice_id ? 'fa6-solid:spinner' : 'fa6-solid:file-pdf'"
                                    :class="{ 'animate-spin': downloadingSummaryId === run.invoice_id }"
                                />
                                <span>{{ $t('billing_block.general_invoices_summary_pdf') }}</span>
                            </button>

                        </div>

                        <div v-if="isRunExpanded(run, index)" class="px-2 pb-2">
                            <InvoiceMiniDetail
                                :item="run.invoices"
                                :contract="contract"
                                @show-detail="showDetail"
                                :isSubRegion="isSubRegion"
                                :exportable="true"
                                :export-file-name="`factures_generals_${contract?.token || contract?.id || ''}_${run.issue_date || run.key}`"
                            />
                        </div>

                    </div>

                    <div
                        v-if="!generalInvoiceRuns.length"
                        class="footering text-slate-500 p-2"
                    >
                        {{ $t('common.no_records') }}
                    </div>

                </section>

            </template>

        </section>

        <section
            v-show="activeTab === 'orders'"
            role="tabpanel"
            id="tab_orders"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="newOrder"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:clipboard-list" />

                    <span class="ml-1">
                        {{ t('order_block.new_order') }}
                    </span>

                </button>

            </div>

            <div class="h-content max-h-[40vh] overflow-y-auto mb-10">

                <OrderMiniDetail
                    :contract_id="contract.id"
                    :supply_point_ids="
                        contract?.supply_points?.map(sp => sp.id) || []
                    "
                    @update:count="updateOrderCount"
                    @show-detail="showDetail"
                    :isSubRegion="isSubRegion"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'bonifications'"
            role="tabpanel"
            id="tab_bonifications"
            class="bg-white antialiased py-3 mb-10"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="changeBonifications"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:percent" />

                    <span class="ml-1">
                        {{ t('common.modify') }}
                        {{ t('bonifications') }}
                    </span>

                </button>

            </div>

            <div
                v-if="
                    contract?.bonifications?.length == 0 &&
                    (!expired_bonifications ||
                    expired_bonifications?.length == 0)
                "
                class="footering text-slate-500 p-2"
            >

                {{ t('common.no_records') }}

            </div>

            <div
                v-for="bonification in contract.bonifications"
                :key="bonification.id"
                class="mb-3 bg-sky-50 rounded"
            >

                <BonificationDetail
                    :item="bonification"
                    :deleteButton="false"
                />

            </div>

            <hr
                v-if="expired_bonifications?.length > 0"
                class="mt-20 opacity-0"
            />

            <span
                v-if="expired_variables?.length > 0"
                class="text-slate-500 text-sm bg-slate-100 rounded-md px-2 py-1"
            >

                {{ t('contract_block.expired_bonifications') }}

            </span>

            <div
                v-for="b in expired_bonifications"
                :key="b.id"
                class="my-3 bg-slate-100 rounded"
            >

                <BonificationDetail
                    :item="b.expired_bonification"
                    :deleteButton="false"
                    :is_expired="true"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'bails'"
            role="tabpanel"
            id="tab_bails"
            class="bg-white antialiased"
        >

            <div
                v-if="contract?.bails?.length > 0"
                class="mt-3 h-[40vh] overflow-y-auto mb-10 rounded"
            >

                <div
                    v-for="b in contract.bails"
                    :key="b.id"
                    class="mb-3 bg-slate-100 rounded px-2"
                >

                    <BailDetail
                        :id="b.id"
                        :data="null"
                        :isSubRegion="isSubRegion"
                        :hideContract="true"
                        @show-detail="showDetail"
                    />

                </div>

            </div>

        </section>

        <section
            v-if="activeTab === 'dataChange'"
            role="tabpanel"
            id="tab_dataChange"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="dataChangeAction"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:address-card" />

                    <span class="ml-1">
                        {{ t('common.modify') }}
                    </span>

                </button>

            </div>

            <div>

                <div v-if="!allHistoryEntries?.length">

                    <div class="footering text-slate-500 p-2">

                        {{ t('common.no_changes') }}

                    </div>

                </div>

                <template
                    v-for="entry in allHistoryEntries"
                    :key="`${entry._type}-${entry.id}`"
                >

                    <DataChange
                        v-if="entry._type === 'datachange'"
                        :object="entry"
                    />

                    <article
                        v-else
                        class="relative p-2 text-base bg-white group hover:bg-slate-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-slate-400"
                    >

                        <span
                            class="absolute left-[-5px] top-0 text-[10px]"
                        >

                            <Icon
                                name="fa6-solid:circle"
                                class="text-slate-400"
                            />

                        </span>

                        <footer class="flex justify-between items-center pt-1">

                            <div class="flex items-center mb-1 gap-3">

                                <p class="text-sm text-gray-700">
                                    {{
                                        entry.user?.username ||
                                        t('common.admin')
                                    }}
                                </p>

                                <p class="inline-flex items-center text-sm text-gray-900 font-semibold">

                                    <TimeRelative
                                        :datetime="entry.created_at"
                                    />

                                </p>

                            </div>

                            <span class="text-xs text-slate-400 uppercase tracking-wide">
                                {{ entry.operation_token }}
                            </span>

                        </footer>

                        <p class="text-sm flex items-center gap-2 mt-1">

                            <span class="font-medium text-slate-600">
                                {{ entry.field_name }}
                            </span>

                            <span class="text-slate-400">
                                {{
                                    entry.old_value ||
                                    t('common.no_value')
                                }}
                            </span>

                            <Icon
                                name="fa6-solid:arrow-right"
                                class="text-slate-400 text-xs"
                            />

                            <span class="text-slate-900 font-medium">
                                {{
                                    entry.new_value ||
                                    t('common.no_value')
                                }}
                            </span>

                        </p>

                    </article>

                </template>

            </div>

        </section>

        <section
            v-if="activeTab === 'surrogation'"
            role="tabpanel"
            id="tab_surrogation"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="surrogate"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:person-walking-arrow-right" />

                    <span class="ml-1">
                        {{ t('contract_block.new_surrogation') }}
                    </span>

                </button>

            </div>

            <div>

                <div v-if="surrogations?.length == 0">

                    <div class="footering text-slate-500 p-2">

                        {{ t('common.no_records') }}

                    </div>

                </div>

                <HolderChange
                    v-for="s in surrogations"
                    :key="s.id"
                    :object="s"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'tenantChanges'"
            role="tabpanel"
            id="tab_tenantChanges"
            class="bg-white antialiased"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="tenantChange"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:people-arrows" />

                    <span class="ml-1">
                        {{ t('contract_block.tenant_changes') }}
                    </span>

                </button>

            </div>

            <div>

                <div v-if="tenant_changes?.length == 0">

                    <div class="footering text-slate-500 p-2">

                        {{ t('common.no_records') }}

                    </div>

                </div>

                <TenantChange
                    v-for="tc in tenant_changes"
                    :key="tc.id"
                    :object="tc"
                />

            </div>

        </section>

        <section
            v-if="activeTab === 'clauses'"
            role="tabpanel"
            id="tab_clauses"
            class="bg-white antialiased py-3"
        >

            <div
                v-if="canChange"
                class="flex justify-end mx-4 mb-2"
            >

                <button
                    @click="emit('show-detail', 'ContractClausesEdit', contract.id)"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon
                        name="fa6-solid:paragraph"
                        class="mr-1"
                    />

                    {{ t('common.modify') }} {{ t('contract_block.clauses') }}

                </button>

            </div>

            <div
                v-if="contract.clauses && contract.clauses.length > 0"
                class="m-4"
            >

                <div
                    v-for="c in contract.clauses"
                    :key="c.id"
                    class="border rounded p-2 bg-slate-100 mb-2"
                >

                    <MoleculesClauseDetail
                        :item="c"
                    />

                </div>

            </div>

            <div v-else>

                <div class="footering text-slate-500 p-2">

                    {{ t('common.no_records') }}

                </div>

            </div>

        </section>

        <section
            v-if="activeTab === 'variables'"
            role="tabpanel"
            id="tab_variables"
            class="bg-white antialiased mb-10"
        >

            <div
                v-if="canChange"
                class="flex justify-end mt-2 mb-4"
            >

                <button
                    @click="changeBonifications"
                    class="button-primary !px-2.5 !py-1 text-xs"
                >

                    <Icon name="fa6-solid:shuffle" />

                    <span class="ml-1">
                        {{ t('common.modify') }}
                        {{ t('variables') }}
                    </span>

                </button>

            </div>

            <div
                v-if="
                    contract.variables?.length == 0 &&
                    expired_variables?.length == 0
                "
            >

                <div class="footering text-slate-500 p-2 my-3">

                    {{ t('common.no_records') }}

                </div>

            </div>

            <div class="py-3">

                <div class="grid grid-cols-2 gap-3">

                    <div
                        v-for="v in contract.variables"
                        :key="v.id"
                        class="border rounded p-2 bg-sky-50"
                    >

                        <MoleculesVariableDetail
                            :item="v"
                            :deleteButton="false"
                            :editButton="canChange"
                            @edit="editVariable(v)"
                        />

                    </div>

                </div>

                <hr
                    v-if="expired_variables?.length > 0"
                    class="mt-20 opacity-0"
                />

                <span
                    v-if="expired_variables?.length > 0"
                    class="text-slate-500 text-sm bg-slate-100 rounded-md px-2 py-1"
                >

                    {{ t('contract_block.expired_variables') }}

                </span>

                <div
                    v-if="expired_variables?.length > 0"
                    class="grid grid-cols-2 gap-3 mt-2"
                >

                    <div
                        v-for="v in expired_variables"
                        :key="v.id"
                        class="border rounded p-2 bg-slate-100"
                    >

                        <MoleculesVariableDetail
                            :item="v.expired_variable"
                            :deleteButton="false"
                            :editButton="false"
                            :is_expired="true"
                        />

                    </div>

                </div>

            </div>

        </section>

        <section
            v-if="activeTab === 'documents'"
            role="tabpanel"
            id="tab_documents"
            class="bg-white antialiased py-3"
        >

            <MoleculesContractDocumentsData
                :contract="contract"
                @update-item="handleChange"
            />

        </section>

        <section
            v-if="activeTab === 'debt_mng'"
            role="tabpanel"
            id="tab_debt_mng"
            class="bg-white antialiased py-3 mb-10"
        >

            <div class="mb-5">

                <span class="text-slate-500 font-bold my-2">
                    {{ t('common.vulnerable_reqs') }}
                </span>

                <div class="my-2">

                    <VulnerabilityRequestList
                        :contract_id="contract.id"
                        @show-detail="showDetail"
                    />

                </div>

            </div>

            <div class="mb-5">

                <span class="text-slate-500 font-bold my-2">
                    {{ t('claim_block.pay_commitments') }}
                </span>

                <div class="my-2">

                    <CommitmentDepositList
                        :contract_id="contract.id"
                        @show-detail="showDetail"
                    />

                </div>

            </div>

            <div class="mb-5">

                <div class="flex items-center justify-between my-2">

                    <span class="text-slate-500 font-bold">
                        {{ t('claim_block.claims_payments') }}
                    </span>

                    <button
                        v-if="canChange"
                        @click="newClaimRequest"
                        class="button-primary !px-2.5 !py-1 text-xs"
                    >

                        <Icon name="fa-solid:exclamation-circle" />

                        <span class="ml-1">
                            {{ t('claim_block.new_claim_request') }}
                        </span>

                    </button>

                </div>

                <div class="my-2">

                    <ClaimRequestList
                        :contract_id="contract.id"
                        :isSubRegion="isSubRegion"
                        @show-detail="showDetail"
                    />

                </div>

            </div>

        </section>

        <section
            v-if="isPinned && activeTab === 'supply_point'"
            role="tabpanel"
            id="tab_supply_point"
            class="bg-white antialiased"
        >

            <div class="mt-3 grid grid-cols-3 gap-2">

                <div
                    v-for="supply_point in contract?.supply_points?.filter(
                        sp => sp.id != contract?.supply_point_default?.id
                    )"
                    :key="supply_point.id"
                >

                    <div class="p-1 rounded border border-slate-300 bg-sky-50">

                        <FieldDetail
                            :label="`${$t('common.identification')} ${$t('common.short_supply')}`"
                        >

                            <button
                                v-if="supply_point"
                                @click="
                                    showDetail(
                                        'SupplyPointRegion',
                                        supply_point?.id
                                    )
                                "
                                class="text-start text-sky-500 hover:no-underline underline hover:text-sky-600"
                            >

                                {{ supply_point?.token }}

                            </button>

                        </FieldDetail>

                        <FieldDetail
                            :label="$t('address_block.address')"
                            :value="supply_point.address_complete"
                        />

                        <FieldDetail
                            :label="$t('service_block.short_supply_type')"
                            :value="supply_point?.source?.name"
                        />

                        <FieldDetail
                            :label="$t('service_block.short_type')"
                            :value="supply_point?.supply_type?.name"
                        />

                        <FieldDetail
                            :label="$t('service_block.is_potable')"
                            :value="
                                supply_point?.is_potable
                                    ? $t('common.yes')
                                    : $t('common.no')
                            "
                        />

                        <FieldDetail :label="$t('meter')">

                            <button
                                v-if="supply_point?.meter"
                                @click="
                                    showDetail(
                                        'MeterRegion',
                                        supply_point?.meter.id
                                    )
                                "
                                class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline"
                            >

                                {{ supply_point?.meter.code }}

                            </button>

                            <span v-else>-</span>

                        </FieldDetail>

                    </div>

                </div>

            </div>

            <div
                v-if="contract?.supply_points?.length <= 1"
            >

                <div class="footering text-slate-500 p-2">

                    {{ t('contract_block.no_additional_supply_points') }}

                </div>

            </div>

        </section>

        <section
            v-if="
                contract?.contract_request_type?.has_persons &&
                activeTab === 'change_var'
            "
            role="tabpanel"
            id="tab_change_var"
            class="bg-white antialiased py-3"
        >

            <VariablesBonificationsChange
                :id="contract.id"
                :object="contract"
                @update:count="updateBonificationVariableChangeCount"
            />

        </section>

    </div>

</template>