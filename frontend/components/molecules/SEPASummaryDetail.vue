<script setup>
import { ca, da, is } from 'date-fns/locale';
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import { hideIban, formatIban } from '~/utils/iban';
import FieldDetail from '../atoms/FieldDetail.vue';
import SEPAPaymentsDetail from './SEPAPaymentsDetail.vue';


const { t } = useI18n();
const toast = useToast();

const props = defineProps({
    paymentLines: Object,
    totalAnomalies: Number,
});

const paymentLines = ref(props.paymentLines ? props.paymentLines : null);
const selectedPaymentsDel = ref([]);
const filteredPaymentLines = ref(paymentLines.value);

const isDeleting = ref(false);
const filterAnomalies = ref(false);
const totalAnomalies = ref(props.totalAnomalies ? props.totalAnomalies : 0);

const emit = defineEmits(['show-detail', 'remove-payment']);

const searchInput = ref('');

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const toggleRegion = (force) => {
    showRegion.value = force !== undefined ? force : !showRegion.value;
    if (showRegion.value == false) {
        isSubRegionOpen.value = false;
    }
}

const showDetail = function () {
    if (selectedPaymentsDel.value?.detail_data?.length > 0) {
        showRegion.value = true;
        toggleRegion(true)
    } else {
        toast.warning(t("warning_block.warning_sepa_no_payments"), {
            position: 'bottom-right',
            timeout: 1500,
            autoClose: false,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: false,
            icon: false,
            rtl: false,
            draggable: true,
            progress: undefined,
            theme: 'light',
        });
    }
}


const removePayment = function () {
    if (selectedPaymentsDel.value?.payment_ids?.length > 0) {
        if (confirm(t("confirmation_text_block.confirm_exclude_payments"))) {
            const paymentsToRemove = selectedPaymentsDel.value.payment_ids.flatMap(payment => payment);
            filterAnomalies.value = false;
            emit('remove-payment', paymentsToRemove)
        }
        toggleDeleting()
    } else {
        toast.warning(t("warning_block.warning_sepa_no_payments"), {
            position: 'bottom-right',
            timeout: 1500,
            autoClose: false,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: false,
            icon: false,
            rtl: false,
            draggable: true,
            progress: undefined,
            theme: 'light',
        });
    }
}

const paymentClicked = function (item, index) {

    if (!selectedPaymentsDel.value.indexes) {
        selectedPaymentsDel.value.indexes = [];
    }
    if (!selectedPaymentsDel.value.payment_ids) {
        selectedPaymentsDel.value.payment_ids = [];
    }
    if (!selectedPaymentsDel.value.detail_data) {
        selectedPaymentsDel.value.detail_data = [];
    }

    const indexExists = selectedPaymentsDel.value.indexes.includes(index);

    if (indexExists) {
        const idx = selectedPaymentsDel.value.indexes.indexOf(index);
        if (idx > -1) {
            selectedPaymentsDel.value.indexes.splice(idx, 1);
            selectedPaymentsDel.value.payment_ids.splice(idx, 1);
            selectedPaymentsDel.value.detail_data.splice(idx, 1);
        }
    } else {
        selectedPaymentsDel.value.indexes.push(index);
        selectedPaymentsDel.value.payment_ids.push(item.payment_ids);
        selectedPaymentsDel.value.detail_data.push({ 'index': index, 'payment_ids': item.payment_ids });
    }
};


const toggleDeleting = () => {
    isDeleting.value = !isDeleting.value;
    if (isDeleting.value) {
        toast.info(t("informative_block.info_start_selecting_payments"), {
            position: 'bottom-right',
            timeout: 1500,
            autoClose: false,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: false,
            icon: false,
            rtl: false,
            draggable: true,
            progress: undefined,
            theme: 'light',
        });

    } else {
        selectedPaymentsDel.value = [];
    }
}

/* const handleSearch = () => {
    console.log(searchInput.value);
    if (!searchInput.value) {
        filteredPaymentLines.value = paymentLines.value;
    } else {
        filteredPaymentLines.value = Object.entries(paymentLines.value).map((data) => {
            return data.filter((item_data, index_data) => {
                return Object.entries(item_data).filter((item, index) => {
                    console.log(item)
                    console.log(index)
                    const searchTerm = searchInput.value.toLowerCase();
                    const iban = item.iban ? item.iban.toLowerCase() : '';
                    const itemIndex = index.toString();

                    return (
                        iban.includes(searchTerm) ||
                        itemIndex.includes(searchTerm)
                    );
                });
            });
        });

    }
}; */

onMounted(async () => {
    
})

watch(() => props.paymentLines, (newValue) => {
    searchInput.value = '';
    paymentLines.value = newValue;
    filteredPaymentLines.value = newValue;
}, { immediate: true });


</script>

<template>
    <div id="wrapper" class="text-base">
        <div>
            <!-- <div class="flex items-center my-2">
                <div class=" mx-1 grid grid-cols-[20px,1fr] flex items-center">
                    <Icon name="fa6-solid:magnifying-glass" class="text-slate-500 text-sm" />
                    <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
                        :placeholder="$t('Cerca DNI o IBAN')"
                        class="w-full px-1 rounded-md border-b border-salte-100 focus:outline-none "
                        autocomplete="off" />
                </div>
            </div> -->
            <div class="flex justify-between items-center">
                <div class="flex gap-2 py-2">

                    <button @click="filterAnomalies = !filterAnomalies"
                        class="px-2 mx-2 text-sm font-medium  border border-transparent rounded-3xl  transition duration-200 ease-in-out"
                        :class="filterAnomalies ? 'border border-sky-500 bg-sky-50 hover:bg-sky-400 hover:text-white text-sky-600 rounded-3xl font-semibold ring-1 ring-sky-400' : 'text-slate-400 hover:bg-slate-200 hover:border hover:border-slate-200'">
                        {{ $t('common.anomalies') }}
                    </button>

                </div>

                <div class="flex gap-2 py-2 items-center">

                    <div>
                        <button
                            class="px-2 mx-2 text-sm font-medium border border-transparent rounded-3xl transition duration-200 ease-in-out text-slate-400 hover:bg-slate-200 hover:border hover:border-slate-200"
                            @click="toggleDeleting">
                            {{ isDeleting ? t('common.cancel') : `${t('common.select')} ${t('billing_block.payments')}`}}
                        </button>
                    </div>

                </div>

            </div>
            <div v-if="isDeleting" class="flex justify-end pb-5 border-t pt-2">
                <button
                    class="px-2 mx-2 text-sm font-medium border border-transparent rounded-3xl transition duration-200 ease-in-out border border-orange-500 bg-yellow-50 hover:bg-yellow-400 hover:text-white text-orange-600 rounded-3xl font-semibold ring-1 ring-orange-400"
                    @click="showDetail()">
                    {{ t('common.show') }} {{ t('billing_block.payments') }}
                </button>
                <button
                    class="px-2 mx-2 text-sm font-medium border border-transparent rounded-3xl transition duration-200 ease-in-out border border-red-500 bg-red-50 hover:bg-red-400 hover:text-white text-red-600 rounded-3xl font-semibold ring-1 ring-red-400"
                    @click="removePayment">
                    {{ t('billing_block.exclude') }} {{ t('billing_block.payments') }}
                </button>
            </div>

            <fieldset class="mb-5 mt-2 bg-sky-50 p-2 rounded-lg  text-sm">
                <div v-for="(data, id) in filteredPaymentLines" :key="id" class="space-y-1">
                    <div v-for="(item, index) in data" :key="index" @click="isDeleting && paymentClicked(item, index)">
                        <div v-if="!(!item.is_anomaly && filterAnomalies)"
                            class="relative group bg-white px-4 pt-3 rounded-lg mt-1  border-2" :class="{
                                'border-red-300': item.is_anomaly && !isDeleting,
                                'bg-yellow-50': selectedPaymentsDel?.some((entry) =>
                                    entry.payment_ids?.includes(item.id)
                                ),
                            }">
                            <div :class="{ 'grid grid-cols-[25px,1fr]': isDeleting }">
                                <span v-if="isDeleting" class="flex items-center pb-3">
                                    <Icon name="fa6-solid:angle-right"
                                        :class="{ 'selected': selectedPaymentsDel?.indexes?.includes(index) }" />
                                </span>
                                <div>
                                    <legend v-if="item.is_anomaly"
                                        class="absolute cursor-pointer text-sm w-8 h-8 right-12 top-5 rounded-md">
                                        <Icon name="fa6-solid:circle-exclamation" class="text-red-500" />
                                    </legend>
                                    <div class="grid grid-cols-2 gap-4"
                                        :class="{ 'selected': selectedPaymentsDel?.indexes?.includes(index) }">
                                        <span>
                                            {{ index + ' - ' + item.tax_name }}
                                        </span>
                                        <span>{{ item.address }}</span>
                                    </div>
                                    <div class="grid grid-cols-2 gap-4"
                                        :class="{ 'selected': selectedPaymentsDel?.indexes?.includes(index) }">
                                        <span>
                                            {{ formatIban(item.iban) }}
                                        </span>
                                        <span>
                                            {{ item.swift ? item.swift : '-' }}
                                        </span>
                                    </div>
                                    <div :class="{ 'selected': selectedPaymentsDel?.indexes?.includes(index) }">
                                        <FieldDetail :label="t('common.total')"
                                            :value="formatMoneyWithCurrency(item.amount)" />
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>
                </div>
                <div v-if="filterAnomalies && totalAnomalies == 0"
                    class="mt-4 text-gray-700 text-center bg-sky-50 pb-4 px-4 rounded-lg">
                    {{ t('common.no_data_found') }}
                </div>
            </fieldset>
        </div>
        <div v-if="showRegion" role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[95%] overflow-y-auto overflow-x-hidden"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="toggleRegion(false)"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <SEPAPaymentsDetail :paymentIds="selectedPaymentsDel.detail_data" />
            </div>
        </div>
    </div>
</template>
<style scoped>
.selected {
    margin-left: 15px
}
</style>