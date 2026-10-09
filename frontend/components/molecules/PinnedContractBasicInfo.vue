<script setup>
import { ref, inject, nextTick } from 'vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import ContractStatusBadges from '~/components/molecules/ContractStatusBadges.vue';

const { t } = useI18n();

const props = defineProps({
    contract: Object,
})
const emit = defineEmits(['show-detail', 'new-call', 'change']);

const showAddresses = ref(false);
const showComms = ref(false);
const showContacts = ref(false);
const showWarnings = ref(false);
const isEditingRemittance = ref(false);
const remittance_date = ref(props.contract?.remittance_date ? parseInt(props.contract.remittance_date) : null);
const { $ContractApiService } = useNuxtApp();

const applyRemittanceDate = (value) => {
    remittance_date.value = value;
    if (props.contract) {
        props.contract.remittance_date = value;
    }
};

const emitChange = () => {
    const payload = {
        id: props.contract.id,
        remittance_date: remittance_date.value ? remittance_date.value : null,
    };
    applyRemittanceDate(payload.remittance_date);
    isEditingRemittance.value = false;
    $ContractApiService.save(payload).then((response) => {
        applyRemittanceDate(response?.remittance_date ?? null);
        emit('change');
    });
};

const clearRemittance = async () => {
    const previous = props.contract?.remittance_date ?? remittance_date.value;
    applyRemittanceDate(null);
    isEditingRemittance.value = false;
    await nextTick();
    if (!confirm(t('confirmation_text_block.confirm_delete'))) {
        applyRemittanceDate(previous);
        return;
    }
    $ContractApiService.save({
        id: props.contract.id,
        remittance_date: null,
    }).then(() => {
        emit('change');
    }).catch((err) => {
        console.error(err);
        applyRemittanceDate(previous);
    });
};

const startCall = async (item) => {
    showComms.value = false;
    showContacts.value = false;
    showAddresses.value = false;
    emit('new-call', item)
}

const isSubRegion = inject('isSubRegion', false);

const showDetail = (component, id) => {
    emit('show-detail', component, id);
}

</script>

<template>
    <div v-if="contract.important_observations && contract.important_observations.length > 0" class="col-span-3">
        <span v-for="observation in contract.important_observations" :key="observation.id"
            class="flex items-center gap-2 text-orange-600 font-semibold p-1 pr-2 text-left border-l-2 border-orange-500 bg-orange-100 rounded-r mb-2 w-fit">
            <Icon name="fa6-solid:circle-exclamation" class="text-orange-600" />
            {{ observation.observation }}
        </span>
    </div>

    <div class="flex gap-3 mb-3">

        <div class="relative col-span-3 rounded px-2 py-1 border border-slate-300 w-fit hover:bg-slate-50 hover:font-semibold cursor-pointer"
            @mouseenter="showWarnings = true" @mouseleave="showWarnings = false">
            <div class="flex items-center gap-2">
                <Icon name="fa6-solid:circle-exclamation"
                    :class="{ 'text-sky-500': contract.active_claim_requests || contract.active_contract_termination || contract.block_billing, 'text-slate-400': !contract.active_claim_requests && !contract.active_contract_termination && !contract.block_billing }" />
                <span class="text-slate-500 text-sm">
                    {{ t('common.warnings') }}
                </span>
            </div>

            <div class="absolute z-10 top-full left-0 mt-1 bg-white shadow-lg rounded-lg p-3 border border-slate-200 shadow min-w-max"
                v-if="showWarnings">

                <div v-if="!contract.active_claim_requests && !contract.active_contract_termination && !contract.block_billing"
                    role="row">
                    <div>
                        <div class="text-slate-500 px-2">
                            {{ t('common.no_warnings') }}
                        </div>
                    </div>
                </div>

                <div v-if="contract.active_claim_requests" role="row" class="mb-2">
                    <div class="flex justify-center items-center gap-2 border border-sky-500 rounded p-1 w-fit">
                        <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-sky-500 my-auto" />
                        <span class="text-sky-400 font-semibold">
                            {{ $t('informative_block.info_contract_claim') }}
                        </span>
                    </div>
                </div>
                <div v-if="contract.active_contract_termination" role="row" class="mb-2">
                    <div class="flex justify-center items-center gap-2 border border-red-500 rounded p-1 w-fit">
                        <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-red-500 my-auto" />
                        <span class="text-red-400 font-semibold">
                            {{ $t('informative_block.info_contract_termination') }}
                        </span>
                    </div>
                </div>
                <div v-if="contract.block_billing" role="row" class="mb-2">
                    <div class="flex justify-center items-center gap-2 border border-blue-500 rounded p-1 w-fit">
                        <Icon name="fa6-solid:sack-xmark" class="font-bold text-blue-500 my-auto" />
                        <span class="text-blue-400 font-semibold">
                            {{ $t('contract_block.block_billing') }}
                        </span>
                    </div>
                </div>
            </div>
        </div><!-- end relative avisos -->
        <ContractStatusBadges :contract="contract" :isSubRegion="isSubRegion" @show-detail="showDetail" />
    </div>
    <div class="grid grid-cols-3 gap-4" @click="showAddresses = false; showComms = false; showContacts = false">

        <div>
            <FieldDetail :label="t('common.creation_date')" :value="formatDate(contract.created_at)">
                <AtomsDate :date="contract.created_at"></AtomsDate>
            </FieldDetail>
            <FieldDetail :label="$t('common.usage_type')"
                :value="contract.use_type ? contract.use_type?.name : t('common.no_usage_type')"></FieldDetail>
            <FieldDetail :label="$t('contract_block.client_type')"
                :value="contract.client_type ? contract.client_type?.name : t('contract_block.no_client_type')">
            </FieldDetail>
            <FieldDetail :label="$t('contract_block.category')"
                :value="contract.category ? contract.category?.name : t('contract_block.no_category')"></FieldDetail>
            <FieldDetail :label="$t('contract_block.debt_management')"
                :value="contract.debt_management ? contract.debt_management.name : t('contract_block.no_debt_management')" />
            <!-- <FieldDetail :label="$t('common.persons')"
                :value="contract.total_persons ? (contract.total_persons).toString() : '-'" /> -->
            <FieldDetail v-if="contract.owner && contract.owner.id != contract.holder.id"
                :label="$t('contract_block.owner')" :value="contract.owner?.token" class="flex mr-5">
                <div class=" flex items-center"
                    :class="{ 'grid grid-cols-[auto,1fr]': contract.owner?.vulnerability_level > 0 }">
                    <AtomsVulnerabilityCheck v-if="contract.owner?.vulnerability_level > 0"
                        :vulnerability_level="contract.owner?.vulnerability_level" :small="true" class="mr-1" />
                    <AtomsPersonBadge :person="contract.owner" class="font-bold" />
                </div>
            </FieldDetail>
            <FieldDetail v-if="contract.tenant && contract.tenant.id != contract.holder.id"
                :label="$t('contract_block.tenant')" :value="contract.tenant?.token" class="flex mr-5">
                <div class=" flex items-center"
                    :class="{ 'grid grid-cols-[auto,1fr]': contract.tenant?.vulnerability_level > 0 }">
                    <AtomsVulnerabilityCheck v-if="contract.tenant?.vulnerability_level > 0"
                        :vulnerability_level="contract.tenant?.vulnerability_level" :small="true" class="mr-1" />
                    <AtomsPersonBadge :person="contract.tenant" class="font-bold" />
                </div>
            </FieldDetail>
            <div v-for="representant in contract.representatives">
                <FieldDetail :label="$t('contract_block.representative')" :value="representant.full_name"
                    class="flex mr-5">
                    <AtomsVulnerabilityCheck v-if="representant.person?.vulnerability_level > 0"
                        :vulnerability_level="representant.person?.vulnerability_level" :small="true" class="mr-1" />
                    <AtomsPersonBadge :person="representant.person" class="font-bold" />
                </FieldDetail>
                <p class="text-slate-400 text-right mr-5">{{ representant.type?.name || null }}</p>
            </div>
            <FieldDetail v-if="contract.last_contract_termination" :label="$t('common.contract_termination_detail')">
                <button @click="showDetail('ContractTerminationRegion', contract.last_contract_termination?.id)"
                    class="text-start text-sky-500 hover:no-underline underline hover:text-sky-600">{{
                        contract.last_contract_termination?.token }}</button>
            </FieldDetail>
            <details open class="w-full my-3 group">
                <summary
                    class="w-full flex items-center justify-between px-2 text-sm text-slate-600 hover:bg-sky-100 rounded transition-colors py-1 cursor-pointer">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:credit-card" class="w-3.5 h-3.5 text-sky-500" />
                        <span>{{ $t('common.payment_method') }}</span>
                    </div>
                    <Icon name="fa6-solid:chevron-up"
                        class="w-3 h-3 transform transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div class="mx-2 px-1 rounded mt-1">
                    <div class="grid grid-cols-2 gap-x-3">
                        <FieldDetail
                            v-if="contract.payment?.IBAN && contract.payment?.IBAN?.dni != contract.holder.token"
                            class="col-span-2" :label="$t('contract_block.holder')"
                            :value="`${contract.payment?.IBAN?.name} (${contract.payment?.IBAN?.dni})`" />
                        <FieldDetail :label="$t('common.payment_method')">
                            <abbr class="truncate"
                                :title="contract.payment?.type?.name || $t('common.no_payment_method')">
                                <span class="truncate">
                                    {{ contract.payment?.type?.name || $t('common.no_payment_method') }}
                                </span>
                            </abbr>
                        </FieldDetail>
                        <FieldDetail v-if="contract.payment?.IBAN?.updated_at" :label="$t('common.updated')"
                            :value="formatDate(contract.payment?.IBAN?.updated_at)" />
                    </div>
                    <div v-if="contract.payment?.type?.token == 'DIRECT_DEBIT'" class="relative group">
                        <MoleculesBankDetail :item="contract.payment?.IBAN" :is_detail="true"
                            :sepa="contract.payment?.sepa_document || null" :show_sepa="true" />
                    </div>

                    <div v-if="!isEditingRemittance && contract.remittance_date" class="mt-1">
                        <FieldDetail :label='$t("common.remittance_day")' class="items-center"
                            :value="contract.remittance_date ? contract.remittance_date.toString() : '-'">
                            <span v-if="!isSubRegion">
                                <span class="p-3">{{ contract.remittance_date ? contract.remittance_date : '-' }}</span>
                                <button class="px-2 py-1 text-gray-500"
                                    @click="isEditingRemittance = !isEditingRemittance">
                                    <Icon name="fa6-solid:pencil" />
                                </button>
                            </span>
                            <span v-else>
                                <span class="p-3">{{ contract.remittance_date }}</span>
                            </span>
                        </FieldDetail>
                    </div>
                    <div v-else-if="isEditingRemittance" class="grid grid-cols-2">
                        <FieldDetail :label='$t("common.remittance_day")'
                            :value="(remittance_date ?? '-').toString()"
                            class="items-center">
                            <span class="flex gap-3 w-full h-[75%]">
                                <input type="number" v-model="remittance_date" class="input w-3/4" />
                                <button class="py-1 text-gray-500 hover:text-sky-600" @click="emitChange">
                                    <Icon name="fa6-solid:floppy-disk" />
                                </button>
                                <button v-if="props.contract.remittance_date"
                                    class="py-1 text-gray-500 hover:text-red-500" @click="clearRemittance">
                                    <Icon name="fa6-solid:trash" />
                                </button>
                            </span>
                        </FieldDetail>
                    </div>

                    <div v-if="contract.general_invoice"
                        class="mt-1 px-2 mr-2 border border-slate-200 rounded text-sm text-slate-500 font-medium">
                        <div class="flex items-center gap-2 my-1">
                            <!-- <Icon name="fa6-solid:circle-info" class="text-sky-500 flex-shrink-0" /> -->
                            <span class="font-semibold">{{ t('informative_block.info_general_invoice') }}</span>
                        </div>
                        <FieldDetail :label="$t('common.send_address')" :value="contract.general_invoice.address_send">
                        </FieldDetail>
                        <FieldDetail :label="$t('common.payment_method')"
                            :value="contract.general_invoice.payment_type">
                        </FieldDetail>
                        <AtomsIBAN v-if="contract.general_invoice.payment_iban"
                            :iban="contract.general_invoice.payment_iban" />
                    </div>
                </div>
            </details>

        </div>

        <div>
            <details open class="w-full group">
                <summary
                    class="w-full flex items-center justify-between px-2 text-sm text-slate-600 hover:bg-sky-100 rounded transition-colors py-1 cursor-pointer">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:house" class="w-3.5 h-3.5 text-sky-500" />
                        <Icon v-if="!contract.address_billing && !contract.address_contact" name="fa6-solid:exclamation"
                            class="text-sky-500" />
                        <span>{{ $t('address_block.addresses') }}</span>
                    </div>
                    <Icon name="fa6-solid:chevron-up"
                        class="w-3 h-3 transform transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div class="mx-2 px-1  rounded">
                    <div class="space-y-2">
                        <div
                            v-if="contract.address_billing && contract.address_contact && contract.address_billing.address_complete === contract.address_contact.address_complete">
                            <div class="text-xs font-medium text-slate-500">
                                {{ $t('common.fiscal_address') }} {{ $t('common.and') }} {{ $t('common.contact') }}
                            </div>
                            <div class="text-sm">{{ contract.address_billing.address_complete }}</div>
                        </div>
                        <template v-else>
                            <div v-if="contract.address_billing">
                                <div class="text-xs font-medium text-slate-500">{{ $t('common.fiscal_address') }}</div>
                                <div class="text-sm">{{ contract.address_billing.address_complete }}</div>
                            </div>
                            <div v-if="contract.address_contact">
                                <div class="text-xs font-medium text-slate-500">{{ $t('contract_block.contact_address')
                                    }}</div>
                                <div class="text-sm">{{ contract.address_contact.address_complete }}</div>
                            </div>
                        </template>
                    </div>
                </div>
            </details>
            <details open class="w-full my-3 group">
                <summary
                    class="w-full flex items-center justify-between px-2 text-sm text-slate-600 hover:bg-sky-100 rounded transition-colors py-1 cursor-pointer">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:at" class="w-3.5 h-3.5 text-sky-500" />
                        <Icon name="fa6-solid:exclamation"
                            v-if="!contract.person_contact_email && contract.person_contact_sms.length == 0 && !contract.address_contact?.address_complete"
                            class="text-sky-500" />
                        <span v-if="contract.communication_type == 'DIGITAL'">{{ $t('contract_block.digital_comm')
                            }}</span>
                        <span v-else-if="contract.communication_type == 'PAPER'">{{ $t('contract_block.paper_comm')
                            }}</span>
                    </div>
                    <Icon name="fa6-solid:chevron-up"
                        class="w-3 h-3 transform transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div class="mx-2 px-1  rounded">
                    <div v-if="contract.communication_type == 'DIGITAL'" class="space-y-2">
                        <div>
                            <!-- <div class="text-xs font-medium text-slate-500">{{ $t('Comm. Digital') }}</div> -->
                            <div class="text-sm">
                                <div>{{ contract.person_contact_email?.email || $t('common.no_email_long') }}</div>
                                <!-- <div v-if="contract.person_contact_sms.length > 0" class="mt-1">
                                    <div v-for="phone in contract.person_contact_sms" :key="phone.id"
                                        class="flex items-center gap-1 text-slate-600">
                                        <span class="text-sm">SMS:</span>
                                        <button @click="startCall(phone)" class="text-sky-500 hover:text-sky-600">{{
                                            phone.phone }}</button>
                                    </div>
                                </div>
                                <div v-else class="text-xs text-slate-400">{{ $t('customer_service_block.no_tlf_sms') }}
                                </div> -->
                            </div>
                        </div>
                    </div>
                    <div v-else>
                        <!-- <div class="text-xs font-medium text-slate-500">{{ $t('Comm. Paper') }}</div> -->
                        <div class="text-sm">{{ contract.address_contact?.address_complete || '-' }}</div>
                    </div>
                </div>
            </details>
            <details open class="w-full my-3 group">
                <summary
                    class="w-full flex items-center justify-between px-2 text-sm text-slate-600 hover:bg-sky-100 rounded transition-colors py-1 cursor-pointer">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:comments" class="w-3.5 h-3.5 text-sky-500" />
                        <Icon name="fa6-solid:exclamation" v-if="contract.contacts.length == 0" class="text-sky-500" />
                        <span>{{ $t('common.contacts') }} ({{ contract.contacts.length }})</span>
                    </div>
                    <Icon name="fa6-solid:chevron-up"
                        class="w-3 h-3 transform transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div class="mx-2 px-1 rounded">
                    <div v-if="contract.contacts.length == 0" class="text-sm text-slate-400">
                        {{ $t('common.no_contact') }}
                    </div>
                    <div v-else class="space-y-1">
                        <div v-for="item in contract.contacts" :key="item.id"
                            class="border border-slate-200 px-3 pt-2 rounded">
                            <MoleculesPersonContactDetail
                                :isSMS="contract.person_contact_sms.length > 0 && contract.person_contact_sms.find(sms => sms.id == item.id)"
                                :item="item" @add-call="startCall" />
                        </div>
                    </div>
                </div>
            </details>
            <details
                v-if="contract.payment?.accounting_office && contract.payment?.managing_body && contract.payment?.processing_unit"
                open class="w-full my-3 group">
                <summary
                    class="w-full flex items-center justify-between px-2 text-sm text-slate-600 hover:bg-sky-100 rounded transition-colors py-1 cursor-pointer">
                    <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:file-invoice" class="w-3.5 h-3.5 text-sky-500" />
                        <span>{{ t('common.electronic_invoice') }}</span>
                    </div>
                    <Icon name="fa6-solid:chevron-up"
                        class="w-3 h-3 transform transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div class="mx-2 px-1 rounded">
                    <div class="grid grid-cols-2 gap-x-2 border border-slate-200 px-3 pt-2 rounded">
                        <FieldDetail :label="$t('billing_block.short_accounting_office')">
                            <abbr class="truncate" :title="contract.payment?.accounting_office">
                                <span class="truncate text-sm">
                                    {{ contract.payment?.accounting_office }}
                                </span>
                            </abbr>
                        </FieldDetail>
                        <FieldDetail :label="$t('billing_block.short_managing_body')">
                            <abbr class="truncate" :title="contract.payment?.managing_body">
                                <span class="truncate text-sm">
                                    {{ contract.payment?.managing_body }}
                                </span>
                            </abbr>
                        </FieldDetail>
                        <FieldDetail :label="$t('billing_block.short_processing_unit')">
                            <abbr class="truncate" :title="contract.payment?.processing_unit">
                                <span class="truncate text-sm">
                                    {{ contract.payment?.processing_unit }}
                                </span>
                            </abbr>
                        </FieldDetail>
                        <FieldDetail v-if="contract.payment?.command" :label="$t('billing_block.command')">
                            <abbr class="truncate" :title="contract.payment?.command">
                                <span class="truncate text-sm">
                                    {{ contract.payment?.command }}
                                </span>
                            </abbr>
                        </FieldDetail>
                        <FieldDetail v-if="contract.payment?.record" :label="$t('billing_block.record')">
                            <abbr class="truncate" :title="contract.payment?.record">
                                <span class="truncate text-sm">
                                    {{ contract.payment?.record }}
                                </span>
                            </abbr>
                        </FieldDetail>
                    </div>
                    
                </div>
            </details>

            <div class="grid grid-cols-2 gap-2 mt-1">
                <div v-if="contract.communication_type == 'DIGITAL' && (!contract.person_contact_email || contract.person_contact_email?.email == null)"
                    class="flex items-center gap-2 bg-orange-100 text-orange-500 border border-orange-500 rounded-md px-2 py-1">
                    <!-- sense email-->
                    <Icon name="fa6-solid:at" class="w-3.5 h-3.5 text-orange-500" />
                    <span>{{ $t('common.no_email_long') }}</span>
                </div>
            </div>
        </div>

        <div>
            <FieldDetail :label="`${$t('common.identification')}. ${$t('common.supply')}`">
                <button v-if="contract.supply_point_default"
                    @click="showDetail('SupplyPointRegion', contract.supply_point_default?.id)"
                    class="text-start text-sky-500 hover:no-underline underline hover:text-sky-600">{{
                        contract.supply_point_default?.token }}</button>
                <span v-else>-</span>
            </FieldDetail>
            <FieldDetail :label="$t('service_block.supply_source')"
                :value="contract.supply_point_default?.source?.name">
            </FieldDetail>
            <FieldDetail :label="$t('service_block.supply_type')"
                :value="contract.supply_point_default?.supply_type?.name">
            </FieldDetail>
            <FieldDetail :label="$t('service_block.is_potable')"
                :value="contract.supply_point_default?.is_potable ? $t('common.yes') : $t('common.no')">
            </FieldDetail>
            <FieldDetail :label="$t('meter')">
                <button v-if="contract.supply_point_default?.meter"
                    @click="showDetail('MeterRegion', contract.supply_point_default?.meter.id)"
                    class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">{{
                        contract.supply_point_default?.meter.code }}</button>
                <span v-else>-</span>
            </FieldDetail>
        </div>
        <!-- <div v-if="contract.important_observations && contract.important_observations.length > 0" class="col-span-3">
            <span v-for="observation in contract.important_observations" :key="observation.id"
                class="flex items-center gap-2 text-orange-600 font-semibold p-1 pr-2 text-left border-l-2 border-orange-500 bg-orange-100 rounded-r w-fit">
                <Icon name="fa6-solid:circle-exclamation" class="text-orange-600" />
                {{ observation.observation }}
            </span>
        </div> -->
    </div>

</template>
