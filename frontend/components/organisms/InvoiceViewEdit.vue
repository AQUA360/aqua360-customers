<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import IBAN from '~/components/atoms/IBAN.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import AddNewInvoiceLine from '../molecules/AddNewInvoiceLine.vue';
import _ from 'lodash'
import AppLoading from '~/components/atoms/AppLoading.vue';
import Draggable from 'vuedraggable';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { t } = useI18n();
const { $LineItemApiService, $InvoiceApiService, $ConfigProjectApiService, $LineItemTypeApiService } = useNuxtApp()
const toast = useToast();

const props = defineProps({
  id: {
    type: Number,
    default: null
  },
  allowLineItemTypeManual: {
    type: Boolean,
    default: false
  },
  is_connection: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['changed']);

const pending = ref(true);
const loadingPdf = ref(false);
const error = ref(null);

const lineItemTypeManual = ref(null)

const showSelectLineType = ref(false)

const item = ref(null);
const invoiceTypeToken = ref(null)
const originReadingToken = ref(null)
const statusCancelledToken = ref(null)
const generatingInvoice = ref(false)

const comment = ref(null)

const isReorderable = computed(() => {
  // 1. Si l'origen és de lectures (sigui factura o pressupost), ha de ser FIXA
  if (item.value?.origin?.token === originReadingToken.value || item.value?.reading || item.value?.consumption) {
    return false;
  }

  // 2. Si és de connexió (prop o camp), sempre REORDENABLE
  if (props.is_connection || item.value?.connection_request) return true;

  // 3. Si és una factura definitiva (no pressupost) i té contracte, la fem FIXA (cas de la "personalitzada d'aigua")
  if (item.value?.type?.token === invoiceTypeToken.value && item.value?.contract) return false;

  // 4. Per a tota la resta (pressupostos manuals, factures a persones, etc.), permetem reordenar
  return true;
});

const getData = async () => {
  pending.value = true;

  const manulaLineToken = await $ConfigProjectApiService.get('manual_invoice_line');

  const lineItemTypes = await $LineItemTypeApiService.getAll(manulaLineToken, [], 1, null, false, null)
  lineItemTypeManual.value = lineItemTypes.results && lineItemTypes.results.length > 0 ? lineItemTypes.results[0] : null;

  await getInvoice()

}

const getInvoice = async () => {
  item.value = null
  $InvoiceApiService.getDetail(props.id).then((data) => {
    if (data && data.line_items) {
      data.line_items.sort((a, b) => (a.custom_order || a.product_order || 0) - (b.custom_order || b.product_order || 0));
    }
    item.value = data;
    comment.value = data.budget_comment;
    pending.value = false;
    error.value = null;
  }).catch((err) => {
    error.value = err;
    pending.value = false;
  });
}

const syncOrderToBackend = async () => {
  if (!item.value?.line_items) return;
  const promises = item.value.line_items.map((line, index) => {
    line.custom_order = (index + 1) * 10;
    if (!line.id) return Promise.resolve();

    let data = { ...line };
    data.price = Number(line.price_unit * line.units).toFixed(4);
    data.custom_order = line.custom_order;
    data.tax_price = Number(data.price * ((data.tax_percent) / 100)).toFixed(4);
    data.manually_modified = true;
    data.line_item_type = data.line_item_type ? data.line_item_type.id : null;
    data.company = data.company ? data.company.id : null;
    data.price_rate = data.price_rate ? data.price_rate.id : null;
    data.tax = data.tax ? data.tax.id : null;
    data.total = Number(Number(data.price + data.tax_price).toFixed(4));
    return $LineItemApiService.save(data);
  });
  await Promise.all(promises);
};

const onDraggableEnd = () => {
  if (!item.value?.line_items) return;
  item.value.line_items.forEach((line, index) => {
    line.custom_order = (index + 1) * 10;
  });
};

const invoicePDF = async () => {
  loadingPdf.value = true;
  try {
    await syncOrderToBackend();
  } catch (e) {
    console.error(e);
  }

  $InvoiceApiService.getTemporaryPDF(props.id).then(async (data) => {
    await openAuthenticatedFileUrl(data.url);
    loadingPdf.value = false;
  }).catch((err) => {
    error.value = err;
    loadingPdf.value = false;
  });

}
const handleChanged = (close = true, invoiceData = null) => {
  emit('changed', close, invoiceData);
}

const handleSaveLineItem = async (line, index, close = true) => {
  pending.value = true;
  try {

    let data = { ...line };
    data.price = Number(line.price_unit * line.units).toFixed(4);
    data.tax_price = Number(data.price * ((data.tax_percent) / 100)).toFixed(4);

    if (!data.id) {
      data.id = line.id;
      data.token = _.random(10000, 99999);
      data.invoice = props.id;
      data.line_item_type = lineItemTypeManual?.value?.id;
      data.manually_added = true;
      await $LineItemApiService.save(data);
    }

    await syncOrderToBackend();

    await getInvoice();
    handleChanged(close);
  } catch (err) {
    error.value = err;
    pending.value = false;
    console.error(err);
  }
};

const handleAddLine = async () => {
  if (props.allowLineItemTypeManual) {
    showSelectLineType.value = true
  } else {
    let new_line = {
      name: '',
      description: '',
      units: 0,
      price_unit: 0,
      price: 0,
      tax_percent: 0,
      product_name: 'Nova línia',
      manually_added: true
    }
    item.value.line_items.push(new_line)
  }
}

const handleAddLineItem = async (new_lines) => {
  showSelectLineType.value = false
  pending.value = true;
  try {
    console.log("check")
    for (let new_line of new_lines) {
      item.value.line_items.push(new_line)
      handleSaveLineItem(new_line, 0, false)
    }
    pending.value = false;
  } catch (err) {
    error.value = err;
    pending.value = false;
  }
};

const handleDeleteLineItem = async (index, line) => {
  if (confirm(t('confirmation_text_block.confirm_delete_line'))) {
    if (line.id) {
      await $LineItemApiService.remove(line.id)
      await getInvoice()
      handleChanged(false)
    }
    else item.value.line_items.splice(index, 1);
  }
};

const handleSaveComment = async () => {
  pending.value = true;
  try {

    const payload = {
      id: props.id,
      budget_comment: comment.value
    }

    await $InvoiceApiService.save(payload);
    // await getInvoice();
    handleChanged(false);
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const canConvertToInvoice = computed(() => {
  return item.value
    && item.value.type?.token != invoiceTypeToken.value
    && item.value.status?.token != statusCancelledToken.value
    && !item.value.invoice_budget;
});

const convertBudgetToInvoice = async () => {
  if (!confirm(t('confirmation_text_block.confirm_budget_invoice'))) return;
  generatingInvoice.value = true;
  try {
    const response = await $InvoiceApiService.generateInvoiceBudget({
      entity: 'invoice',
      object_id: props.id,
      is_budget: false,
    });
    if (response) {
      toast.success(t('billing_block.generated_invoice'));
      // La conversió crea una factura nova (id diferent); el pressupost original no canvia,
      // per això cal propagar response.invoice enlloc de recarregar amb el mateix props.id.
      handleChanged(false, response.invoice);
    }
  } catch (err) {
    error.value = err;
  } finally {
    generatingInvoice.value = false;
  }
};

const handleMoveLine = async (index, direction) => {
  if (!item.value?.line_items) return;
  const lines = item.value.line_items;

  const targetIndex = direction === 'up' ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= lines.length) return;

  const temp = lines[index];
  lines[index] = lines[targetIndex];
  lines[targetIndex] = temp;

  lines.forEach((l, idx) => {
    l.custom_order = (idx + 1) * 10;
  });
  await syncOrderToBackend();
};


watch(() => props.id, getData);


onMounted( async () => {
  invoiceTypeToken.value = await $ConfigProjectApiService.get('invoice_type_invoice_token');
  originReadingToken.value = await $ConfigProjectApiService.get('origin_reading_token');
  statusCancelledToken.value = await $ConfigProjectApiService.get('invoice_status_cancelled_token');
  await getData();
});
</script>

<template>
    <div class="region__content pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
      <div v-if="pending">
        <AppLoading :text="$t('common.loading')" />
      </div>
      <div v-else-if="error">
        <p>{{t('common.error')}}: {{ error.message }}</p>
        <p>
          <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button>
        </p>
      </div>
      <div class="pb-5" v-else @click="showSelectLineType = false">
        <div class="mb-4 flex items-center justify-between">
          <div class="flex items-center">
            <H1Region> {{ item?.type?.token == invoiceTypeToken ? t('invoice') : t('common.budget_detail') }} {{ item?.serie_final }} </H1Region>
            <div v-if="item?.manually_modified" class="ml-5 relative inline-block">
              <div class="w-5 h-5 rounded-full bg-orange-500 flex items-center justify-center mousover"
                :title="t('common.manually_modified')">
                <span class="text-white text-xs font-bold">!</span>
              </div>
            </div>
          </div>
          <button v-if="canConvertToInvoice" @click="convertBudgetToInvoice" :disabled="generatingInvoice"
            class="bg-sky-500 hover:bg-sky-700 text-white font-bold py-2 px-4 rounded transition duration-300 ease-in-out">
            {{ generatingInvoice ? t('common.loading') + '...' : t('billing_block.invoice_generate') }}
          </button>
        </div>
    
    
    
        <div class="grid grid-cols-[2fr,1fr] gap-4 border-b">
          <div>
            <p class="font-semibold pb-2">{{ t('contract_block.contract_data') }}</p>
            <div class="invoice__heading max-w-md pb-3">
              <p v-if="item?.contract" class="flex justify-between">
                <label>{{ t('common.identification') }} {{ t('contract') }}:</label>
                <span>{{ item?.contract.token }}</span>
              </p>
              <p v-else-if="item?.contract_request" class="flex justify-between">
                <label>{{ t('common.identification') }} {{ t('contract_block.short_contract_request') }}:</label>
                <span>{{ item?.contract_request.token }}</span>
              </p>
              <p v-else-if="item?.contract_termination" class="flex justify-between">
                <label>{{ t('common.identification') }} {{ t('contract_block.short_contract_termination') }}:</label>
                <span>{{ item?.contract_termination.token }}</span>
              </p>
              <p v-else-if="item?.connection_request" class="flex justify-between">
                <label>{{ t('common.identification') }} {{ t('connection') }}:</label>
                <span>{{ item?.connection_request.token }}</span>
              </p>
              <!-- <p v-else class="flex justify-between">
                <label>{{ t('common.identification') }} -:</label>
                <span>{{ t('common.no_records') }}</span>
              </p> -->
              <p v-if="item?.serie_final" class="flex justify-between">
                <label>{{ t('billing_block.serie') }}:</label>
                <span>{{ item?.serie_final }}</span>
              </p>
              <p class="flex justify-between">
                <label>{{ t('contract_block.holder') }}:</label>
                <span>{{ item?.customer_final }}</span>
              </p>
              <p class="flex justify-between">
                <label>{{ t('common.person_id') }}:</label>
                <span>{{ item?.customer_token_final }}</span>
              </p>
              <p class="flex justify-between">
                <label>{{ t('address_block.address') }}:</label>
                <span>{{ item?.address_final }}</span>
              </p>
              <p class="flex justify-between">
                <label>{{ t('address_block.municipality') }}:</label>
                <span>{{ item?.location_final }}</span>
              </p>
              <p v-if="item?.persons_final" class="flex justify-between">
                <label>{{ t('contract_block.total_persons') }}:</label>
                <span>{{ item?.persons_final }}</span>
              </p>
            </div>
            <p class="font-semibold pb-2">{{ t('billing') }}</p>
            <div class="invoice__heading max-w-md pb-3">
              <p class="flex justify-between">
                <label>{{ t('common.date') }}:</label>
                <span>{{ formatDate(item?.issue_date) }}</span>
              </p>
              <p class="flex justify-between">
                <label>{{ t('common.number') }}:</label>
                <span>{{ item?.number }}</span>
              </p>
            </div>
            <p class="font-semibold pb-2">{{ t('billing_block.payment_info') }}</p>
            <div class="invoice__heading max-w-md pb-3">
              <p class="flex justify-between">
                <label>{{ t('common.payment_method') }}:</label>
                <span>{{ item?.payment_type_final || t('common.no_payment_method') }}</span>
              </p>
              <p v-if="item?.payment_bank_final" class="flex justify-between">
                <label>{{ t('common.iban') }}:</label>
                <span>
                  <IBAN :value="item?.payment_bank_final" />
                </span>
              </p>
            </div>
          </div>
          <div>
            <p v-if="item?.reading" class="font-semibold pb-2">{{ t('service') }}</p>
            <div v-if="item?.reading" class="invoice__heading max-w-md pb-10">
              <p class="grid grid-cols-3 justify-between">
                <label>{{ t('meter') }}:</label>
                <span class="text-right">{{ item?.reading.meter_code }}</span>
                <span class="text-right" v-if="item?.reading.meter_caliber">&#8960; {{
                  item?.reading.meter_caliber }}</span>
              </p>
              <p v-if="item?.reading_last" class="grid grid-cols-3">
                <label>{{ t('billing_block.previous_reading') }}:</label>
                <span class="text-right">{{ formatDate(item?.reading_last.reading_date) }}</span>
                <abbr class="text-right" :title="item?.reading_last?.id || null">{{
                  parseInt(item?.reading_last.reading_value)
                  }}</abbr>
              </p>
              <p class="grid grid-cols-3">
                <label>{{ t('billing_block.current_reading') }}:</label>
                <span class="text-right">{{ formatDate(item?.reading.reading_date) }}</span>
                <abbr class="text-right" :title="item?.reading?.id || null">{{ parseInt(item?.reading.reading_value)
                  }}</abbr>
              </p>
              <p class="flex justify-between">
                <label>{{ t('billing_block.consumption') }}:</label>
                <span>{{ item?.consumption }} <kbd>m3</kbd></span>
              </p>
    
              <p class="flex justify-between">
                <label>{{ t('billing_block.consumption_days') }}:</label>
                <span>{{ item?.consumption_days }}</span>
              </p>
    
              <p class="flex justify-between">
                <label>{{ t('billing_block.consumption_responsible') }}:</label>
                <span>{{ item?.responsible_consumption ? t('common.yes') : t('common.no') }}</span>
              </p>
            </div>
          </div>
        </div>
    
        <div class="invoice__main pb-10 pt-2">
          <div class="flex justify-between items-center pb-2">
            <h3 class="font-bold">{{ item?.title_final }}</h3>
            <button @click.stop @click="handleAddLine"
              class="bg-sky-500 hover:bg-sky-700 text-white font-bold py-2 px-4 rounded transition duration-300 ease-in-out">
              {{ t('common.add') }} {{ t('common.line') }}
            </button>
          </div>
          <div class="invoice__main_heading mb-3 p-1">
            <div class="grid grid-cols-[1fr,80px,80px,100px,70px] gap-2">
              <div><strong>{{ t('line_item') }}</strong></div>
              <div><strong>{{ t('common.units') }}</strong></div>
              <div><strong>{{ t('billing_block.price_unit_short') }}</strong></div>
              <div><strong>{{ t('common.amount') }}</strong></div>
              <div><strong>{{ t('common.iva') }}%</strong></div>
            </div>
          </div>
          <Draggable v-if="item?.line_items" v-model="item.line_items" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd"
            tag="div" :options="{ animation: 200 }" :disabled="!isReorderable">
            <template #item="{ element: line, index }">
              <div :class="['grid grid-cols-[1fr,80px,80px,100px,70px] gap-2 pb-3 p-1 relative transition-all duration-150', { 'bg-slate-100': !(index % 2) }]">
                <div>
                  <div class="flex items-center gap-2 ml-1">
                    <div class="flex items-center">
                      <div v-if="isReorderable" class="handle-move cursor-move text-slate-400 hover:text-slate-600 mr-1.5 flex items-center p-1" title="Arrossegar per reordenar">
                        <Icon name="fa6-solid:grip-vertical" class="w-3.5 h-3.5" />
                      </div>
                      <strong>{{ line.product_name }}</strong>
                      <div v-if="isReorderable" class="flex items-center gap-0.5 ml-2">
                        <button v-if="index > 0" @click="() => handleMoveLine(index, 'up')" :disabled="pending"
                          class="p-1 text-slate-400 hover:text-sky-600 transition" title="Pujar">
                          <Icon name="fa6-solid:chevron-up" class="w-3 h-3" />
                        </button>
                        <button v-if="index < (item?.line_items?.length || 0) - 1" @click="() => handleMoveLine(index, 'down')" :disabled="pending"
                          class="p-1 text-slate-400 hover:text-sky-600 transition" title="Baixar">
                          <Icon name="fa6-solid:chevron-down" class="w-3 h-3" />
                        </button>
                      </div>
                      <OptionsDropdown :bg="!(index % 2) ? 'gray-100' : 'white'" :bgHover="!(index % 2) ? 'white' : 'gray-100'">
                        <DropdownOption :name="t('common.delete')" @click="handleDeleteLineItem(index, line)"></DropdownOption>
                      </OptionsDropdown>
                    </div>
                    <div v-if="(line?.manually_modified || line?.manually_added) && item.type.token == invoiceTypeToken" class="relative inline-block">
                      <div class="w-5 h-5 rounded-full bg-orange-500 flex items-center justify-center mousover"
                        :title="line?.manually_added ? t('common.manually_added') : t('common.manually_modified')">
                        <span class="text-white text-xs font-bold">!</span>
                      </div>
                    </div>
                  </div>
                  <div class="pl-2">
                    <input v-model="line.name" type="text" class="w-full border rounded px-2 py-1 mb-1" /><br />
                    <textarea v-model="line.description" class="w-full border rounded px-2 py-1" rows="2"></textarea>
                  </div>
                </div>
                <div class="mt-5">
                  <input v-numeric-only v-model.number="line.units" class="w-full border rounded px-2 py-1" />
                </div>
                <div class="mt-5">
                  <input v-numeric-only.signed v-model.number="line.price_unit" class="w-full border rounded px-2 py-1" />
                </div>
                <div class="mt-6"><strong>{{ formatMoneyWithCurrency(line.price) }} <span class="text-orange-500"
                      v-if="line.price != _.round(line.price_unit * line.units, 2)"> 
                      {{ formatMoneyWithCurrency(_.round(line.price_unit * line.units)) }}</span></strong></div>
                <div class="mt-5 mr-1">
                  <input v-numeric-only v-model.number="line.tax_percent" class="w-full border rounded px-2 py-1" />
                </div>
                <div class="absolute right-2 bottom-2 flex gap-2">
                  <button @click="() => handleSaveLineItem(line, index, false)" class="button button-primary w-40" :disabled="pending">
                    {{ pending ? t('common.loading') + '...' : t('common.save') }}
                  </button>
                </div>
              </div>
            </template>
          </Draggable>
        </div>

        <div class="mb-4 px-1 border-b pb-3">
          <label for="comment" class="col-span-2 text-sm font-medium text-slate-800">
          <strong>{{ $t('common.comment') }} ({{ t('common.optional') }})</strong> 
          </label>
          <div class="flex justify-between gap-x-4">
            <textarea v-model="comment" class="w-full border rounded px-2 py-1 w-xl" rows="2"></textarea>

            <div>
              <button @click="handleSaveComment" class="button button-primary w-40" :disabled="pending">
                {{ pending ? t('common.loading') + '...' : t('common.save') }}
              </button>
            </div>
          </div>
        </div>
    
        <div class="invoice__totals max-w-md pb-10">
          <p class="flex justify-between">
            <label>{{ t('billing_block.taxable_base') }}:</label>
            <span>{{ formatMoneyWithCurrency(item?.subtotal_final) }}</span>
          </p>
    
          <p v-for="tax_value, percent in item?.taxes" class="flex justify-between">
            <label>{{ t('common.iva') }} ({{ parseFloat(percent) }}%): {{ t('billing_block.taxable_base') }} {{
              formatMoneyWithCurrency(item?.taxes_base[percent]) }}:</label>
            <span>{{ formatMoneyWithCurrency(tax_value) }}</span>
          </p>
    
          <span class="flex justify-between">
            <h3 class="font-bold">{{ t('billing_block.total_invoice') }}:</h3>
            <span>{{ formatMoneyWithCurrency(item?.total_final) }}</span>
          </span>
          <span v-if="item?.left_to_pay != item?.total_final" class="flex justify-between">
            <h3 class="">{{ t('contract_block.liquidated_balance') }}:</h3>
            <span>{{ formatMoneyWithCurrency(parseFloat(item?.total_final) - parseFloat(item?.left_to_pay)) }}</span>
          </span>
          <span class="flex justify-between">
            <h3 class="font-bold">{{ t('billing_block.total_to_pay') }}:</h3>
            <span>{{ formatMoneyWithCurrency(item?.left_to_pay) }}</span>
          </span>
        </div>
    
        <div class="invoice__footer  max-w-md pb-10">
          <p class="flex justify-between">
            <label>{{ t('common.payment_method') }}:</label>
            <span>{{ item?.payment_type_final }}</span>
          </p>
          <p v-if="item?.payment_bank_final" class="flex justify-between">
            <label>{{ t('common.iban') }}:</label>
            <span>
              <IBAN :value="item?.payment_bank_final" />
            </span>
          </p>
          <!-- <div v-if="item?.accounting_office_final">
            <p  class="flex justify-between">
              <label>{{ t('Oficina comptable') }}:</label>
              <span>{{ item?.accounting_office_final }}</span>
            </p>
            <p  class="flex justify-between">
              <label>{{ t('Òrgan gestor') }}:</label>
              <span>{{ item?.managing_body_final }}</span>
            </p>
            <p  class="flex justify-between">
              <label>{{ t('Unitat tramitadora') }}:</label>
              <span>{{ item?.processing_unit_final }}</span>
            </p>
          </div> -->
        </div>
    
        <Teleport to="body">
          <button @click="invoicePDF()" :disabled="loadingPdf"
            class="fixed bottom-8 right-8 rounded-full bg-slate-700/50 w-12 h-12 hover:bg-slate-700/75 transition-all duration-150 p-4 shadow-lg flex items-center justify-center z-[110]">
            <Icon :name="loadingPdf ? 'fa6-solid:spinner' : 'fa6-solid:file-pdf'" class="text-white w-8 h-8 text-2xl"
              :class="{ 'animate-spin': loadingPdf }" />
          </button>
        </Teleport>
    
      </div>
      <div @click="showSelectLineType = false" v-if="showSelectLineType"
        class="absolute inset-0 flex items-center justify-center z-30 p-4">
        <AddNewInvoiceLine @click.stop :is_connection="is_connection" :id="props.id" 
        @handleNewItem="handleAddLineItem" class="shadow-2xl relative" >
          <template #button-exit>
            <button @click="showSelectLineType = false" 
            class="absolute top-0 right-0 text-slate-500 hover:text-red-500 w-5 h-5 rounded bg-white customers-shadow hover:bg-slate-100 flex items-center justify-center">
              <Icon name="fa6-solid:xmark" class="" />
            </button>
          </template>
        </AddNewInvoiceLine>
      </div>
    </div>
</template>

<style scoped>
.invoice__heading p {
  border-bottom: 1px solid #000;
}

/* Optional: Add tooltip styles if you want a more sophisticated hover effect */
.mousover:hover::after {
  content: attr(title);
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  margin-left: 8px;
  z-index: 10;
}
</style>
