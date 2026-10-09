<script setup>
import { ca } from 'date-fns/locale';
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import { hideIban, formatIban } from '~/utils/iban';
import FieldDetail from '../atoms/FieldDetail.vue';
import SEPAPaymentsList from './SEPAPaymentsList.vue';
import SEPASummaryDetail from '../molecules/SEPASummaryDetail.vue';


const { t } = useI18n();
const route = useRoute()
const router = useRouter();
const toast = useToast();
const { $PaymentApiService, $ProductApiService } = useNuxtApp();

const props = defineProps({
    selectedPayments: Object,
    loadedPayments: Object,
    selectedPaymentsDel: Object,
    anomalies: Object,
});

const pending = ref(true);
const error = ref(null);
const items = ref([]);

const anomalies = ref([]);
const payments = ref(props.loadedPayments ? props.loadedPayments : []);

const totalAmount = ref(null)
const selectedPayments = ref(props.selectedPayments ? props.selectedPayments : []);
const selectedPaymentsDel = ref(props.selectedPaymentsDel ? props.selectedPaymentsDel : []);

const emit = defineEmits(['changed']);


const getData = async () => {
    pending.value = true;
    error.value = null;
    try {
        if (props.anomalies && props.anomalies.length > 0) {
            let payments_anomalies = payments.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: false }));
            let deleted_anomalies = selectedPaymentsDel.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: true }));;
            const uniqueAnomalies = [...payments_anomalies, ...deleted_anomalies].filter((payment, index, self) =>
                index === self.findIndex((p) => p.id === payment.id)
            );
            anomalies.value = uniqueAnomalies;
        }
        getAllAmounts()
    } catch (err) {
        error.value = err;
    } finally {
        pending.value = false;
    }
}

const getAllAmounts = () => {
    let total = 0;
    for (let payment in payments.value) {
        total += payment.amount;
    }
    totalAmount.value = total;
}

const removePayment = function (payment, action) {
    if (!action) {
        payment.is_excluded = true;
        selectedPaymentsDel.value.push(payment);
        selectedPayments.value = selectedPayments.value.filter(item => payment.id !== item);
        payments.value = payments.value.filter(item => payment.id !== item.id);
    }
    else {
        payment.is_excluded = false;
        selectedPaymentsDel.value = selectedPaymentsDel.value.filter(item => payment.id !== item.id);
        selectedPayments.value.push(payment.id);
        payments.value.push(payment);
    }
    emit('changed', selectedPayments.value, selectedPaymentsDel.value);
}


onMounted(() => {
    getData();
});


watch(() => props.selectedPayments, (newValue) => {
    if (newValue) {
        selectedPayments.value = newValue;
    } else {
        selectedPayments.value = [];
    }
}, { immediate: true });

watch(() => props.loadedPayments, (newValue) => {
    payments.value = newValue;
    if (props.anomalies && props.anomalies.length > 0) {
        let payments_anomalies = payments.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: false }));
        let deleted_anomalies = selectedPaymentsDel.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: true }));;
        const uniqueAnomalies = [...payments_anomalies, ...deleted_anomalies].filter((payment, index, self) =>
            index === self.findIndex((p) => p.id === payment.id)
        );
        anomalies.value = uniqueAnomalies;
    }
}, { immediate: true });

watch(() => props.selectedPaymentsDel, (newValue) => {
    selectedPaymentsDel.value = newValue;
}, { immediate: true });

watch(() => props.anomalies, (newValue) => {
    if (newValue && newValue.length > 0) {
        let payments_anomalies = payments.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: false }));
        let deleted_anomalies = selectedPaymentsDel.value.filter(payment => props.anomalies.includes(payment.id)).map(payment => ({ ...payment, is_excluded: true }));;
        const uniqueAnomalies = [...payments_anomalies, ...deleted_anomalies].filter((payment, index, self) =>
            index === self.findIndex((p) => p.id === payment.id)
        );
        anomalies.value = uniqueAnomalies;
    }
}, { immediate: true });


const showRegion = ref(false);

const toggleRegion = (force) => {
    showRegion.value = force !== undefined ? force : !showRegion.value;
    if (showRegion.value == false) {
        isSubRegionOpen.value = false;
        selectedItem.value = null;
    }
}

const selectedItem = ref(null);
const showDetail = (item) => {
    selectedItem.value = item;
    toggleRegion(true);
}

const isSubRegionOpen = ref(false);



</script>

<template>
    <div id="wrapper" class="text-base p-6">
        <h2 class="text-2xl font-bold mb-6 text-gray-800">{{ $t('common.summary') }} {{ $t('common.and') }} {{ $t('common.anomalies') }}</h2>

        <div class="m-2 rounded-lg border border-slate-300  max-w-xl py-2">
            <div class="group rounded-lg relative p-2 flex items-center justify-between">
                <div class=" text-slate-600 font-semibold px-2">
                    {{ t('billing_block.selected_payments') }}:
                </div>
                <span class="inline-flex items-center bg-green-300 text-slate-700  rounded-full px-2 py-1 ml-2 mr-5">
                    {{ selectedPayments.length }}</span>
                <button
                    class="w-10 opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                    @click="showDetail('payments')">
                    <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </button>
            </div>
            <div class="group rounded-lg relative p-2 flex items-center justify-between">
                <div class=" text-slate-600 font-semibold px-2">
                    {{ t('billing_block.excluded_payments') }}
                </div>
                <span class="inline-flex items-center bg-orange-300 text-slate-700  rounded-full px-2 py-1 ml-2 mr-5">
                    {{ selectedPaymentsDel.length }}</span>
                <button
                    class="w-10 opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                    @click="showDetail('excluded')">
                    <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </button>
            </div>
            <div class="group rounded-lg relative p-2 flex items-center justify-between">
                <div class=" text-slate-600 font-semibold px-2">
                    {{ t('common.anomalies') }}:
                </div>
                <span class="inline-flex items-center bg-orange-300 text-slate-700  rounded-full px-2 py-1 ml-2 mr-5">
                    {{ anomalies ? Object.entries(anomalies).length : 0 }}</span>
                <button
                    class="w-10 opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                    @click="showDetail('anomalies')">
                    <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </button>
            </div>
        </div>

        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all z-10 duration-500 ease py-4 bg-white w-[90%]"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
            <div id="region_nav" class="mb-3 px-4">
                <button @click="toggleRegion(false)"
                    class="px-3 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <SEPAPaymentsList v-if="selectedItem == 'payments'" :payments="payments" @change="removePayment" @exclude_change="removePayment($event, !$event.is_excluded)" />
                <SEPAPaymentsList v-if="selectedItem == 'excluded'" :payments="selectedPaymentsDel" :is_excluded="true"
                    @change="removePayment" @exclude_change="removePayment($event, !$event.is_excluded)" />
                <SEPAPaymentsList v-if="selectedItem == 'anomalies'" :payments="anomalies" @change="removePayment"
                    :is_anomaly="true" @exclude_change="removePayment($event, !$event.is_excluded)" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.selected {
    margin-left: 15px;
}
</style>
