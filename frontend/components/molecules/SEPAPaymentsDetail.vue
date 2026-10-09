<script setup>
import { ref, onMounted, watch } from 'vue';
import { useNuxtApp } from '#app';
import PaymentDetail from '../molecules/PaymentDetail.vue';

const props = defineProps({
    paymentIds: Array,
});

const paymentIds = ref(props.paymentIds || []);
const paymentDetails = ref({}); // Store payment details

const { $PaymentApiService } = useNuxtApp();

const getDetailData = async function (id) {
    try {
        const data = await $PaymentApiService.getDetail(id);
        paymentDetails.value[id] = data;
    } catch (error) {
        console.error("Error fetching payment details:", error);
    }
};

watch(paymentIds, async (newValue) => {
    for (const item of newValue) {
        for (const id of item.payment_ids) {
            if (!paymentDetails.value[id]) {
                await getDetailData(id);
            }
        }
    }
}, { immediate: true });

</script>


<template>
    <div id="wrapper" class="text-base">
        <div v-for="item in paymentIds" :key="item.index" class="my-2 ">
            <details>
                <summary
                    class="text-sm border-b p-2 bg-sky-50 rounded-lg text-slate-500 hover:bg-slate-200 active:bg-slate-300 cursor-pointer">
                    {{ item.index }}</summary>
                <div v-for="id in item.payment_ids" :key="id"
                    class="m-2 p-3 border customers-shadow rounded-lg border-slate-200 bg-white">
                    <PaymentDetail :data="paymentDetails[id]" :isSubRegion="true" v-if="paymentDetails[id]" />
                </div>
                <div class="h-[1px]"></div>
            </details>
        </div>
    </div>
</template>

<style scoped>
.selected {
    margin-left: 15px
}
</style>