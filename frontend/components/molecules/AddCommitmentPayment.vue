<script setup>
import { format } from 'date-fns';
import H1Region from '../atoms/H1Region.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

const props = defineProps({
    id: Number,
});

const { t } = useI18n();
const emit = defineEmits(['change']);
const { $CommitmentDepositApiService, $PaymentCommitmentApiService } = useNuxtApp();

const showRegionComponent = ref('');
const showRegion = ref(false);

const loading = ref(true);
const error = ref(null)
const attemptedSave = ref(false);
const saving = ref(false);

const paymentTypeOptionsById = ref([]);

const depositData = ref(null);
const data = ref(null)

const paymentDate = ref()
const paymentAmount = ref(null)
const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);

const availableBalance = computed(() => {
    return depositData.value.contract_piggy_bank;
});

const paymentTypeExcludeTokens = computed(() =>
    availableBalance.value <= 0 ? ['BALANCE'] : []
);

const getData = async () => {
    loading.value = true
    try {
        const result = await $CommitmentDepositApiService.getDetail(props.id);
        depositData.value = result;
        paymentDate.value = format(new Date(), 'yyyy-MM-dd').toString();

    } catch (err) {
        error.value = err;
        console.error(err)
    } finally {
        loading.value = false;
    }
}

const onPaymentTypesLoaded = ({ byId }) => {
    paymentTypeOptionsById.value = byId;
};

const isValid = () => {
    if (!paymentDate.value) return false;
    if (!paymentAmount.value || paymentAmount.value == 0) return false;
    if (!selectedPaymentMethod.value) return false;

    return true;
}

const save = async () => {
    attemptedSave.value = true;
    if (!isValid()) return;

    if (!confirm(t('confirmation_text_block.confirm_pay_payment'))) return;
    saving.value = true;
    try {
        let save_data = {
            commitment_deposit_id: props.id,
            payment_date: paymentDate.value,
            currently_paid: paymentAmount.value,
            payment_type_id: selectedPaymentMethod.value,
            payment_bank: selectedBankDebit.value || null,
            payment_bank_final: selectedBankDebit.value?.iban || null,
            payment_swift_final: selectedBankDebit.value?.swift || null,
            is_guide: false,
        };

        let response = await $PaymentCommitmentApiService.save(save_data);
        emit('change')
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
        attemptedSave.value = false;
    }

}

const onSelectPaymentMethod = () => {
    selectedBankDebit.value = null;
    if (availableBalance.value > 0 && paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token == 'BALANCE') {
        if (availableBalance.value < depositData.value.remaining) {
            paymentAmount.value = availableBalance.value;
        } else {
            paymentAmount.value = depositData.value.remaining;
        }
    }
}

const openPersonBankSelect = () => {
    closeAllRegions();
    showRegionComponent.value = 'PersonBankSelect';
    showRegion.value = true;
};


const onPersonBankSelected = (bank) => {
    selectedBankDebit.value = bank;
    closeAllRegions();
};

const closeAllRegions = () => {
    showRegionComponent.value = '';
    showRegion.value = false;
};

onMounted(async () => {
    await getData()
})

</script>

<template>
    <div class="region__content">
        <!-- OPTIONAL INFO -->
        <div v-if="loading">
            <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
            <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
        </div>
        <div v-else>
            <H1Region class="mb-4">{{ $t('billing_block.new_paid_payment') }}</H1Region>
            <div class="my-2 grid grid-cols-2 gap-4">
                <div class="mb-2">
                    <AtomsInputDate v-model="paymentDate" :label="t('billing_block.payment_date')" class="mb-2"
                        :required="true" />
                </div>

                <div class="mb-2">
                    <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.total_paid') }}
                        *</label>
                    <input required type="number" v-model="paymentAmount" 
                    :disabled="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'BALANCE'"
                        :class="{ 'invalid': attemptedSave && (!paymentAmount || paymentAmount == 0) }" class="input" />
                </div>

                <div class="mb-2 col-span-2">
                    <div class="flex flex-row justify-between gap-4">
                        <div class="w-[65%]">
                            <SelectPaymentType v-if="depositData" v-model="selectedPaymentMethod"
                                :exclude-tokens="paymentTypeExcludeTokens" :model-as-number="true"
                                :invalid="attemptedSave && !selectedPaymentMethod"
                                @change="onSelectPaymentMethod" @loaded="onPaymentTypesLoaded">
                                <template #label>
                                    <label class="block text-sm font-medium text-slate-500 mb-2">
                                        {{ t('common.payment_method') }} *
                                    </label>
                                </template>
                            </SelectPaymentType>
                        </div>
                        <div class="flex self-end"
                            v-if="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'BALANCE'">
                            <div class="flex items-center gap-2 p-2 rounded border border-slate-300 w-fit">
                                <Icon name="fa6-solid:piggy-bank" class="text-slate-400" />
                                <span class="text-slate-500">
                                    {{ t('contract_block.available_balance') }}
                                </span>
                                <span class="text-green-600 font-bold">
                                    {{ formatMoneyWithCurrency(availableBalance) }}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="select_bank mt-3 w-[65%]"
                        v-if="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT'">
                        <div v-if="selectedBankDebit" class="bg-green-100 p-4 rounded relative group">
                            <div>
                                <BankDetail :item="selectedBankDebit" />
                            </div>
                            <button @click="openPersonBankSelect"
                                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                                <Icon name="fa6-solid:pencil" />
                            </button>
                        </div>

                        <ButtonSeleccio v-else @click="openPersonBankSelect()" class="py-3">
                            <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                            {{ $t('common.select') }} {{ $t('common.iban') }}
                        </ButtonSeleccio>
                    </div>
                </div>
            </div>
            <hr />
            <div class="flex flex-row-reverse mt-4">
                <button @click="save" :disabled="saving" class="button-primary">
                    <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
                </button>
            </div>
        </div>
        <div v-if="showRegion == true" role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[47%] overflow-y-auto overflow-x-hidden"
            :class="{
                'translate-x-0': showRegion,
                'translate-x-full': !showRegion,

            }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeAllRegions()"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
                    :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="[depositData.contract.holder]"
                    @selected-item="onPersonBankSelected" />
            </div>
        </div>
    </div>

</template>