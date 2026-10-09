<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();

const props = defineProps({
    modelValue: {
        type: Array,
        default: () => []
    },
    payments: {
        type: Array,
        default: () => []
    }
});

const allSelected = computed(() => {
    return props.payments.every(payment => selectedTokens.value.has(payment?.token));
});

const emit = defineEmits(['update:modelValue']);

const selectedTokens = computed(() =>
    new Set((props.modelValue || []).map(payment => payment?.token).filter(Boolean))
);

const selectAll = () => {
    emit('update:modelValue', allSelected.value ? [] : props.payments, true);
}

const selectNextPayments = () => {
    emit('update:modelValue', props.payments.slice(0, 20), true);
}
const getOriginType = (payment) => {
    if (payment?.invoice) return t('invoice');
    if (payment?.commitment_deposit) return t('claim_block.pay_commitments');
    return '-';
};

const getOriginToken = (payment) => payment?.invoice?.serie_final || payment?.commitment_deposit?.token || '-';

const isSelected = (payment) => selectedTokens.value.has(payment?.token);

const paymentClicked = (payment) => {
    if (!payment?.token) return;

    const current = [...(props.modelValue || [])];
    const existingIndex = current.findIndex(item => item?.token === payment.token);

    if (existingIndex >= 0) {
        current.splice(existingIndex, 1);
    } else {
        current.push(payment);
    }

    emit('update:modelValue', current);
};
</script>

<template>
    <div id="wrapper" class="text-base">
        <div class="flex justify-between items-center mb-2">
            <H1 class="mb-2">{{ $t('billing_block.pending_payments') }}</H1>

            <div class="flex items-center gap-x-2">
                <button v-if="payments.length > 20" @click="selectNextPayments" class="button-default">
                    <Icon name="fa6-solid:check-all" />
                    {{ $t('common.select_first_multiple', { count: 20 }) }}
                </button>
                <button @click="selectAll" class="button-default">
                    <Icon name="fa6-solid:check-all" />
                    {{ allSelected ? $t('common.deselect_all') : $t('common.select_all') }}
                </button>
            </div>
        </div>

        <div id="list"
            style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 220px); max-height: calc(100vh - 220px);">
            <div
                class="heading grid grid-cols-[80px,80px,160px,80px,100px,150px,130px,10px] gap-3 border-b text-base items-center">
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.amount') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.due_date') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.payment_method') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.origin') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.identificator') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('common.status') }}</span>
                <span class="p-1 font-semibold text-slate-700">{{ $t('service_block.barcode_ident') }}</span>
                <span>&nbsp;</span>
            </div>

            <div v-for="payment in payments" :key="payment.token"
                class="grid grid-cols-[80px,80px,160px,80px,100px,150px,130px,10px] cursor-pointer gap-3 border-b text-base items-center bg-white mr-3"
                :class="{ 'bg-yellow-50': isSelected(payment) }" @click="paymentClicked(payment)">
                <span :class="{ selected: isSelected(payment) }" class="p-1 text-nowrap transition-all duration-200">
                    {{ formatMoneyWithCurrency(payment.amount) }}
                </span>
                <span :class="{ selected: isSelected(payment) }" class="p-1 text-nowrap transition-all duration-200">
                    {{ payment.due_date || '-' }}
                </span>
                <span :class="{ selected: isSelected(payment) }"
                    class="p-1 text-nowrap transition-all duration-200 truncate">
                    {{ payment.payment_type || '-' }}
                </span>
                <span :class="{ selected: isSelected(payment) }"
                    class="p-1 text-nowrap transition-all duration-200 truncate">
                    {{ getOriginType(payment) }}
                </span>
                <span :class="{ selected: isSelected(payment) }" class="p-1 text-nowrap transition-all duration-200">
                    {{ getOriginToken(payment) }}
                </span>
                <span :class="{ selected: isSelected(payment) }" class="p-1 text-nowrap transition-all duration-200">
                    <AtomsColorBadge :value="payment.status?.name || payment.status?.token || '-'"
                        :color="payment.status?.color" />
                </span>
                <span :class="{ selected: isSelected(payment) }" class="p-1 text-nowrap transition-all duration-200">
                    {{ payment.token || '-' }}
                </span>
                <span>&nbsp;</span>
            </div>

            <div v-if="payments.length === 0" class="my-3">
                <p>{{ $t('common.no_records') }}</p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.selected {
    margin-left: 15px;
}
</style>