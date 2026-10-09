<script setup>
import { toRaw, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import _ from 'lodash';
import InvoiceMiniDetail from './InvoiceMiniDetail.vue';

const props = defineProps({
    data: Object,
});

const { $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const emit = defineEmits(['remove', 'show-detail']);
const localData = ref(null);
const selected_data = ref([]);
const showing_item_id = ref(null);
const debt_vulnerable_token = ref(null);

const contractClaimClicked = (item) => {
    const contractId = item.id;
    const contractToken = item.token;

    const existingIndex = selected_data.value.findIndex(
        (selected) => selected.contract_id === contractId
    );

    if (existingIndex > -1) {
        selected_data.value.splice(existingIndex, 1);
    } else {
        selected_data.value.push({
            contract_id: contractId,
            token: contractToken,
        });
    }
};

const removeContractsFromManagement = () => {
    if (!confirm(t('confirmation_text_block.confirm_exclude_contract'))) return;
    emit('remove', selected_data.value);
};

const checkItem = (entity, item) => {
    emit('show-detail', entity, item);
};

const checkInvoices = (id) => {
    if (showing_item_id.value == id) {
        showing_item_id.value = null;
    } else {
        showing_item_id.value = id;
    }
};

onMounted( async () => {
    debt_vulnerable_token.value = await $ConfigProjectApiService.get('debt_vulnerable_token');
    localData.value = props.data;
});

watch(() => props.data, (newVal) => {
    localData.value = newVal;
});

</script>

<template>
    <div v-if="localData && localData.length > 0" class="bg-white rounded-lg overflow-hidden">
        <div
            class="grid grid-cols-[150px,250px,150px,100px,1fr,50px] font-semibold bg-slate-100 py-3 px-4 border-b border-slate-200 text-slate-700">
            <span>{{ $t('contract') }}</span>
            <span>{{ $t('contract_block.current_holder') }}</span>
            <span>{{ $t('contract_block.holder_id') }}</span>
            <span>{{ $t('common.usage') }}</span>
            <span>{{ $t('contract_block.debt_management_type') }}</span>
            <span></span>
        </div>
        <div class="content">
            <div v-for="item in localData" :key="item.id"
                class="group grid grid-cols-[150px,250px,150px,100px,1fr,50px] py-2 px-4 border-b border-slate-100 hover:bg-slate-50 transition-colors duration-150 relative"
                :class="{
                    'selected': selected_data?.some((entry) => entry.contract_id === item.id),
                }" @click="contractClaimClicked(item)">
                <span>
                    <button
                        class="flex justify-between w-full items-center text-sky-500 hover:text-sky-700 font-medium focus:outline-none"
                        @click.stop="checkItem('ContractRegion', item.id)">
                        {{ item.token }}
                        <Icon name="fa6-solid:eye"
                            class="opacity-0 hover:opacity-100 text-slate-500 ml-1 transition-opacity duration-200" />
                    </button>
                </span>
                <span class="text-slate-800">{{ item.holder_name + ' ' + item.holder_surname }}</span>
                <span class="text-slate-700">{{ item.holder_token }}</span>
                <span class="text-slate-700">{{ item.use_type_name }}</span>
                <span v-if="item.debt_management_token && item.debt_management_token != debt_vulnerable_token" class="text-slate-700">
                    {{ item.debt_management_name }}
                </span>
                <span v-else-if="item.debt_management_token && item.debt_management_token == debt_vulnerable_token" class="text-slate-700"> 
                    <AtomsColorBadge :value="item.debt_management_name" :color="'purple'" />
                </span>
                <span v-else class="text-slate-700">
                    {{ $t('contract_block.no_vulnerable') }}
                </span>
                <abbr :title="`${$t('common.show')} ${$t('invoices')}`">
                    <button class="group rounded-md focus:outline-none w-full h-full" @click.stop="checkInvoices(item.id)">
                        <Icon v-show="showing_item_id != item.id" name="fa6-solid:angle-down"
                            class="text-slate-500 group-hover:text-sky-500 transition-colors duration-200" />
                        <Icon v-show="showing_item_id == item.id" name="fa6-solid:angle-up"
                            class="text-slate-500 group-hover:text-sky-500 transition-colors duration-200" />
                    </button>
                </abbr>

                <div v-if="showing_item_id == item.id" class="col-span-full mt-2" @click.stop>
                    <InvoiceMiniDetail :item="item.invoices" :is_info="true" @show-detail="checkItem"
                        class="shadow-md rounded-md overflow-hidden group-hover:bg-white" />
                </div>
            </div>
        </div>
        <div class="p-4">
            <abbr :title="selected_data.length == 0 ? t('contract_block.select_contract') : null">
                <button
                    class="bg-orange-500 hover:bg-orange-700 text-white font-bold py-2 px-4 rounded focus:outline-none disabled:opacity-50"
                    @click="removeContractsFromManagement()" :disabled="selected_data.length == 0">
                    {{ t('billing_block.exclude') }}
                </button>
            </abbr>
        </div>
    </div>
    <div v-if="localData && localData.length == 0"
        class="flex flex-col items-center justify-center p-8 bg-slate-50 rounded-lg shadow-md">
        <Icon name="fa6-solid:circle-exclamation" class="text-slate-400 text-5xl mb-4" />
        <span class="text-slate-700 font-semibold text-lg">{{ $t('common.no_records') }}</span>
        <p class="text-slate-500 text-sm mt-2 text-center">
            {{ $t('common.no_data_found') }}
        </p>
        <p class="text-slate-500 text-sm mt-1 text-center">{{ $t('contract_block.check_filters') }}</p>
    </div>
</template>


<style scoped>
.content {
    max-height: 60vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 0;
}


.selected {
    margin-left: 15px;
    background-color: rgb(232, 244, 255);
    border: 1px solid #e5e7eb;
}
</style>
