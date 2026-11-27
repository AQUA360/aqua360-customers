<script setup>
import { formatDate } from '~/utils/date';

// Avís de factures pendents que el procés de facturació no ha domiciliat perquè el contracte
// tenia factures pendents de cobrar (paràmetre block_remittance_if_unpaid). El contracte
// continua domiciliat. `alert` ve del camp `remittance_blocked_alert` del contracte.
defineProps({
    alert: { type: Object, default: null },
});
</script>

<template>
    <div v-if="alert" role="alert" class="mb-2">
        <div class="flex items-start gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 shadow-sm">
            <div class="flex h-4 w-4 mt-0.5 shrink-0 items-center justify-center text-amber-700">
                <Icon name="fa6-solid:triangle-exclamation" class="text-sm" />
            </div>
            <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="text-sm font-semibold text-amber-900 leading-snug">
                    {{ $t('contract_block.remittance_blocked_alert_title') }}
                </span>
                <span class="text-sm text-amber-800 leading-snug">
                    {{ $t('contract_block.remittance_blocked_alert_detail') }}
                </span>
                <span class="text-xs text-amber-700 leading-snug">
                    {{ $t('contract_block.remittance_blocked_alert_count') }}: {{ alert.count }}
                    <template v-if="alert.invoices?.length"> ({{ alert.invoices.map(invoice => invoice.number).join(', ') }})</template>
                    <template v-if="alert.date"> · {{ formatDate(alert.date) }}</template>
                </span>
            </div>
        </div>
    </div>
</template>
