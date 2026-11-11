<script setup>
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
    contract: Object,
    isSubRegion: Boolean,
    // Show the consumption bag and commitment deposit badges
    showExtra: {
        type: Boolean,
        default: true
    },
    // Debt badge opens ContractDebtRegion (only where the parent handles it)
    showDebtDetail: {
        type: Boolean,
        default: false
    },
    // Bail badge switches to the bails tab (only where the parent handles it)
    showBailTab: {
        type: Boolean,
        default: false
    },
});

const emit = defineEmits(['show-detail', 'show-tab']);

const { t } = useI18n();
const { $ConfigProjectApiService } = useNuxtApp();

const bailReturnedToken = ref(null);

const showDetail = (component, id) => {
    emit('show-detail', component, id);
}

const showTab = (tab) => {
    emit('show-tab', tab);
}

const availableBailAmount = computed(() => {
    const bails = props.contract?.bails;
    if (!bails?.length) return 0;
    return bails
        .filter((bail) => bail.status_token !== bailReturnedToken.value)
        .reduce((acc, bail) => acc + (parseFloat(bail.amount) || 0), 0);
});

const totalBagConsumption = computed(() => {
    if (!props.contract?.estimated_bags) return 0;
    return props.contract.estimated_bags.reduce((acc, bag) => acc + (parseFloat(bag.total_consumption) || 0), 0);
});

const mainBagId = computed(() => {
    if (!props.contract?.estimated_bags) return null;
    const activeBag = props.contract.estimated_bags.find(e => parseFloat(e.total_consumption) > 0);
    return activeBag ? activeBag.id : (props.contract.estimated_bags[0]?.id || null);
});

function removeUselessZero(value) {
    if (!value) return '';
    if (value.includes('.')) {
        return value.replace(/\.?0+$/, '');
    }
    return value;
}

onMounted(async () => {
    try {
        bailReturnedToken.value = await $ConfigProjectApiService.get('bail_status_returned_token');
    } catch (err) {
        console.error(err);
    }
});
</script>



<template>
    <div class="flex gap-x-3 mb-1">
        <div class="flex items-center gap-2 rounded px-2 py-1 border truncate"
            :class="`bg-${contract.status?.color}-100 border-${contract.status?.color}-600`">
            <Icon name="fa6-solid:file-contract" :class="`text-${contract.status?.color}-600`" />
            <span class="text-sm" :class="`text-${contract.status?.color}-600`">
                {{ contract.status?.name }}
            </span>
        </div>
        <button v-if="contract.piggy_bank" @click="showDetail('PiggyBankRegion', contract.piggy_bank.id)"
            :disabled="isSubRegion"
            class="flex items-center gap-2 rounded px-2 py-1 border transition-all truncate enabled:bg-sky-50 enabled:border-sky-300 enabled:text-sky-700 enabled:hover:bg-sky-100 enabled:hover:border-sky-400 disabled:bg-slate-50 disabled:border-slate-200 disabled:text-slate-400 disabled:cursor-default shadow-sm group"
            :title="!isSubRegion ? t('common.view_details') : ''">
            <Icon name="fa6-solid:piggy-bank" class="text-sky-500 group-disabled:text-slate-400" />
            <span class="text-sm font-semibold">
                {{ t('contract_block.balance') }}: {{ formatMoneyWithCurrency(contract.piggy_bank.amount) }}
            </span>
            <Icon v-if="!isSubRegion" name="fa6-solid:chevron-right" class="text-sky-400 text-[10px] ml-1 group-hover:translate-x-0.5 transition-transform" />
        </button>
        <component :is="showBailTab ? 'button' : 'div'"
            v-if="availableBailAmount > 0"
            @click="showBailTab && showTab('bails')"
            class="flex items-center gap-2 rounded px-2 py-1 border truncate transition-colors group shadow-sm"
            :class="showBailTab
                ? 'bg-sky-50 border-sky-300 text-sky-700 hover:bg-sky-100 hover:border-sky-400'
                : 'bg-slate-50 border-slate-200 text-slate-500'"
            :title="showBailTab ? t('common.view_details') : ''">
            <Icon name="fa6-solid:money-bills" :class="showBailTab ? 'text-sky-500' : 'text-slate-400'" />
            <span class="text-sm font-semibold">
                {{ t('bail') }}: {{ formatMoneyWithCurrency(availableBailAmount) }}
            </span>
            <Icon v-if="showBailTab" name="fa6-solid:chevron-right"
                class="text-sky-400 text-[10px] ml-1 group-hover:translate-x-0.5 transition-transform" />
        </component>
        <button v-if="showExtra && totalBagConsumption > 0 && mainBagId" @click="showDetail('EstimatedBagRegion', mainBagId)"
            :disabled="isSubRegion"
            class="flex items-center gap-2 rounded px-2 py-1 border transition-all truncate enabled:bg-sky-50 enabled:border-sky-300 enabled:text-sky-700 enabled:hover:bg-sky-100 enabled:hover:border-sky-400 disabled:bg-slate-50 disabled:border-slate-200 disabled:text-slate-400 disabled:cursor-default shadow-sm group"
            :title="!isSubRegion ? t('common.view_details') : ''">
            <Icon name="fa6-solid:droplet" class="text-sky-500 group-disabled:text-slate-400" />
            <span class="text-sm font-semibold">
                {{ t('billing_block.consumption_bag') }}: {{ removeUselessZero(totalBagConsumption.toString()) }} m³
            </span>
            <Icon v-if="!isSubRegion" name="fa6-solid:chevron-right" class="text-sky-400 text-[10px] ml-1 group-hover:translate-x-0.5 transition-transform" />
        </button>
        <component :is="showDebtDetail ? 'button' : 'div'"
            @click="showDebtDetail && !isSubRegion && showDetail('ContractDebtRegion', contract.id)"
            :disabled="showDebtDetail ? isSubRegion : undefined"
            class="flex items-center gap-2 rounded px-2 py-1 border truncate transition-colors group"
            :class="[
                contract.debt_amount > 0 ? 'bg-red-50 border-red-300' : 'border-slate-300',
                { 'shadow-sm enabled:hover:border-red-400 enabled:hover:bg-red-100 disabled:cursor-default': showDebtDetail },
            ]"
            :title="showDebtDetail && !isSubRegion ? t('common.view_details') : ''">
            <Icon name="fa6-solid:money-bill-wave" :class="contract.debt_amount > 0 ? 'text-red-500' : 'text-slate-400'" />
            <span class="text-sm font-medium" :class="contract.debt_amount > 0 ? 'text-red-700' : 'text-slate-500'">
                {{ t('common.debt') }}: {{ formatMoneyWithCurrency(contract.debt_amount) }}
            </span>
            <Icon v-if="showDebtDetail && !isSubRegion" name="fa6-solid:chevron-right"
                class="text-[10px] ml-1 group-hover:translate-x-0.5 transition-transform"
                :class="contract.debt_amount > 0 ? 'text-red-400' : 'text-slate-400'" />
        </component>
        <div v-if="showExtra && contract.total_in_commitment_deposits && parseFloat(contract.total_in_commitment_deposits) > 0" class="flex items-center gap-2 rounded px-2 py-1 border border-slate-300 truncate">
            <Icon name="fa6-solid:wallet" class="text-slate-400" />
            <span class="text-slate-500 text-sm">
                {{ t('contract_block.debt_in_commit') }}: {{
                    formatMoneyWithCurrency(contract.total_in_commitment_deposits) }}
            </span>
        </div>
        <div class="flex items-center gap-2 rounded px-2 py-1 border border-slate-300 truncate">
            <Icon name="fa6-solid:users" class="text-slate-400" />
            <span class="text-slate-500 text-sm">
                {{ t('contract_block.total_persons') }}: {{ contract.total_persons }}
            </span>
        </div>
    </div>
</template>
