<script setup>
import { formatDate } from '~/utils/date';

// Avís de domiciliació anul·lada per un retorn SEPA de compte invàlid.
// `alert` ve del camp `invalid_account_payment_alert` del contracte.
defineProps({
    alert: { type: Object, default: null },
});
</script>

<template>
    <div v-if="alert" role="alert" class="mb-2">
        <div class="flex items-start gap-3 w-full rounded-lg border border-rose-300 bg-rose-50 px-3 py-1.5 shadow-sm">
            <div class="flex h-4 w-4 mt-0.5 shrink-0 items-center justify-center text-rose-700">
                <Icon name="fa6-solid:building-columns" class="text-sm" />
            </div>
            <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="text-sm font-semibold text-rose-900 leading-snug">
                    {{ $t('contract_block.invalid_account_alert_title') }}
                </span>
                <span class="text-sm text-rose-800 leading-snug">
                    {{ $t('contract_block.invalid_account_alert_detail') }}
                </span>
                <span class="text-xs text-rose-700 leading-snug">
                    <template v-if="alert.motive_token">
                        {{ alert.motive_token }}<template v-if="alert.motive_name"> · {{ alert.motive_name }}</template>
                    </template>
                    <template v-if="alert.date"> · {{ formatDate(alert.date) }}</template>
                    <template v-if="alert.previous_iban"> · {{ $t('contract_block.invalid_account_alert_previous_iban') }}: {{ alert.previous_iban }}</template>
                </span>
            </div>
        </div>
    </div>
</template>
