<script setup>
import H1Region from '../atoms/H1Region.vue';
import InvoiceViewEdit from '../organisms/InvoiceViewEdit.vue';
import InvoiceView from '../organisms/InvoiceView.vue';
import { useToast } from 'vue-toastification';

const { $InvoiceApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const props = defineProps({
    id: Number,
    object_id: Number,
    service: Object,
    entity: String,
    invoice_id: Number,
    is_budget: Boolean,
    payment_data: Object,
    redo_budget: Boolean,
    redo_option: Object,
    is_connection: {
        type: Boolean,
        default: false
    },
    selected_custom: Object,
    isSubRegion: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['changed', 'disable-redo']);

const pending = ref(true);
const error = ref(null);

const object = ref(null)
const invoice = ref(null)

const invoiceTypeToken = ref(null)
const pendingToken = ref(null)

const getData = async () => {
    try {
        console.log(props.invoice_id)
        console.log(props.id)
        //Obtain the object from the service
        if (props.id) {
            const result = await props.service.getDetail(props.id);
            object.value = result;
        }

        if (props.invoice_id) {
            if (props.redo_budget) {
                let invoice_generation = {
                    entity: props.entity,
                    object_id: props.id,
                    is_budget: props.is_budget,
                    redo_budget: props.invoice_id,
                    payment_data: props.payment_data,
                    redo_option: props.redo_option,
                    selected_custom: props.selected_custom
                }

                let response = await $InvoiceApiService.generateInvoiceBudget(invoice_generation);
                console.log(response)
                if (response) {
                    toast.success(props.is_budget? (t('informative_block.info_budget_correct_gen')) : (t('informative_block.info_invoice_correct_gen')))
                    invoice.value = response.invoice
                    emit('disable-redo', response.invoice)
                }
            } else {
                //Obtain the invoice if it exists
                const invoice_result = await $InvoiceApiService.getDetail(props.invoice_id);
                invoice.value = invoice_result;
            }
        } else {
            let invoice_generation = {
                entity: props.entity,
                object_id: props.object_id,
                is_budget: props.is_budget,
                payment_data: props.payment_data,
                redo_option: props.redo_option,
                selected_custom: props.selected_custom
            }

            let response = await $InvoiceApiService.generateInvoiceBudget(invoice_generation);
            console.log(response)
            if (response) {
                toast.success(props.is_budget? (t('informative_block.info_budget_correct_gen')) : (t('informative_block.info_invoice_correct_gen')))
                invoice.value = response.invoice
                await nextTick()
                emit('changed', false, response.invoice)
            }
        }
    } catch (err) {
        error.value = err;
        console.error(err);
    } finally {
        pending.value = false;
    }
    console.log(invoice.value)
}

const handleChanged = async (close, newInvoice = null) => {
    if (newInvoice && newInvoice.id !== invoice.value?.id) {
        invoice.value = newInvoice;
    } else {
        const invoice_result = await $InvoiceApiService.getDetail(invoice.value.id);
        invoice.value = invoice_result;
    }
    emit('changed', close, invoice.value);
}

onMounted(async () => {
    invoiceTypeToken.value = await $ConfigProjectApiService.get('invoice_type_invoice_token');
    pendingToken.value = await $ConfigProjectApiService.get('invoice_status_pending_token');
    
    getData()
})


</script>

<template>

    <div class="region__content pr-2 relative" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
        <div v-if="pending">
            <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
            <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
                    }}</button></p>
        </div>
        <div v-else class="pb-24">
            <!-- <H1Region> {{ t('Generació de pressupost') }} </H1Region> -->
            <div v-if="invoice">
                
                <div v-if="(!is_budget && invoiceTypeToken != invoice.type_final) || (invoice?.status?.token && invoice?.status?.token != pendingToken) || (invoice?.status_token && invoice?.status_token != pendingToken)">
                    <InvoiceView :id="invoice.id" :isSubRegion="props.isSubRegion" />
                </div>
                
                <div v-else class="relative">
                    <InvoiceViewEdit :is_connection="is_connection" :id="invoice.id" @changed="handleChanged" :allowLineItemTypeManual="true" :isSubRegion="props.isSubRegion" />
                </div>
            </div>
        </div>
    </div>

</template>