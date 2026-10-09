<script setup>
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const props = defineProps({
    contract: Object,
    canChange: Boolean,
    terminatedStatusToken: String,
    personIds: Array,
});

const emit = defineEmits(['show-detail', 'change', 'delete-click']);

const router = useRouter();
const { t } = useI18n();
const toast = useToast();
const { $ContractApiService, $VulnerabilityRequestApiService } = useNuxtApp();

const dataChange = () => {
    return router.push(`/contract/contracts/${props.contract.id}/data-change`);
}

const surrogate = () => {
    return router.push(`/contract/contracts/${props.contract.id}/surrogate`);
}

const tenantChange = () => {
    return router.push(`/contract/contracts/${props.contract.id}/change-tenant`);
}

const changeName = () => {
    return navigateTo({
        path: '/contract/contract-requests/add',
        query: {
            contract_id: props.contract.id
        }
    })
}

const terminate = () => {
    return router.push(`/contract/contract-terminations/add?contract=${props.contract.id}`);
}

const changeBonifications = () => {
    return router.push(`/contract/contracts/${props.contract.id}/bonifications`);
}

const changePriceRates = () => {
    return router.push(`/contract/contracts/${props.contract.id}/price-rates`);
}

const manageGeneralInvoices = () => {
    let gen_id = props.contract.general_invoice?.id || props.contract.general_invoice || '';
    return navigateTo(`/contract/contracts/${props.contract.id}/general-invoices/?id=${gen_id}`);
}

const newCommunicationProcess = () => {
    return navigateTo({
        path: '/communication/process-communications/add',
        query: {
            contract_id: props.contract.id,
        }
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

const hasDebt = computed(() => Number(props.contract?.debt_amount) > 0);

const newCommitmentDeposit = () => {
    return navigateTo({
        path: '/billing/commitment-deposits/add',
        query: {
            contract_id: props.contract.id,
        }
    })
}

const cutSupplyPoint = () => {
    return navigateTo({
        path: '/service/supply-cut/add',
        query: {
            action: 'CONTRACT',
            contract: props.contract.id
        }
    })
}

const newOrder = () => {
    return navigateTo({
        path: '/order/orders/add',
        query: {
            contract_id: props.contract.id
        }
    })
}

const modifyReadings = () => {
    return router.push(`/contract/contracts/${props.contract.id}/reading-change`);
}

const toggleBillable = async () => {
    const txt = props.contract.block_billing ? t('contract_block.mark_as_billable') : t('contract_block.mark_as_unbillable')

    if (confirm(t('confirmation_text_block.confirm_base') + ' ' + txt.toLowerCase() + '?')) {
        const res = await $ContractApiService.toggleBillable(props.contract.id);
        props.contract.block_billing = res.block_billing;
        emit('change');
    }
}

const requestVulnerability = async () => {
    if (confirm(t('confirmation_text_block.confirm_create_vulnerability_request'))) {
        let save_data = {
            contract_id: props.contract.id,
        }
        try {
            let response = await $VulnerabilityRequestApiService.save(save_data);
            if (response) {
                toast.success(t('informative_block.info_vulnerability_request_created'))
                emit('change');
            }
        } catch (error) {
            console.error(error)
        }
    }
}

const generateContract = async () => {
    const response = await $ContractApiService.getDocument(props.contract.id, true);
    await openAuthenticatedFileUrl(response.pdf_url);
}

const showDetail = (component, id) => {
    emit('show-detail', component, id);
}

const deleteContract = () => {
    emit('delete-click');
}
</script>

<template>
    <OptionsDropdown v-if="canChange" id="ContractPinnedRegionOptions">
        <DropdownOption :name="t('common.modify')" @click="dataChange">
            <Icon name="fa6-solid:address-card" class="display-inline mr-2" /> {{ t('common.modify') }}
        </DropdownOption>
        <DropdownOption :name="t('contract_block.new_surrogation')" @click="surrogate">
            <Icon name="fa6-solid:person-walking-arrow-right" class="display-inline mr-2" />
            {{ t('contract_block.new_surrogation') }}
        </DropdownOption>
        <DropdownOption :name="t('contract_block.tenant_changes')" @click="tenantChange">
            <Icon name="fa6-solid:people-arrows" class="display-inline mr-2" /> {{
                t('contract_block.tenant_changes') }}
        </DropdownOption>
        <DropdownOption :disabled="!contract?.supply_point_default" :name="t('contract_block.change_of_name')" @click="changeName">
            <Icon name="fa6-solid:id-card" class="display-inline mr-2" /> {{ t('contract_block.change_of_name') }}
        </DropdownOption>
        <DropdownOption :disabled="contract?.active_contract_termination || contract?.status?.token == terminatedStatusToken"
            :name="t('common.terminate')" @click="terminate">
            <Icon name="fa6-regular:circle-xmark" class="display-inline mr-2" /> {{ t('common.terminate') }}
        </DropdownOption>
        <DropdownOption :disabled="(contract?.contract_file && contract.contract_file.is_active !== false)"
            :name="`${t('common.generate')} ${t('contract')}`" @click="generateContract">
            <Icon name="fa6-solid:file-pdf" class="display-inline mr-2" />
            {{ $t('common.generate') }} {{ t('contract') }}
        </DropdownOption>
        <DropdownOption :name="`${t('common.modify')} ${t('contract_block.clauses')}`"
            @click="showDetail('ContractClausesEdit', contract.id)">
            <Icon name="fa6-solid:paragraph" class="display-inline mr-2" />
            {{ t('common.modify') }} {{ t('contract_block.clauses') }}
        </DropdownOption>

        <li class="flex items-center gap-2 px-3 py-1.5">
            <span class="h-px flex-1 bg-gray-100"></span>
            <span class="text-[10px] text-slate-400 uppercase tracking-wide">{{ t('billing') }}</span>
            <span class="h-px flex-1 bg-gray-100"></span>
        </li>
        <DropdownOption :name="`${t('common.modify')} ${t('bonifications')}`" @click="changeBonifications">
            <Icon name="fa6-solid:percent" class="display-inline mr-2" /> {{ t('common.modify') }} {{
                t('bonifications') }}
        </DropdownOption>
        <DropdownOption :name="`${t('common.modify')} ${t('common.price_rates')}`"
            @click="changePriceRates">
            <Icon name="fa6-solid:tag" class="display-inline mr-2" /> {{ t('common.modify') }} {{
                t('common.price_rates') }}
        </DropdownOption>
        <DropdownOption :name="`${t('contract_block.general_invoices')}`" @click="manageGeneralInvoices">
            <Icon name="fa6-solid:layer-group" class="display-inline mr-2" /> {{
                t('contract_block.general_invoices') }}
        </DropdownOption>
        <DropdownOption :name="`${t('common.massive_invoice_download')}`"
            @click="showDetail('MassiveInvoiceDownload', null)">
            <Icon name="fa6-solid:download" class="display-inline mr-2" /> {{ t('common.massive_invoice_download') }}
        </DropdownOption>
        <DropdownOption :name="`${t('common.add')} ${t('billing_block.custom_invoice')}`"
            @click="showDetail('AddInvoiceBudget', null)">
            <Icon name="fa6-solid:coins" class="display-inline mr-2" /> {{ t('common.add') }} {{
                t('billing_block.custom_invoice') }}
        </DropdownOption>
        <DropdownOption :name="t('contract_block.mark_as_billable')" @click="toggleBillable">
            <Icon name="fa6-solid:sack-xmark" class="display-inline mr-2" />
            {{ contract?.block_billing ? t('contract_block.mark_as_billable') :
                t('contract_block.mark_as_unbillable') }}
        </DropdownOption>
        <DropdownOption v-if="!contract?.holder?.is_juridic || (contract?.holder?.is_juridic && contract?.tenant)"
            :name="`${t('common.requesting')} ${t('contract_block.vulnerability')}`"
            @click="requestVulnerability" :disabled="contract?.active_vulnerability_requests">
            <Icon name="fa6-solid:shield-halved" class="display-inline mr-2" />
            {{ t('common.requesting') }} {{ t('contract_block.vulnerability') }}
        </DropdownOption>
        <DropdownOption :name="t('claim_block.new_claim_request')" @click="newClaimRequest">
            <Icon name="fa-solid:exclamation-circle" class="display-inline mr-2" />
            {{ t('claim_block.new_claim_request') }}
        </DropdownOption>
        <DropdownOption v-if="hasDebt" :name="t('claim_block.new_commitment_deposit')" @click="newCommitmentDeposit">
            <Icon name="fa6-solid:handshake" class="display-inline mr-2" />
            {{ t('claim_block.new_commitment_deposit') }}
        </DropdownOption>

        <li class="flex items-center gap-2 px-3 py-1.5">
            <span class="h-px flex-1 bg-gray-100"></span>
            <span class="text-[10px] text-slate-400 uppercase tracking-wide">{{ t('readings') }}</span>
            <span class="h-px flex-1 bg-gray-100"></span>
        </li>
        <DropdownOption :disabled="!contract?.supply_point_default || !contract?.supply_point_default?.meter_code"
            :name="`${t('common.modify')} ${t('readings')}`" @click="modifyReadings">
            <Icon name="fa6-solid:droplet" class="display-inline mr-2" /> {{ t('common.modify') }} {{
                t('readings') }}
        </DropdownOption>

        <li class="flex items-center gap-2 px-3 py-1.5">
            <span class="h-px flex-1 bg-gray-100"></span>
            <span class="text-[10px] text-slate-400 uppercase tracking-wide">{{ t('service') }}</span>
            <span class="h-px flex-1 bg-gray-100"></span>
        </li>
        <DropdownOption :name="t('service_block.cut_supply')" @click="cutSupplyPoint">
            <Icon name="fa6-solid:scissors" class="display-inline mr-2" />
            {{ t('service_block.cut_supply') }}
        </DropdownOption>

        <li class="flex items-center gap-2 px-3 py-1.5">
            <span class="h-px flex-1 bg-gray-100"></span>
            <span class="text-[10px] text-slate-400 uppercase tracking-wide">{{ t('customer_service') }}</span>
            <span class="h-px flex-1 bg-gray-100"></span>
        </li>
        <DropdownOption :name="t('customer_service_block.new_incident')"
            @click="showDetail('IncidentEdit', contract.id)">
            <Icon name="fa6-solid:bug" class="display-inline mr-2" /> {{
                t('customer_service_block.new_incident') }}
        </DropdownOption>
        <DropdownOption :name="`${t('common.add')} ${t('dashboard.task')}`"
            @click="showDetail('CalendarTaskEdit', null)">
            <Icon name="fa6-solid:calendar" class="display-inline mr-2" /> {{ t('common.add') }} {{
                t('dashboard.task') }}
        </DropdownOption>
        <DropdownOption :name="t('customer_service_block.new_comms_process')"
            @click="newCommunicationProcess">
            <Icon name="fa6-solid:envelopes-bulk" class="display-inline mr-2" /> {{
                t('customer_service_block.new_comms_process') }}
        </DropdownOption>

        <li class="flex items-center gap-2 px-3 py-1.5">
            <span class="h-px flex-1 bg-gray-100"></span>
            <span class="text-[10px] text-slate-400 uppercase tracking-wide">{{ t('work_orders') }}</span>
            <span class="h-px flex-1 bg-gray-100"></span>
        </li>
        <DropdownOption :name="t('order_block.new_order')" @click="newOrder">
            <Icon name="fa6-solid:clipboard-list" class="display-inline mr-2" />
            {{ t('order_block.new_order') }}
        </DropdownOption>

        <hr />
        <DropdownOption :name="`${t('common.delete')} ${t('contract')}`" @click="deleteContract">
            <Icon name="fa6-solid:eraser" class="display-inline mr-2" />
            {{ t('common.delete') }} {{ t('contract') }}
        </DropdownOption>
    </OptionsDropdown>
</template>
