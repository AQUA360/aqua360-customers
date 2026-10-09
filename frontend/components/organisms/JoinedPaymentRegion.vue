<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { usePermissions } from '~/middleware/permission';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import JoinedPaymentDetail from '../molecules/JoinedPaymentDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '../molecules/ChangeStatus.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import PaymentRegion from './PaymentRegion.vue';
import ContractRegion from './ContractRegion.vue';
import JoinedPaymentModals from './JoinedPaymentModals.vue';
import TypedConfirmationModal from '../molecules/TypedConfirmationModal.vue';

const { t } = useI18n();
const { permissions, loading } = usePermissions();
const toast = useToast();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion', 'close']);
const router = useRouter();
const { $JoinedPaymentApiService, $PaymentApiService, $ConfigProjectApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);
const statusPaidToken = ref(false)
const statusCancelledToken = ref(false)

const openLiquidateModal = ref(false);
const openModifyModal = ref(false);
const openPaymentProofModal = ref(false);
const cancelConfirmOpen = ref(false);
const selectedPaymentDate = ref(null);
const observation = ref('');
const selectedDueDate = ref(null);
const selectedPaymentMethod = ref(null);

const activeTab = ref('observations');
const logNumber = ref(0)
const observationNumber = ref(0)

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PaymentApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  error.value = null;
  statusPaidToken.value = await $ConfigProjectApiService.get('joined_payment_status_paid_token');
  statusCancelledToken.value = await $ConfigProjectApiService.get('joined_payment_status_cancelled_token');

  try {
    const result = await $JoinedPaymentApiService.getDetail(props.id);
    data.value = result;
    selectedPaymentMethod.value = data.value.payment_type;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const modifyData = async (payment_date = null) => {
  if (
    selectedPaymentMethod.value == data.value.payment_type &&
    selectedDueDate.value == format(data.value.due_date, 'yyyy-MM-dd')
  ) return;

  if (payment_date && payment_date != '') {
    if (selectedPaymentDate.value && data.value.created_at && selectedPaymentDate.value < format(data.value.created_at, 'yyyy-MM-dd')) {
      toast.error(t('warning_block.warning_payment_date_before_invoice_issue_date'));
      selectedPaymentDate.value = format(data.value.created_at, 'yyyy-MM-dd');
      return;
    }
    // if (!confirm(t("confirmation_text_block.confirm_short_pay_payment"))) return
  }

  try {
    let save_data = {
      id: props.id,
    }
    if (selectedDueDate.value) save_data.due_date = selectedDueDate.value;
    if (selectedPaymentMethod.value) save_data.payment_method_id = selectedPaymentMethod.value;
    if (payment_date && payment_date != '') {
      save_data.payment_date = payment_date;
      save_data.status_token = statusPaidToken.value;
    }
    const response = await $JoinedPaymentApiService.save(save_data)
    if (response) {
      getData(false)
    }
  } catch (err) {
    console.error(err)
  } finally {
    openLiquidateModal.value = false;
    openModifyModal.value = false;
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});


onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const updateSubRegion = function () {
  getData();
  closeSubRegion();
  emit('changed')
}

const openLiquidateMethod = () => {
  openLiquidateModal.value = true;
  selectedPaymentDate.value = format(new Date(), 'yyyy-MM-dd');
}

const openModify = () => {
  openModifyModal.value = true;
  selectedDueDate.value = format(data.value.due_date, 'yyyy-MM-dd');
}

const openPaymentProof = () => {
  openPaymentProofModal.value = true;
  selectedPaymentDate.value = format(data.value.payment_date, 'yyyy-MM-dd');
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
  emit('changed');
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}


const showCancelModal = () => {
  cancelConfirmOpen.value = true;
};

const onCancelConfirmed = async () => {
  try {
    const save_data = {
      id: props.id,
      status_token: statusCancelledToken.value,
    }
    const result = await $JoinedPaymentApiService.save(save_data);
    if (result) {
      toast.success(t('common.correct_save'));
      getData();
    }
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
};

const generatePaymentDocument = async () => {
  try {
    const file = await $JoinedPaymentApiService.generatePDF(props.id);
    // window.open(file.file_url, '_blank').focus();
    await openAuthenticatedFileUrl(file.file_url);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
}


const generatePaymentProofDocument = async () => {
  try {
    const payload = {
      id: props.id,
      date: selectedPaymentDate.value,
      observation: observation.value,
    }
    const file = await $JoinedPaymentApiService.generatePaymentProofDoc(payload);
    await openAuthenticatedFileUrl(file.pdf_url);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    openPaymentProofModal.value = false;
    selectedPaymentDate.value = null;
    observation.value = '';
  }
}

let paymentDateCheckTimeout = null
watch(selectedPaymentDate, () => {
  if (paymentDateCheckTimeout) clearTimeout(paymentDateCheckTimeout)
  paymentDateCheckTimeout = setTimeout(() => {
    if (selectedPaymentDate.value && selectedPaymentDate.value < format(data.value.created_at, 'yyyy-MM-dd')) {
      toast.warning(t('warning_block.warning_payment_date_before_invoice_issue_date'));
      selectedPaymentDate.value = format(data.value.created_at, 'yyyy-MM-dd');
    }
    paymentDateCheckTimeout = null
  }, 1000)
})

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[47%]': SubRegion }">
      <JoinedPaymentModals v-if="data" v-model:liquidate-open="openLiquidateModal" v-model:modify-open="openModifyModal"
        v-model:selected-payment-date="selectedPaymentDate" v-model:selected-payment-method="selectedPaymentMethod"
        v-model:selected-due-date="selectedDueDate" :joined-payment="data"
        @modify-data="modifyData" v-model:observation="observation" v-model:generate-proof-open="openPaymentProofModal"
        @generate-proof="generatePaymentProofDocument" />

      <TypedConfirmationModal v-model:open="cancelConfirmOpen"
        :message="t('confirmation_text_block.confirm_cancel_joined_payment')"
        :expected-phrase="t('confirmation_phrase_block.cancel')" @confirm="onCancelConfirmed" />


      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.joined_payment') }}

        </H1Region>
        <div v-if="objectPermissions?.can_change && !openLiquidateModal && !openModifyModal && !cancelConfirmOpen"
          class="relative">
          <OptionsDropdown id="SupplyPointRegionOptions" v-if="data.status?.token != statusCancelledToken">
            <DropdownOption :disabled="(data.status?.token === statusCancelledToken)"
              :name="t('billing_block.download_document')" @click="generatePaymentDocument">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:download" class="display-inline" /> {{ t('billing_block.download_document') }}
              </div>
            </DropdownOption>
            <DropdownOption :disabled="(data.status?.token !== statusPaidToken)"
              :name="t('billing_block.payment_proof')" @click="openPaymentProof">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:file" class="display-inline" /> {{ t('billing_block.payment_proof') }}
              </div>
            </DropdownOption>
            <DropdownOption
              :disabled="(data.status?.token === statusPaidToken) || (data.status?.token === statusCancelledToken)"
              :name="t('common.modify')" @click="openModify">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:pencil" class="display-inline" /> {{ t('common.modify') }}
              </div>
            </DropdownOption>
            <DropdownOption
              :disabled="(data.status?.token === statusPaidToken) || (data.status?.token === statusCancelledToken)"
              :name="t('common.pay')" @click="openLiquidateMethod">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:coins" class="display-inline" /> {{ t('common.pay') }}
              </div>
            </DropdownOption>
            <DropdownOption
              :disabled="(data.status?.token === statusPaidToken) || (data.status?.token === statusCancelledToken)"
              :name="t('common.cancel')" @click="showCancelModal">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:xmark" class="display-inline" /> {{ t('common.cancel') }}
              </div>
            </DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <JoinedPaymentDetail @show-detail="showDetail" :id="props.id" :data="data" :isSubRegion="isSubRegion" />
        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
              aria-current="page">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
                observationNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_log" @click.prevent="setActiveTab('log')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" />
              {{ $t('common.history') }} ({{ logNumber || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_payments" @click.prevent="setActiveTab('payments')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'payments', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'payments' }">
              <Icon name="fa6-solid:briefcase" class="display-inline mr-2" />
              {{ $t('billing_block.payments') }} ({{ data?.payments?.length || 0 }})
            </a>
          </li>
        </AtomsTabs>
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            parent_entity="joined_payment" url_entity="joined-payment" :id="props.id" module="billing">
          </MoleculesObservationList>
        </section>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log"
          class="bg-white antialiased max-h-[50vh] overflow-y-auto">
          <MoleculesLogList v-if="data" entity="joined-payment-status" parent_entity="joined_payment" :id="props.id"
            @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>
        <section v-show="activeTab === 'payments'" role="tabpanel" id="tab_payments"
          class="bg-white antialiased overflow-y-auto mt-2"
          :style="{ minHeight: 'calc(100vh - 450px)', maxHeight: 'calc(100vh - 450px)' }">

          <article v-for="payment in data.payments" :key="payment.id" @click="showDetail('PaymentRegion', payment.id)"
            :title="`${$t('common.show')} ${$t('common.details')}`"
            class="p-3 text-base rounded-lg group hover:bg-sky-50 hover:ring-1 hover:ring-sky-200 cursor-pointer relative mb-2 transition-all duration-200 ease-in-out overflow-hidden"
            :class="{
              'bg-yellow-50': (payment.id === regionDetailId && showRegionDetailComponent === 'PaymentRegion')
                || (payment.invoice?.id === regionDetailId && showRegionDetailComponent === 'InvoiceRegion')
                || (payment.commitment_deposit?.id === regionDetailId && showRegionDetailComponent === 'CommitmentDepositRegion'),
              'bg-slate-50': !(
                (payment.id === regionDetailId && showRegionDetailComponent === 'PaymentRegion')
                || (payment.invoice?.id === regionDetailId && showRegionDetailComponent === 'InvoiceRegion')
                || (payment.commitment_deposit?.id === regionDetailId && showRegionDetailComponent === 'CommitmentDepositRegion')
              ),
            }">
            <footer class="flex justify-between items-center relative pt-1">
              <div class="flex items-center mb-1 gap-2">
                <p class="text-sm text-gray-700 font-medium">
                  {{ payment.name || '-' }}
                </p>
              </div>
              <AtomsColorBadge :value="payment.status?.name" :color="payment.status?.color" class="rounded-full text-xs">
              </AtomsColorBadge>
            </footer>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-700">
              <p class="col-span-2"><span class="font-semibold">{{ t('common.identification') }}:</span> {{
                payment.token }}</p>
              <p><span class="font-semibold">{{ t('common.amount') }}:</span>
                {{ formatMoneyWithCurrency(payment.amount) }}</p>
              <p><span class="font-semibold">{{ t('common.payment_method') }}:</span> {{ payment.payment_type || '-' }}
              </p>
              <p><span class="font-semibold">{{ t('common.due_date') }}:</span> {{ payment.due_date || '-' }}</p>
              <p><span class="font-semibold">{{ t('billing_block.payment_date') }}:</span> {{ payment.payment_date ||
                '-' }}</p>
              <p class="col-span-2">
                <span class="font-semibold">{{ t('common.origin') }}:</span>
                <template v-if="payment.invoice">
                  <button type="button" class="ml-1 text-sky-600 hover:text-sky-800 underline text-left align-baseline"
                    :title="$t('common.show') + ' ' + $t('invoice')"
                    @click.stop="showDetail('InvoiceRegion', payment.invoice.id)">
                    {{ t('invoice') }} — {{ payment.invoice.serie_final || payment.invoice.token || '-' }}
                  </button>
                </template>
                <template v-else-if="payment.commitment_deposit">
                  <button type="button" class="ml-1 text-sky-600 hover:text-sky-800 underline text-left align-baseline"
                    :title="$t('common.show') + ' ' + $t('commitment_deposit')"
                    @click.stop="showDetail('CommitmentDepositRegion', payment.commitment_deposit.id)">
                    {{ t('commitment_deposit') }} — {{ payment.commitment_deposit.token || '-' }}
                  </button>
                </template>
                <template v-else>
                  <span class="ml-1">-</span>
                </template>
              </p>
            </div>
            <div
              class="pointer-events-none absolute inset-y-0 right-0 flex items-center justify-end pr-3 pl-10 opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200 ease-in-out bg-gradient-to-l from-sky-100 via-sky-50/80 to-transparent">
              <span
                class="inline-flex items-center gap-1.5 rounded-full bg-white border border-sky-200 text-sky-600 text-xs font-medium px-2.5 py-1 shadow-sm">
                <Icon name="fa6-solid:eye" class="w-3 h-3" />
                {{ $t('common.show') }}
              </span>
            </div>
          </article>

        </section>
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[47%] z-10"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true"
          @update-id="(newId) => regionDetailId = newId" />
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true"
          @changed="updateSubRegion()" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
          :isSubRegion="true" @changed="updateSubRegion()" />
        <ChangeStatus v-if="showRegionDetailComponent === 'ChangeStatus'" entity="joined-payment"
          parent_entity="joined_payment" :id="props.id" :status="data.status?.id" module="billing"
          :forceToken="statusCancelledToken" @changed="handleStatusChanged" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
