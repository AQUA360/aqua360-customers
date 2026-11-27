<script setup>
import { computed } from 'vue';
import { formatDate } from '~/utils/date';

// Avís de mètode de pagament canviat pel sistema: retorn SEPA de compte invàlid o
// domiciliació bloquejada perquè el contracte tenia factures pendents de cobrar.
// `alert` ve del camp `payment_method_alert` de la factura.
const props = defineProps({
    alert: { type: Object, default: null },
});

const isInvalidAccount = computed(() => props.alert?.reason === 'invalid_account_return');
</script>

<template>
    <div v-if="alert" role="alert" class="mb-2">
        <div class="flex items-start gap-3 w-full rounded-lg border px-3 py-1.5 shadow-sm"
            :class="isInvalidAccount ? 'border-rose-300 bg-rose-50' : 'border-amber-300 bg-amber-50'">
            <div class="flex h-4 w-4 mt-0.5 shrink-0 items-center justify-center"
                :class="isInvalidAccount ? 'text-rose-700' : 'text-amber-700'">
                <Icon :name="isInvalidAccount ? 'fa6-solid:building-columns' : 'fa6-solid:triangle-exclamation'" class="text-sm" />
            </div>
            <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1"
                :class="isInvalidAccount ? 'text-rose-800' : 'text-amber-800'">
                <span class="text-sm font-semibold leading-snug"
                    :class="isInvalidAccount ? 'text-rose-900' : 'text-amber-900'">
                    {{ isInvalidAccount
                        ? $t('billing_block.payment_method_alert_invalid_account_title')
                        : $t('billing_block.payment_method_alert_blocked_title') }}
                </span>
                <span class="text-sm leading-snug">
                    {{ isInvalidAccount
                        ? $t('billing_block.payment_method_alert_invalid_account_detail')
                        : $t('billing_block.payment_method_alert_blocked_detail') }}
                </span>
                <span class="text-xs leading-snug">
                    <template v-if="alert.motive_token">
                        {{ alert.motive_token }}<template v-if="alert.motive_name"> · {{ alert.motive_name }}</template> ·
                    </template>
                    <template v-if="alert.date">{{ formatDate(alert.date) }}</template>
                    <template v-if="alert.previous_payment_type"> · {{ $t('billing_block.payment_method_alert_previous') }}: {{ alert.previous_payment_type }}</template>
                    <template v-if="alert.previous_iban"> · {{ $t('contract_block.invalid_account_alert_previous_iban') }}: {{ alert.previous_iban }}</template>
                </span>
            </div>
        </div>
    </div>
</template>
