<script setup>
import { ref, watch } from 'vue';
import { formatDate } from '~/utils/date';

// Resum d'un retorn SEPA triat com a origen d'un procés de comunicació.
const props = defineProps({
    return_id: {
        type: [Number, String],
        required: true
    },
});

const { $SepaRemittanceReturnApiService } = useNuxtApp();
const item = ref(null);

const getData = async () => {
    try {
        item.value = await $SepaRemittanceReturnApiService.getDetail(props.return_id);
    } catch (error) {
        console.error(error);
        item.value = null;
    }
}

watch(() => props.return_id, getData, { immediate: true });
</script>

<template>
    <div v-if="item" class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span class="text-slate-500">{{ $t('common.identification') }}</span>
        <span class="font-medium">{{ item.token }}</span>
        <span class="text-slate-500">{{ $t('common.returned') }}</span>
        <span>{{ item.return_date ? formatDate(item.return_date) : '-' }}</span>
        <span class="text-slate-500">{{ $t('billing_block.payments') }}</span>
        <span>{{ item.total_payments }}</span>
        <span class="text-slate-500">{{ $t('billing_block.total_amount') }}</span>
        <span>{{ formatMoneyWithCurrency(item.total_amount) }}</span>
    </div>
</template>
