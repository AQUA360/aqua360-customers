<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';

const { t } = useI18n();

const props = defineProps({
    id: Number, //CommitmentDepositId
    item: Object, //invoices
    isSubRegion: {
        type: Boolean,
        default: false
    },
});
const emit = defineEmits(['change']);
const { $PaymentApiService, $CommitmentDepositApiService, $ConfigProjectApiService } = useNuxtApp();

const loading = ref(true);
const saving = ref(false);

const selectedPayments = ref([])
const selectedPaymentsTotal = ref(0)
const localData = ref(null);
const commitmentDeposit = ref(null)

const paid_status_token = ref(null)

const disablePayments = computed(() => {
    try {
        return selectedPaymentsTotal.value > commitmentDeposit.value.remaining_to_share
    } catch (err) {
        console.error('Error obtenint les dades:', err);
        return true
    }
})

const getData = async () => {
    try {
        const result = await $CommitmentDepositApiService.getDetail(props.id);
        commitmentDeposit.value = result;
    } catch (err) {
        console.error('Error obtenint les dades:', err);
    }
};

const getPaymentsFromInvoice = async (invoice) => {
    try {
        const result = await $PaymentApiService.getAll('', [], 1, null, false, invoice.id);
        return result.results
    } catch (err) {
        console.error('Error obtenint les dades:', err);
        return []
    } finally {
        loading.value = false;
    }
}

const loadLocalDataWithPayments = async (items) => {
    const enriched = await Promise.all(items.map(async (invoice) => {
        const payments = await getPaymentsFromInvoice(invoice);
        return { ...invoice, payments };
    }));

    localData.value = enriched;
};

const paymentClicked = ((payment) => {
    if (selectedPayments.value.includes(payment.id)) {
        var index = selectedPayments.value.indexOf(payment.id);
        if (index > -1) {
            selectedPayments.value.splice(index, 1);
        }
    }
    else selectedPayments.value.push(payment.id)

    const total = localData.value.reduce((total, invoice) => {
        return total + invoice.payments.reduce((subtotal, p) => {
            return subtotal + (selectedPayments.value.includes(p.id) ? parseFloat(p.amount) : 0);
        }, 0);
    }, 0);
    selectedPaymentsTotal.value = Math.round(total * 100) / 100;

})

const save = async () => {
    if (!confirm(t("confirmation_text_block.confirm_apply"))) return
    saving.value = true;
    try {
        for (let payment of selectedPayments.value) {
            await $PaymentApiService.save({
                id: payment,
                status_token: paid_status_token.value,
                payment_date: commitmentDeposit.value.due_date_commitment,
                is_piggy_contract: false
            })
        }
        emit('change')
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
}

onMounted(async () => {
    loading.value = true;
    paid_status_token.value = await $ConfigProjectApiService.get('payment_status_paid_token')
    await getData()
    await loadLocalDataWithPayments(props.item);
});

watch(() => props.item, async (newVal) => {
    loading.value = true;
    await getData()
    await loadLocalDataWithPayments(newVal);
});

</script>

<template>
    <div class="wrapper">
        <div v-if="loading">
            <div class="flex justify-center items-center py-6">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-400" />
                <span class="ml-3 text-sm text-slate-500">{{ $t('common.loading') }}...</span>
            </div>
        </div>

        <div v-if="!loading && localData && localData.length > 0"
            class="min-w-full text-sm text-slate-700 mt-4 relative">
            <H1Region class="mb-4">
                {{ $t('common.liquidate') }} {{ $t('invoices') }} {{ $t('common.and') }} {{ $t('billing_block.payments') }}
            </H1Region>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 w-full mb-6 p-4 bg-white rounded-lg shadow-sm">
                <div class="flex items-center gap-2 text-slate-600">
                    <Icon name="fa6-solid:check-double" class="text-blue-500" />
                    <span>{{ $t('billing_block.selected_payments') }}:</span>
                    <span class="font-medium text-slate-700">{{ selectedPayments.length }}</span>
                </div>
                <div class="flex items-center gap-2 text-slate-600">
                    <Icon name="fa6-solid:wallet" class="text-green-500" />
                    <span>{{ $t('billing_block.total_available') }}:</span>
                    <span class="font-medium text-green-600">{{
                        formatMoneyWithCurrency(commitmentDeposit.remaining_to_share)
                    }}</span>
                </div>
                <div class="flex items-center gap-2 text-slate-600">
                    <Icon name="fa6-solid:sack-dollar" class="text-yellow-500" />
                    <span>{{ $t('billing_block.total_to_liquidate') }}:</span>
                    <span class="font-medium text-yellow-600">{{ formatMoneyWithCurrency(selectedPaymentsTotal)
                    }}</span>
                </div>
            </div>

            <div v-if="disablePayments"
                class="flex items-center bg-orange-100 text-orange-600 rounded-md px-4 py-3 mb-4 border-l-4 border-orange-500 shadow-sm">
                <Icon name="fa6-solid:triangle-exclamation" class="text-orange-500 text-xl" />
                <span class="ml-3">{{ $t('warning_block.warning_liquidate_limit') }} <span class="font-semibold">{{
                    formatMoneyWithCurrency(commitmentDeposit.remaining_to_share) }}</span>.</span>
            </div>
            <div class="h-[60vh] overflow-y-auto">

                <div v-for="item in localData" :key="item.id" class="bg-slate-50 rounded-lg shadow-sm mb-4 overflow-hidden">
    
                    <div class="px-4 py-1 grid grid-cols-2 gap-4 border-b border-slate-200">
                        <div class="text-slate-700 flex items-center">
                            <span class="font-semibold mr-2">{{ $t('invoice') }}:</span>
                            <span class="text-slate-600">{{ item.serie_final }}</span>
                        </div>
                        <div class="text-slate-700 flex items-center">
                            <span class="font-semibold mr-2">{{ $t('common.title') }}:</span>
                            <span>{{ item.title_final }}</span>
                        </div>
                        <!-- <div class="text-slate-700 flex items-center">
                            <span class="font-semibold mr-2">{{ $t('billing_block.paid') }}:</span>
                            <p class="text-green-600 font-medium">{{ formatMoneyWithCurrency(item.total_final) }}</p>
                        </div> -->
                        <div class="text-slate-700 flex items-center">
                            <span class="font-semibold mr-2">{{ $t('common.total') }}:</span>
                            <span class="font-medium text-slate-800">{{ formatMoneyWithCurrency(item.left_to_pay) }}</span>
                        </div>
                    </div>
    
                    <div v-if="item.payments && item.payments.length > 0" class="p-4 bg-white">
                        <div
                            class="grid grid-cols-[25px,1fr,1fr,1.5fr,1fr] gap-4 text-slate-600 font-semibold border-b border-slate-200 pb-2 mb-2">
                            <span></span> <!-- Placeholder for selection -->
                            <span>{{ $t('common.identification') }}</span>
                            <span>{{ $t('common.total') }}</span>
                            <span>{{ $t('common.payment_method') }}</span>
                            <span>{{ $t('common.status') }}</span>
                        </div>
    
    
                        <div v-for="payment in item.payments" :key="payment.id"
                            @click="payment.status.token != paid_status_token ? paymentClicked(payment) : null"
                            class="grid grid-cols-[25px,1fr,1fr,1.5fr,1fr] gap-4 items-center py-1 border-b border-slate-100 last:border-b-0 transition duration-150 ease-in-out rounded-sm"
                            :class="{
                                'bg-yellow-50 selected': selectedPayments.includes(payment.id),
                                'cursor-pointer hover:bg-slate-50': payment.status.token != paid_status_token,
                                'cursor-not-allowed opacity-70': payment.status.token == paid_status_token,
                            }">
                            <div class="flex justify-center items-center">
                                <Icon :name="selectedPayments.includes(payment.id) ? 'fa6-solid:check' : 'fa6-solid:chevron-right'"
                                    :class="selectedPayments.includes(payment.id) ? 'text-yellow-500' : 'text-slate-300'"
                                    class="text-xs" />
                            </div>
                            <div class="text-slate-700 font-mono">
                                {{ payment.token }}
                            </div>
                            <div class="text-slate-700 font-medium">
                                {{ formatMoneyWithCurrency(payment.amount) }}
                            </div>
                            <div class="text-slate-700">
                                {{ payment.payment_type }}
                            </div>
                            <div class="text-slate-700">
                                <AtomsColorBadge :value="payment.status?.name" :color="payment.status?.color" />
                            </div>
                        </div>
                    </div>
                    <div v-else class="p-4 bg-slate-50 text-slate-500 italic text-center">
                        <Icon name="fa6-solid:money-bill-transfer" class="text-xl mr-2" />
                        {{ $t('common.no_records') }}
                    </div>
                </div>
            </div>
            <div class="fixed right-0 bottom-0 py-4 px-4 border-t border-slate-300 w-[50%] bg-white">
                <div class="flex justify-end items-center px-4">
                    <button @click="save" :disabled="disablePayments || selectedPayments.length == 0" :loading="saving"
                        class="button-primary flex items-center gap-2">
                        <Icon name="fa6-solid:floppy-disk" /> {{ $t('common.save') }}
                    </button>
                </div>
            </div>
        </div>

        <div v-else-if="!loading && (!localData || localData.length === 0)"
            class="p-6 text-center text-slate-500 italic bg-white rounded-lg shadow-sm">
            <Icon name="fa6-solid:exclamation-circle" class="text-3xl mb-3" />
            <p>{{ $t('common.no_data_found') }}</p>
        </div>
    </div>
</template>
<style scoped>
.selected {
    margin-left: 15px
}
</style>
