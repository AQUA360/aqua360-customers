<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  invoice_id: {
    type: Number,
    default: null
  },
  by_company: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const { $InvoiceApiService } = useNuxtApp();

const data = ref([]);
const SubRegion = ref(props.isSubRegion);
const loading = ref(false);

// Agrupa una llista d'items primer per Producte i, dins de cada producte, per Tarifa + Concepte.
const groupByProductAndLineItem = (items) => {
  const groupedByProduct = items.reduce((acc, item) => {
    const productKey = item.product_name ?? '-';
    if (!acc[productKey]) {
      acc[productKey] = {
        product_name: item.product_name,
        line_items: {}
      };
    }

    const lineItemId = item.line_item_type?.id;
    const rateKey = `${item.price_rate_name ?? ''}__${lineItemId ?? ''}`;
    if (!acc[productKey].line_items[rateKey]) {
      acc[productKey].line_items[rateKey] = {
        line_item_type: item.line_item_type,
        price_rate_name: item.price_rate_name,
        complete_name: `${item.price_rate_name ?? ''} ${item.line_item_type?.name ?? ''}`,
        items: []
      };
    }
    acc[productKey].line_items[rateKey].items.push(item);
    return acc;
  }, {});

  return groupedByProduct;
}

const getData = async () => {
  loading.value = true
  try {
    const response = await $InvoiceApiService.getInvoiceLineItems(props.invoice_id);
    data.value = []
    //sort results by payment_date
    //data.value = response.results.sort((a, b) => a.payment_date - b.payment_date);
    if (props.by_company) {
      const groupedByCompany = response.results.reduce((acc, item) => {
        if(!item.company){
          if(!acc['null']){
            acc['null'] = {
              company: null,
              items: []
            };
          }
          acc['null'].items.push(item);
          return acc;
        }
        const companyId = item.company.id;
        if (!acc[companyId]) {
          acc[companyId] = {
            company: item.company,
            items: []
          };
        }
        acc[companyId].items.push(item);
        return acc;
      }, {});

      data.value = Object.keys(groupedByCompany).reduce((acc, companyId) => {
        const companyData = groupedByCompany[companyId];
        acc[companyId] = {
          company: companyData.company,
          products: groupByProductAndLineItem(companyData.items)
        };
        return acc;
      }, {});
    } else {
      data.value = groupByProductAndLineItem(response.results);
    }
  } catch (error) {
    console.log(error)
  } finally {
    loading.value = false
  }
}

const emit = defineEmits(['show-detail']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const sliceString = (str, maxLength = 15) => {
  if (!str) return '';
  if (str.length > maxLength) {
    return str.slice(0, maxLength) + '...';
  } else {
    return str;
  }
}

// Aplana tots els items de tots els productes/tarifes d'un grup de company (products) en un únic array.
const flattenItems = (products) => {
  const items = [];
  for (var productKey in products) {
    for (var rateKey in products[productKey].line_items) {
      items.push(...products[productKey].line_items[rateKey].items);
    }
  }
  return items;
}

const getUntaxedTotal = (elements) => {
  return flattenItems(elements.products).reduce((acc, item) => {
    return acc + parseFloat(item.price);
  }, 0);
}

const getTotal = (elements) => {
  return flattenItems(elements.products).reduce((acc, item) => {
    return acc + parseFloat(item.total);
  }, 0);
}
const getTaxes = (elements) => {
  let taxes = {};

  for (const lineItem of flattenItems(elements.products)) {
    const taxPercent = lineItem.tax_percent;
    const totalPrice = parseFloat(lineItem.total);
    if (taxPercent == 0) {
      continue;
    }
    if (!taxes[taxPercent]) {
      taxes[taxPercent] = 0;
    }

    taxes[taxPercent] += totalPrice;
  }

  return taxes
}



getData();

</script>

<template>
  <div v-if="loading">
    <div class="flex justify-center items-center mt-5">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
  <div v-else>
    <div v-if="data.length == 0" class="">
      <span class="footering text-slate-500 p-2">
        {{ t('common.no_records') }}
      </span>
    </div>
    <div v-else>
      <div v-if="!by_company">
        <div v-for="(product_data, product_key) in data" :key="product_key" class="mb-6">
          <div class="px-2 py-1 mb-1 bg-slate-700 text-white font-bold text-sm rounded-t">
            {{ product_data.product_name ?? '-' }}
          </div>
          <div v-for="(line_data, rate_key) in product_data.line_items" :key="rate_key" class="mb-3">
            <div
              class="heading grid grid-cols-[1fr,80px,80px,80px,80px,80px] bg-slate-100 gap-3 text-base border-b items-center">
              <span class="p-2 font-bold">{{ line_data.complete_name }}</span>
              <span class="p-2 text-sm font-semibold">{{ t('common.units_short') }}</span>
              <span class="p-2 text-sm font-semibold">{{ t('billing_block.price_unit_short') }}</span>
              <span class="p-2 text-sm font-semibold">{{ t('billing_block.subtotal') }}</span>
              <span class="p-2 text-sm font-semibold">{{ t('taxes') }}</span>
              <span class="p-2 text-sm font-semibold">{{ t('common.total') }}</span>
            </div>
            <div>
              <div v-for="(element, index) in line_data.items" :key="element.id" class="border-b">
                <div class="grid grid-cols-[1fr,80px,80px,80px,80px,80px] gap-3 text-base border-b items-center">
                  <span class="p-2">
                    <button v-if="!isSubRegion" class="text-start text-sm italic text-sky-500 underline"
                      @click="showDetail('LineItemTypeRegion', element.line_item_type?.id)">
                      <!-- {{ element.name }}<br /> -->
                      {{ element.description ? element.description : element.name }}
                    </button>
                    <span class="text-sm italic" v-else>{{ sliceString(element.line_item_type?.name) }}</span>
                  </span>
                  <span class="p-2">
                    {{ parseInt(element.units) }}
                  </span>
                  <span class="p-2">
                    {{ element.price_unit?.toFixed(4)?? '0.00' }}
                  </span>
                  <span class="p-2">
                    {{ formatMoneyWithCurrency(element.price) }}
                  </span>
                  <span class="p-2">
                    {{ element.tax_percent }}%
                  </span>
                  <span class="p-2">
                    {{ formatMoneyWithCurrency(element.total) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else>
        <div v-for="comp_data in data" class="mb-5">
          <details id="setup__box" class="mb-3 px-2 py-2">
            <summary class="px-3 font-semibold bg-white shadow">{{ comp_data.company? comp_data.company.alias : '-' }}</summary>

            <div v-for="(product_data, product_key) in comp_data.products" :key="product_key" class="mb-6 px-5">
              <div class="px-2 py-1 mb-1 bg-slate-700 text-white font-bold text-sm rounded-t">
                {{ product_data.product_name ?? '-' }}
              </div>
              <div v-for="(line_data, rate_key) in product_data.line_items" :key="rate_key" class="mb-3">
                <div
                  class="heading grid grid-cols-[1fr,80px,80px,80px,80px,80px] bg-slate-100 gap-3 text-base border-b items-center">
                  <span class="p-2 font-bold">{{ line_data.complete_name }}</span>
                  <span class="p-2 text-sm font-semibold">{{ t('common.units_short') }}</span>
                  <span class="p-2 text-sm font-semibold">{{ t('billing_block.price_unit_short') }}</span>
                  <span class="p-2 text-sm font-semibold">{{ t('billing_block.subtotal') }}</span>
                  <span class="p-2 text-sm font-semibold">{{ t('taxes') }}</span>
                  <span class="p-2 text-sm font-semibold">{{ t('common.total') }}</span>
                </div>
                <div>
                  <div v-for="(element, index) in line_data.items" :key="element.id" class="border-b">
                    <div class="grid grid-cols-[1fr,80px,80px,80px,80px,80px] gap-3 text-base border-b items-center">
                      <span class="p-2">
                        <button v-if="!isSubRegion" class="text-start text-sm italic text-sky-500 underline"
                          @click="showDetail('LineItemTypeRegion', element.line_item_type.id)">
                          {{ element.name }}<br />
                          {{ element.description }}
                        </button>
                        <span class="text-sm italic" v-else>{{ sliceString(element.line_item_type?.name) }}</span>
                      </span>
                      <span class="p-2">
                        {{ element.units }}
                      </span>
                      <span class="p-2">
                        {{ element.price_unit?.toFixed(4) ?? '0.00' }}
                      </span>
                      <span class="p-2">
                        {{ formatMoneyWithCurrency(element.price) }}
                      </span>
                      <span class="p-2">
                        {{ element.tax_percent }}%
                      </span>
                      <span class="p-2">
                        {{ formatMoneyWithCurrency(element.total) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </details>

          <div class="w-[40%] px-3 py-2 rounded-lg">
              <div class="space-y-1">
                <p class="flex justify-between text-gray-700">
                  <span>{{ t('billing_block.taxable_base') }}:</span>
                  <span class="font-medium">{{ formatMoneyWithCurrency(getUntaxedTotal(comp_data)) }}</span>
                </p>
                <div v-for="tax_value, percent in getTaxes(comp_data)" :key="percent"
                  class="flex justify-between text-gray-700">
                  <span>{{ t('common.iva') }} ({{ percent }}%):</span>
                  <span class="font-medium">{{ formatMoneyWithCurrency(tax_value) }}</span>
                </div>
                <hr class="border-t border-gray-300 my-2" />
                <p class="flex justify-between text-sky-900 font-semibold text-[14px]">
                  <span>{{ t('common.total') }}:</span>
                  <span>{{ formatMoneyWithCurrency(getTotal(comp_data)) }}</span>
                </p>
              </div>
            </div>

        </div>
      </div>
    </div>
  </div>

</template>