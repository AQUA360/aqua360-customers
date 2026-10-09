<script setup>

const { t } = useI18n();

const { $ConfiglistApiService, $ConfigProjectApiService, $PriceRateApiService, $LineItemTypeApiService, $InvoiceApiService, $ProductApiService } = useNuxtApp()

const emit = defineEmits(['handleNewItem',]);
const props = defineProps({
    id: {
        type: Number,
        default: null
    },
    is_connection: {
        type: Boolean,
        default: false
    }
});

const loading = ref(true);
const loading_price_rates = ref(false);
const loading_line_items = ref(false);
const error = ref(null);

const selectedProduct = ref(null)
const selectedPriceRate = ref(null)
const selectedLineItem = ref(null)
const new_line_name = ref('')
const products = ref([])
const priceRates = ref([])
const lineItems = ref([])

const origin_reading_token = ref(null)
const origin_connection_token = ref(null)
const origin_contract_token = ref(null)
const origin_supply_point_token = ref(null)

const getData = async () => {
    loading.value = true;
    try {
        origin_reading_token.value = await $ConfigProjectApiService.get('origin_reading_token');
        origin_connection_token.value = await $ConfigProjectApiService.get('origin_connection_token');
        origin_contract_token.value = await $ConfigProjectApiService.get('origin_contract_token');
        origin_supply_point_token.value = await $ConfigProjectApiService.get('origin_supply_token');
    } catch (err) {
        console.error(err);
        error.value = err;
    } finally {
        loading.value = false;
    }
}

const getProducts = async (page = 1, search = '') => {
    
    const response = await $ProductApiService.getAll(search, [], page, null, false, null);
    products.value = []
    
    response.results.forEach(item => {
        products.value.push({
            label: `${item.name} (${item.exploitation.name})`,
            value: item.id
        })
    });
    
    let result = {
        items: products.value,
        hasNextPage: response && response.next ? true : false
    }
    return result;
}

const getPriceRates = async () => {
    loading_price_rates.value = true
    priceRates.value = []
    try {
        const result = await $PriceRateApiService.getAll('', [], 1, null, false, selectedProduct.value.value);
        result.results.forEach(item => {
            priceRates.value.push({
                label: item.name,
                code: item.id,
                br_id: item?.billing_range_active?.id || null
            })
        })
    } catch (err) {
        console.error(err);
        error.value = err;
    } finally {
        loading_price_rates.value = false;
    }
}

const getLineItemTypes = async () => {
    loading_line_items.value = true;
    lineItems.value = []
    try {
        const result = await $LineItemTypeApiService.getAll('', [], 1, null, false, selectedPriceRate.value.br_id);
        result.results.forEach(item => {
            let name_extra = ''
            if (item.formula) {
                name_extra = `${t('pricing_block.for')}: ${item.formula.toString()}`
            } else if (item.price) {
                name_extra = `${t('pricing_block.fixed_price')}: ${item.price.toString()}`
            } else if (item.proportional_price) {
                name_extra = `${t('pricing_block.proportional_price')}: ${item.proportional_price.toString()}`
            } else if (item.price_interval) {
                name_extra = t('common.range')
            } else if (item.price_variable) {
                name_extra = t('pricing_block.variable_price')
            }

            lineItems.value.push({
                //label: `${item.name} (${name_extra})`,
                label: item.name,
                code: item.id,
            })
        })
    } catch (err) {
        console.error(err);
        error.value = err;
    } finally {
        loading_line_items.value = false;
    }
}

const updateSelect = async (event, entity) => {
    switch (entity) {
        case 'product':
            selectedProduct.value = event;
            selectedPriceRate.value = null;
            selectedLineItem.value = null;
            await getPriceRates()
            break;
        case 'price_rate':
            selectedPriceRate.value = event;
            selectedLineItem.value = null;
            await getLineItemTypes()
            break;
        case 'line_item':
            selectedLineItem.value = event;
            break;
    }
}

const handleAddLineItem = async (add_line_type = false) => {
    let new_lines = [];
    if (add_line_type) {
        try {
            let new_line_data = {
                invoice_id: props.id,
                line_item_type_id: selectedLineItem.value.code,
            }
            
            const response = await $InvoiceApiService.manageNewBudgetLine(new_line_data);
            
            new_lines = response.new_lines;
        } catch (err) {
            console.error(err);
            error.value = err;
        }
    } else {
        new_lines.push({
            name: '',
            description: '',
            units: 0,
            price_unit: 0,
            price: 0,
            tax_percent: 0,
            product_name: new_line_name.value? new_line_name.value : t('pricing_block.new_line_name'),
            manually_added: true
        })
    }

    emit('handleNewItem', new_lines)
}

onMounted(async () => {
    getData()
    getProducts(1)
})
</script>

<template>
    <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">

        <slot name="button-exit"></slot>

        <div v-if="loading" class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
            <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
        </div>

        <div v-else>
            <div class="flex flex-col space-y-4">
                <input type="text" v-model="new_line_name" class="input"
                :placeholder="t('pricing_block.new_line_name')" />
                <button class="button-primary w-full" @click="handleAddLineItem()">
                    {{ t('billing_block.add_custom_line') }}
                </button>

                <div class="border-t border-slate-300 pt-4">
                    <div class="mb-4">
                        <AtomsInfiniteScrollVueSelect :labelText="t('product')" :loadFunction="getProducts" :item="selectedProduct"
                            @update:modelValue="updateSelect($event, 'product')" />
                    </div>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-slate-700 mb-2" for="pricerate-select">
                            {{ t('price_rate') }}</label>
                        <v-select id="pricerate-select" class="block w-full required" :model-value="selectedPriceRate"
                            :options="priceRates" @update:modelValue="updateSelect($event, 'price_rate')"
                            :disabled="selectedProduct == null" :loading="loading_price_rates" />
                    </div>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-slate-700 mb-2" for="lineitemtype-select">
                            {{ t('pricing_block.line_item_detail') }}</label>
                        <v-select id="lineitemtype-select" class="block w-full required" :model-value="selectedLineItem"
                            :options="lineItems" @update:modelValue="updateSelect($event, 'line_item')"
                            :disabled="selectedProduct == null || selectedPriceRate == null"
                            :loading="loading_line_items" />
                    </div>
                    <button class="button-primary w-full" @click="handleAddLineItem(true)">
                        {{ t('common.add') }} {{ t('pricing_block.line_item_detail') }} 
                    </button>
                </div>
            </div>
        </div>

    </div>

</template>
