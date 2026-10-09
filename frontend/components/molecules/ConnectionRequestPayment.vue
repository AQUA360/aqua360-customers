<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import { format } from 'date-fns';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import BankDetail from './BankDetail.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  request: Object
});

const router = useRouter();
const { $ConnectionRequestApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const addressOptions = ref({});
const addressOptionsById = ref([]);
const addressOptionsAreEmpty = ref(true);
const selectedBillingAddress = ref(null);

const is_electronic_invoice = ref(false)
const accounting_office = ref(null)
const managing_body = ref(null)
const processing_unit = ref(null)
const command = ref(null)
const record = ref(null)

const { fetchFinalInvoiceTokens, findFinalInvoice } = useFinalInvoiceTokens();
const finalInvoice = ref(null)

const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);
const paymentTypeOptions = ref([]);
const paymentTypeOptionsById = ref([]);

const emits = defineEmits([
  'clickCreateBilling',
  'clickChangeAddressBilling',
  'bankSelect',
  'paymentMethodSelected',
  'paymentSelect',
  'invoice-detail'
]);

const sepaDocuments = ref([]);

const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    const result = await $ConnectionRequestApiService.getDetail(props.id);
    data.value = result;

    fillAddressOptions();

    selectedBillingAddress.value = data.value.address_billing
      ? data.value.address_billing.id
      : null;

    if (!selectedBillingAddress.value) {
      const addresses = data.value.person?.addresses || data.value.company?.addresses || [];
      if (addresses.length === 1) {
        selectedBillingAddress.value = addresses[0].id;
      } else if (addresses.length > 1) {
        const billingAddress = addresses.find(a => a.is_billing);
        if (billingAddress) {
          selectedBillingAddress.value = billingAddress.id;
        }
      }
    }

    selectedPaymentMethod.value = data.value.payment?.type.id;

    if (paymentTypeOptionsById?.value[selectedPaymentMethod?.value]?.token == 'DIRECT_DEBIT') {
      if (data.value.company) {
        selectedBankDebit.value = data.value.payment?.company_iban;
      }
      else if (data.value.person) {
        selectedBankDebit.value = data.value.payment?.IBAN;
      }
    }
    accounting_office.value = data.value.payment ? data.value.payment.accounting_office : null;
    managing_body.value = data.value.payment ? data.value.payment.managing_body : null;
    processing_unit.value = data.value.payment ? data.value.payment.processing_unit : null;
    command.value = data.value.payment ? data.value.payment.command : null;
    record.value = data.value.payment ? data.value.payment.record : null;

    if (accounting_office.value || managing_body.value || processing_unit.value) {
      is_electronic_invoice.value = true;
    }

    finalInvoice.value = findFinalInvoice(data.value.invoices)
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false;
  }
};

const fillAddressFromEntity = (entity) => {
  var addresses = [];
  if (entity) {
    addressOptions.value[entity.full_name || entity.name] = [];
    if (entity.addresses) {
      entity.addresses.forEach((entity_address) => {
        addressOptions.value[entity.full_name || entity.name].push({
          value: entity_address.id,
          label: entity_address.address_complete,
        });
        addresses.push(entity_address.id);
      });

      if (entity.addresses.length == 0) {
        addressOptionsAreEmpty.value = true;
        addressOptions.value[entity.full_name || entity.name].push({
          value: '',
          label: t('address_block.no_address'),
        });
      }
    }
  }

  return addresses;
};

const fillAddressOptions = () => {
  addressOptions.value = {};
  let added = [];

  if (data.value.person) {
    added = fillAddressFromEntity(data.value.person);
  } else if (data.value.company) {
    added = fillAddressFromEntity(data.value.company);
  }

  if (added.length > 0) {
    addressOptionsAreEmpty.value = false;

    Object.values(addressOptions.value).forEach((addressList) => {
      addressList.forEach((address) => {
        addressOptionsById.value[address.value] = address.label;
      });
    });
  }
};

const onSelectPaymentMethod = () => {
  let token = null;
  if (paymentTypeOptionsById.value[selectedPaymentMethod.value]) {
    token = paymentTypeOptionsById.value[selectedPaymentMethod.value].token;
  }

  emits('paymentMethodSelected', selectedPaymentMethod.value, token, null);
};

const fetchPaymentTypes = async () => {
  await fetchFinalInvoiceTokens();

  const response = await $ConfiglistApiService.getAll(
    'contract/contract-payment-type'
  );
  paymentTypeOptions.value = response.results.filter(item => item.token != 'BALANCE');
  // fill paymentTypeOptionsById
  paymentTypeOptionsById.value = [];
  response.results.forEach((item) => {
    if (item.token != 'BALANCE') paymentTypeOptionsById.value[item.id] = item;
  });

};

const onChangeElectronicInvoice = () => {

  if (accounting_office.value && managing_body.value && processing_unit.value) {
    let eData = {
      accounting_office: accounting_office.value,
      managing_body: managing_body.value,
      processing_unit: processing_unit.value,
      command: command.value,
      record: record.value
    }
    emits('paymentMethodSelected', selectedPaymentMethod.value, paymentTypeOptionsById.value[selectedPaymentMethod.value].token, eData);
  }
}

const openInputSepa = () => {
  alert('Open SEPA Input');
};

onMounted(async () => {
  await fetchPaymentTypes();
  await getData();
});

watch(() => props.id, () => {
  getData(false);
});

// Watch key to trigger data reload
watch(() => props.id, () => {
  getData(false);
});

watch(() => props.request, () => {
  getData(false);
}, { deep: true });

const showDetail = (component, id) => {
  emits('invoice-detail', component, id)
}

watch(
  () => selectedBillingAddress.value,
  () => {
    emits('clickChangeAddressBilling', selectedBillingAddress.value);
  }
);

watch(is_electronic_invoice, (newVal) => {
  if (!newVal) {
    accounting_office.value = null;
    managing_body.value = null;
    processing_unit.value = null;
    command.value = null;
    record.value = null;
  }
}, { deep: true });
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}
      </button>
    </p>
  </div>
  <div v-else>
    <div v-if="data" id="item_data" :data-rel="id">
      <fieldset id="solicitant__box" v-if="data.person || data.company" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">
          {{ $t('common.requester') }}
        </legend>
        <template v-if="data.person">
          <p>
            {{ data.person?.name || '' }} {{ data.person?.surname || '' }}
          </p>
          <p>{{ data.person?.token || '' }}</p>
        </template>
        <template v-else-if="data.company">
          <p>{{ data.company?.name || '' }}</p>
          <p>{{ data.company?.vat_number || '' }}</p>
        </template>

        <div v-if="data.person">
          <div v-if="addressOptionsAreEmpty">
            <div class="bg-yellow-100 p-3 italic">
              {{ $t("contract_block.holder_no_addresses") }}
            </div>
            <ButtonSeleccio @click="emits('clickCreateBilling')" class="py-3">
              <Icon name="fa-solid:plus" class="text-slate-500" />
              {{ $t('common.add') }} {{ $t('common.fiscal_address') }}
            </ButtonSeleccio>
          </div>
          <div v-else class="grid grid-cols-[1fr,80px,1fr] gap-3 items-center">
            <select v-model="selectedBillingAddress" class="w-full text-base border border-gray-300 rounded p-2"
              id="billing_address">
              <option value="" selected="selected">
                {{ $t('address_block.select_address') }}
              </option>
              <template v-for="(addresses, entityName) in addressOptions" :key="entityName">
                <optgroup :label="entityName">
                  <option v-for="address in addresses" :value="address.value" :key="address.value">
                    {{ address.label }}
                  </option>
                </optgroup>
              </template>
            </select>

            <span class="text-center"> &mdash; {{ $t('common.or') }} &mdash;</span>
            <ButtonSeleccio @click="emits('clickCreateBilling')" class="py-3">
              <Icon name="fa-solid:plus" class="text-slate-500" />
              {{ $t('common.new_fiscal_address') }}
            </ButtonSeleccio>
          </div>
        </div>
        <div v-if="data.company">
          <fieldset class="px-5 pb-2 bg-white max-w-md rounded customers-shadow">
            <legend class="bg-white border border-slate-400 rounded px-1 text-right">
              {{ t('Adreça') }}
            </legend>
            <div class="">
              {{ data.company.address_complete }}
            </div>
          </fieldset>
        </div>
      </fieldset>

      <hr class="my-2" />

      <div class="grid grid-cols-2 gap-3">

        <div class="mb-4">
          <label for="payment_method" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="selectedPaymentMethod" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="!selectedPaymentMethod" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('common.payment_method') }}:</span>
          </label>

          <div class="max-w-xl ml-3">
            <select v-model="selectedPaymentMethod" class="w-full text-base border border-gray-300 rounded p-2"
              @change="onSelectPaymentMethod" id="payment_method">
              <option value="" selected="selected">
                {{ $t('common.select_payment_method') }}
              </option>
              <option v-for="paymentType in paymentTypeOptions" :value="paymentType.id" :key="paymentType.id">
                {{ paymentType.name }}
              </option>
            </select>
          </div>

          <div class="select_bank mt-3 max-w-xl ml-3" v-if="
            paymentTypeOptionsById[selectedPaymentMethod] &&
            paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT'">
            <div v-if="selectedBankDebit" class="bg-green-100 p-4 rounded relative group">
              <div>
                <BankDetail :item="selectedBankDebit" />
              </div>
              <button @click="emits('bankSelect', data.person != null)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>

            <ButtonSeleccio v-else @click="emits('bankSelect', data.person != null)" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.iban') }}
            </ButtonSeleccio>

            <!-- TODO: ADD SEPA?? -->
            <!-- <div v-if="selectedBankDebit">
              <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
                <div v-if="sepaDocuments.length === 0" class="flex items-center">
                  <button @click="openInputSepa()" name="" class="button-default-xs">
                    <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                    {{ $t('Afegir SEPA') }}
                  </button>
                </div>
                <div v-else>
                  <button
                    class="item__bank border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-2 block text-left mb-2"
                    @click="openInputSepa">
                    <label class="inline-block" :class="'text-black-400 m-1'">{{
                      $t('Document SEPA - Revisat')
                      }}</label>
                  </button>
                </div>
              </fieldset>
            </div> -->
          </div>

          <div>
          </div>

          <!-- <fieldset id="connection_request__box" class="my-3 border px-3 py-2 bg-sky-50">
            <legend class="px-3 font-semibold bg-white shadow">{{ t('Factura') }}</legend>
            <ButtonOutline :disabled="selectedPaymentMethod == null" class="my-2"
            @click="showDetail('AddInvoiceContract', null)">
            {{ $t('Generar pressupost i/o factura') }}
          </ButtonOutline>
        </fieldset> -->

        </div>
        <div>
          <div class="flex items-center mt-9 ml-2 text-slate-500">
            <input v-model="is_electronic_invoice" type="checkbox" id="is_electronic_invoice" name="is_electronic_invoice"
              class="checkbox" />
            <label for="is_electronic_invoice" class="ml-2"> {{ t('common.electronic_invoice') }}</label>
          </div>
  
          <div class="select_bank mt-3 max-w-xl" v-if="is_electronic_invoice">
            <div class="bg-green-50 border border-slate-200 rounded-lg p-4 relative group mb-2">
              <div class="grid grid-cols-2 gap-3">
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.accounting_office') }}
                  </label>
                  <input type="text" v-model="accounting_office"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi oficina" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.managing_body') }}
                  </label>
                  <input type="text" v-model="managing_body"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi òrgan" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.processing_unit') }}
                  </label>
                  <input type="text" v-model="processing_unit"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi unitat" />
                </div>
                <!-- <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.command') }}
                  </label>
                  <input type="text" v-model="command" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi comanda" />
                </div>
                <div class="space-y-1 col-span-2">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.record') }}
                  </label>
                  <input type="text" v-model="record" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi expedient" />
                </div> -->
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
    <!-- end if data -->
  </div>
  <!-- end if pending -->
</template>
