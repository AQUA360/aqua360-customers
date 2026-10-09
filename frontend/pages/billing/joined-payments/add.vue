<script setup>
import { ref, computed, onMounted } from 'vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import H1 from '~/components/atoms/H1.vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import AppLoading from '~/components/atoms/AppLoading.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import AddContracts from '~/components/molecules/AddContracts.vue';
import SelectGroupedPayments from '~/components/molecules/SelectGroupedPayments.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

const toast = useToast();
const { t } = useI18n();

const JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS = [
  'BALANCE',
  'DIRECT_DEBIT',
  'ELECTRONIC_INVOICE',
  'CONFIRMING60',
  'CONFIRMING180',
  'TPV_ONLINE',
];

const { $PaymentApiService, $JoinedPaymentApiService } = useNuxtApp();

const objectPermissions = ref(null);

const loading = ref(true);
const loadingClientData = ref(false);
const loadingFromPage = ref(false);
const saving = ref(false);

const attemptedSave = ref(false);

const contractId = ref(null);     //COULD BE COMING FROM URL, IN CASE IT EXISTS, WHEN SAVING RETURN TO CONTRACT PAGE
const personId = ref(null);       //COULD BE COMING FROM URL, IN CASE IT EXISTS, WHEN SAVING RETURN TO PERSON PAGE

const clientSelect = ref('contract');

const selectedContract = ref(null);
const selectedPerson = ref(null);
const selectedPaymentMethod = ref(null);
const selectedPayments = ref([]);
const dueDate = ref(null);

const clientData = ref(null);       //WILL (PROB) CONTAIN DATA SUCH AS CONTRACT AND PERSON BASICS, DEBT, INVOICES AND COMMITMENT PENDING, AND PROBABLY PAYMENTS TO SELECT

const showRegionDetailComponent = ref(null)
const regionDetailId = ref(null)
const isSubRegionOpen = ref(false);

const clientCard = computed(() => {
  if (selectedPerson.value) {
    return {
      label: t('person'),
      title: selectedPerson.value.full_name,
      holder: null,
      idValue: selectedPerson.value.token,
      vulnerability_level: selectedPerson.value.vulnerability_level,
      important_observations: selectedPerson.value.important_observations,
    };
  }
  if (selectedContract.value) {
    return {
      label: t('contract'),
      title: selectedContract.value.token,
      holder: selectedContract.value.holder_full_name,
      idValue: selectedContract.value.holder_token,
      vulnerability_level: selectedContract.value.holder_vulnerability_level,
      important_observations: selectedContract.value.important_observations,
    };
  }
  return null;
});

const amountSelectedPayments = computed(() => {
  return selectedPayments.value.reduce((acc, payment) => parseFloat(acc) + parseFloat(payment.amount), 0);
});

const hasPendingPayments = computed(() => (clientData.value?.pending_payments?.length || 0) > 0);

const cleanData = () => {
  selectedContract.value = null;
  selectedPerson.value = null;
  selectedPayments.value = [];
  clientData.value = null;
}

const getClientData = async () => {
  loadingClientData.value = true;
  try {

    // LEAVING THIS AS EXPANDABLE DATA IN CASE WE NEED MORE VALUES IN THE FUTURE

    const payload_data = {
      contract: selectedContract.value?.id || null,
      person: selectedPerson.value?.id || null,
    }

    const response = await $JoinedPaymentApiService.getPendingClientData(payload_data);
    clientData.value = response.client_data;
    console.log("clientData");
    console.log(clientData.value);

  } catch (error) {
    console.error(error);
  } finally {
    loadingClientData.value = false;
  }
}

const openRegion = (component, id) => {
  closeSubRegion();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
}

const closeSubRegion = () => {
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const changeClientSelect = (value) => {
  clientSelect.value = value;
}

const onPersonSaved = (person) => {
  selectedPerson.value = person;
  selectedContract.value = null;
  closeSubRegion();
  getClientData();
}

const onContractSelected = (item) => {
  if (selectedContract.value?.id == item.id) {
    selectedContract.value = null;
  } else {
    selectedContract.value = item;
  }
  closeSubRegion();
  getClientData();
}

const onSelectedPaymentsUpdated = (payments, close = false) => {
  selectedPayments.value = payments;
  if (close) closeSubRegion();
}

const save = async () => {
  saving.value = true;
  try {
    const payload = {
      contract_id: selectedContract.value?.id || null,
      person_id: selectedPerson.value?.id || null,
      payments_data: selectedPayments.value.map(p => p.id),
      payment_method_id: selectedPaymentMethod.value,
      due_date: dueDate.value,
    }

    const response = await $JoinedPaymentApiService.save(payload);

    if (response) {
      toast.success(t('common.correct_save'));
      downloadPDF(response.id);
      return navigateTo({
        path: '/billing/joined-payments/',
      });
    }

  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
}

const downloadPDF = async (real_id = null) => {
  try {
    try {
      const payload = {
        contract_id: selectedContract.value?.id || null,
        person_id: selectedPerson.value?.id || null,
        payments_data: selectedPayments.value.map(p => p.id),
        payment_method_id: selectedPaymentMethod.value,
        due_date: dueDate.value,
      }
      const file = await $JoinedPaymentApiService.generatePDF(real_id, payload);
      await openAuthenticatedFileUrl(file.file_url);
    } catch (error) {
      console.error(error);
      toast.error(t('common.error'));
    }
  } catch (error) {
    console.error(error);
  }
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loading.value = false;
})

</script>

<template>
  <div id="wrapper" class="mx-auto w-full p-4 text-base">
    <div class="mb-5 flex items-center justify-between">
      <H1>{{ $t(`billing_block.new_joined_payment`) }}</H1>
    </div>

    <div class="overflow-hidden">
      <AppLoading v-if="loading" />

      <div v-else class="space-y-5 p-2">
        <div>
          <section class="space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
            <section class="space-y-3">
              <div class="inline-flex rounded-lg border border-slate-200 text-white bg-sky-400 p-0.5">
                <button type="button"
                  @click="clientSelect == 'person' ? clientSelect = 'contract' : clientSelect = 'person'"
                  class="rounded-md px-3 py-1.5 text-xs uppercase tracking-wide transition-all"
                  :class="clientSelect === 'person' ? 'bg-white text-sky-700 shadow-sm font-bold' : 'hover:text-slate-700'">
                  {{ $t('person') }}
                </button>
                <button type="button"
                  @click="clientSelect == 'contract' ? clientSelect = 'person' : clientSelect = 'contract'"
                  class="rounded-md px-3 py-1.5 text-xs uppercase tracking-wide transition-all"
                  :class="clientSelect === 'contract' ? 'bg-white text-sky-700 shadow-sm font-bold' : 'hover:text-slate-700'">
                  {{ $t('contract') }}
                </button>
              </div>

              <div class="space-y-2">
                <label for="client" class="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <Icon v-show="selectedContract || selectedPerson" name="fa6-solid:circle-check"
                    class="text-lg text-emerald-600" />
                  <Icon v-show="!selectedContract && !selectedPerson" name="fa6-solid:asterisk"
                    class="text-sm text-slate-400" />
                  <span>{{ $t('common.client') }}</span>
                </label>
                <section class="grid grid-cols-[2fr,1fr] gap-4">
                  <ButtonSeleccio v-if="!selectedPerson && !selectedContract"
                    @click="openRegion(clientSelect === 'contract' ? 'AddContracts' : 'PersonSearch', null)"
                    class="flex w-full items-center gap-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700 max-w-xl min-w-xl">
                    <Icon name="fa6-solid:hand-pointer" class="text-slate-500" />
                    {{ $t('common.add') }} {{ clientSelect === 'contract' ? $t('contract') : $t('person') }}
                  </ButtonSeleccio>

                  <div v-if="clientCard"
                    class="w-full max-w-xl min-w-xl rounded-xl border border-slate-300 bg-green-50 p-4 text-sm text-slate-700 shadow-sm relative">
                    <div class="flex items-start justify-between gap-3">
                      <div class="space-y-1">
                        <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          {{ clientCard.label }}
                        </p>
                        <p class="text-sm font-semibold text-slate-800">
                          {{ clientCard.title }}
                        </p>
                        <p v-if="clientCard.holder" class="text-xs text-slate-500">
                          {{ t('contract_block.holder') }}:
                          <span class="font-medium text-slate-700">{{ clientCard.holder }}</span>
                        </p>
                        <p class="text-xs text-slate-500">
                          {{ t('common.person_id') }}:
                          <span class="font-medium text-slate-700">{{ clientCard.idValue }}</span>
                        </p>
                      </div>
                      <AtomsVulnerabilityCheck v-if="clientCard.vulnerability_level > 0"
                        :vulnerability_level="clientCard.vulnerability_level" />
                    </div>

                    <div v-if="clientCard.important_observations?.length"
                      class="mt-2 space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 p-1 px-2">
                      <p v-for="obs in clientCard.important_observations" :key="obs.id"
                        class="text-xs leading-relaxed font-semibold text-amber-600 italic flex items-center gap-2">
                        <Icon name="fa6-solid:circle-exclamation" class="text-amber-600" />
                        {{ obs.observation }}
                      </p>
                    </div>
                    <button @click="cleanData"
                      class="absolute right-2 top-2 h-6 w-6 items-center justify-center rounded-md bg-white hover:bg-red-50 transition-all duration-200 hover:shadow-md">
                      <Icon name="fa6-solid:xmark" class="text-slate-500 hover:text-slate-700" />
                    </button>
                  </div>

                  <aside v-if="loadingClientData"
                    class="rounded-lg border border-slate-200  p-4 flex justify-center items-center">
                    <div class="flex flex-col items-center gap-2">
                      <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-gray-500" />
                      <span class="ml-2 text-sm text-gray-500">{{ $t('common.loading') }}...</span>
                    </div>
                  </aside>
                  <aside v-if="clientData" class="rounded-lg border border-slate-200  p-4">
                    <div class="space-y-1.5 text-sm">
                      <div class="flex items-center justify-between gap-2">
                        <label for="debt_accumulated" class="text-slate-600">{{ $t('contract_block.debt_accumulated')
                          }}</label>
                        <span class="font-semibold text-red-600">{{ formatMoneyWithCurrency(clientData?.total_pending ||
                          0) }}</span>
                      </div>
                      <div class="flex items-center justify-between gap-2 text-xs">
                        <label for="invoices"
                          :class="{ 'text-red-600': clientData?.total_pending_invoices > 0, 'text-slate-500': clientData?.total_pending_invoices == 0 }">{{
                            $t('invoices') }}</label>
                        <span class="font-medium"
                          :class="{ 'text-red-600': clientData?.total_pending_invoices > 0, 'text-slate-700': clientData?.total_pending_invoices == 0 }">
                          {{ formatMoneyWithCurrency(clientData?.total_pending_invoices || 0) }}
                        </span>
                      </div>
                      <div class="flex items-center justify-between gap-2 text-xs">
                        <label for="invoices" class="text-slate-500">{{ $t('claim_block.pay_commitments') }}</label>
                        <span class="font-medium text-slate-700">{{
                          formatMoneyWithCurrency(clientData?.total_pending_commitments || 0) }}</span>
                      </div>
                    </div>
                  </aside>
                </section>
              </div>
            </section>
          </section>
        </div>

        <section class="flex items-center justify-between">
          <div class="w-full">
            <SelectPaymentType v-model="selectedPaymentMethod" :exclude-tokens="JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS"
              :invalid="attemptedSave && !selectedPaymentMethod"
              select-class="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700"
              select-wrapper-class="max-w-xl" :model-as-number="true">
              <template #label>
                <label for="payment_method" class="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <Icon v-show="selectedPaymentMethod" name="fa6-solid:circle-check" class="text-lg text-emerald-600" />
                  <Icon v-show="!selectedPaymentMethod" name="fa6-solid:asterisk" class="text-sm text-slate-400" />
                  <span>{{ $t('common.payment_method') }}</span>
                </label>
              </template>
            </SelectPaymentType>
          </div>
          <div>
            <label for="due_date" class="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <Icon v-show="dueDate" name="fa6-solid:circle-check" class="text-lg text-emerald-600" />
              <Icon v-show="!dueDate" name="fa6-solid:asterisk" class="text-sm text-slate-400" />
              <span>{{ $t('common.due_date') }}</span>
            </label>

            <AtomsInputDate v-model="dueDate" :label="''" />
          </div>
        </section>

        <section class="rounded-lg border border-slate-200  p-4">
          <div class="mb-3 flex items-center justify-between">
            <label for="selected_payments" class="text-sm font-semibold text-slate-700">
              {{ $t('billing_block.selected_payments') }}
            </label>
            <div class="flex items-center gap-x-2">
              <span v-if="!loadingClientData && clientData && amountSelectedPayments > 0"
                class="font-bold text-orange-700">
                {{ formatMoneyWithCurrency(amountSelectedPayments) }}</span>
              <span class="rounded-full px-2 py-0.5 text-xs font-semibold" :class="{
                'text-slate-600 bg-slate-100': clientData?.pending_payments?.length > 0,
                'text-orange-600 bg-orange-100': clientData?.pending_payments?.length == 0 || !clientData,
              }">
                <span v-if="!loadingClientData">
                  {{ selectedPayments.length }} / {{ clientData?.pending_payments?.length || 0 }}
                </span>
                <span v-else class="flex items-center gap-x-2 text-sm">
                  <Icon name="fa6-solid:spinner" class="animate-spin" />
                  <span>{{ $t('common.loading') }}...</span>
                </span>
              </span>
            </div>
          </div>

          <div class="space-y-2 overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 700px)' }">
            <div v-for="payment in selectedPayments" :key="payment.id"
              class="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <div class="flex items-center gap-2 text-slate-600">
                <span class="font-medium">{{ payment.invoice ? $t('invoice') : payment.commitment_deposit ?
                  $t('commitment_deposit') : '-' }}:</span>
                <span class="font-semibold text-slate-700">{{ payment.invoice ? payment.invoice.serie_final :
                  payment.commitment_deposit ? payment.commitment_deposit.token : '-' }}</span>
              </div>

              <div class="flex items-center gap-2 text-slate-600">
                <span class="font-medium">{{ $t('billing_block.total_to_pay') }}:</span>
                <span class="font-semibold text-slate-700">{{ formatMoneyWithCurrency(payment.amount) }}</span>
              </div>
            </div>
          </div>

          <div v-if="!clientData || !hasPendingPayments"
            class="mt-3 flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
            <Icon name="fa6-solid:circle-info" class="mt-0.5 text-sky-600" />
            <p>
              {{ !clientData ? $t('informative_block.info_first_select_client') :
                $t('informative_block.info_no_pending_payments') }}
            </p>
          </div>

          <button @click="openRegion('SelectGroupedPayments', null)" :disabled="!clientData || !hasPendingPayments"
            class="mt-3 flex w-full items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-sky-400 hover:bg-sky-50 hover:text-sky-700 outline-none active:bg-sky-100 active:text-sky-700 active:border-sky-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:hover:border-slate-200 disabled:hover:bg-slate-100 disabled:hover:text-slate-400">
            <Icon name="fa6-solid:plus" />
            {{ $t('billing_block.add_edit_payment') }}
          </button>
        </section>
      </div>

      <div class="flex flex-row-reverse mt-4 gap-x-2">
        <button @click="save"
          :disabled="saving || selectedPayments.length == 0 || selectedPaymentMethod == null || !dueDate"
          class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
        <button @click="downloadPDF(null)"
          :disabled="saving || selectedPayments.length == 0 || selectedPaymentMethod == null || !dueDate"
          class="button-default flex items-center gap-x-1">
          <Icon name="fa6-solid:eye" />&nbsp; {{
            $t('common.check_document') }}
        </button>
      </div>
    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegionDetailComponent, 'translate-x-[2000px]': !showRegionDetailComponent, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonSearch v-if="showRegionDetailComponent === 'PersonSearch'" :id="regionDetailId" :allowCreate="false"
          @show-subregion="handleSubRegionEvent" @saved="onPersonSaved" />
        <AddContracts v-if="showRegionDetailComponent === 'AddContracts'" :multiple="false"
          :selected_items="[selectedContract]" @item-clicked="onContractSelected" />
        <SelectGroupedPayments v-if="showRegionDetailComponent === 'SelectGroupedPayments'"
          :payments="clientData?.pending_payments || []" :modelValue="selectedPayments"
          @update:modelValue="onSelectedPaymentsUpdated" />
      </div>
    </div>
  </div>
</template>
