<script setup>
// components/organisms/ContractDebtRegion.vue
// Pagaments que formen el deute del contracte i liquidació amb un pagament agrupat
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';
import PaymentRegion from './PaymentRegion.vue';
import { checkPermission } from '~/middleware/permission';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

// Mateixos mètodes exclosos que a la creació de pagaments agrupats (billing/joined-payments/add)
const JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS = [
  'BALANCE',
  'DIRECT_DEBIT',
  'ELECTRONIC_INVOICE',
  'CONFIRMING60',
  'CONFIRMING180',
  'TPV_ONLINE',
];

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: Number, // ID del contracte
  isSubRegion: false,
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['show-subregion', 'changed']);

const { $PaymentApiService, $JoinedPaymentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const objectPermissions = ref({ can_change: false, can_view: false });
const SubRegion = ref(props.isSubRegionOpen);

const selectedIds = ref([]);
const selectedPaymentMethod = ref(null);
const dueDate = ref(null);
const attemptedSave = ref(false);
const saving = ref(false);

const payments = computed(() => data.value?.payments || []);
const settleablePayments = computed(() => payments.value.filter(p => p.is_settleable));
const selectedPayments = computed(() => payments.value.filter(p => selectedIds.value.includes(p.id)));
const amountSelectedPayments = computed(() =>
  selectedPayments.value.reduce((acc, payment) => acc + parseFloat(payment.amount), 0)
);
const allSelected = computed(() =>
  settleablePayments.value.length > 0 && settleablePayments.value.every(p => selectedIds.value.includes(p.id))
);
const canSave = computed(() =>
  !saving.value && selectedIds.value.length > 0 && selectedPaymentMethod.value != null && !!dueDate.value
);

/** Carrega permisos i deute, i conserva només les seleccions que encara es poden liquidar. */
const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    objectPermissions.value = await checkPermission($PaymentApiService);
    if (!objectPermissions.value.can_view) {
      error.value = { message: t('common.no_permissions') };
      return;
    }
    data.value = await $JoinedPaymentApiService.getContractDebt(props.id);
    selectedIds.value = selectedIds.value.filter(id => settleablePayments.value.some(p => p.id === id));
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

/** Retorna l'etiqueta traduïda del document que origina el pagament. */
const getOriginType = (payment) => {
  if (payment.invoice) return t('invoice');
  if (payment.commitment_deposit) return t('claim_block.pay_commitments');
  return '-';
};

/** Retorna la referència de la factura o del compromís, o un guió si no n'hi ha. */
const getOriginToken = (payment) => payment.invoice?.serie_final || payment.commitment_deposit?.token || '-';

/** Alterna la selecció d'un pagament liquidable quan hi ha permís de canvi. */
const togglePayment = (payment) => {
  if (!payment.is_settleable || !objectPermissions.value.can_change) return;
  if (selectedIds.value.includes(payment.id)) {
    selectedIds.value = selectedIds.value.filter(id => id !== payment.id);
  } else {
    selectedIds.value = [...selectedIds.value, payment.id];
  }
}

/** Selecciona tots els pagaments liquidables o buida la selecció si ja ho estan. */
const toggleAll = () => {
  selectedIds.value = allSelected.value ? [] : settleablePayments.value.map(p => p.id);
}

/** Construeix les dades de liquidació amb el contracte, la selecció, el mètode i el venciment. */
const buildPayload = () => ({
  contract_id: props.id,
  person_id: null,
  payments_data: selectedIds.value,
  payment_method_id: selectedPaymentMethod.value,
  due_date: dueDate.value,
});

/** Obre el PDF del pagament agrupat indicat o previsualitza les dades del formulari. */
const openPDF = async (id = null) => {
  try {
    const file = await $JoinedPaymentApiService.generatePDF(id, buildPayload());
    await openAuthenticatedFileUrl(file.file_url);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  }
}

/** Desa la liquidació vàlida, obre el PDF i recarrega el deute abans d'emetre el canvi. */
const save = async () => {
  attemptedSave.value = true;
  if (!canSave.value) return;
  saving.value = true;
  try {
    const response = await $JoinedPaymentApiService.save(buildPayload());
    if (response) {
      toast.success(t('common.correct_save'));
      await openPDF(response.id);
      selectedIds.value = [];
      attemptedSave.value = false;
      await getData(false);
      emit('changed');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
}

watch(() => props.id, () => {
  selectedIds.value = [];
  closeSubRegion();
  getData();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(() => {
  getData();
});

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

/** Tanca el detall del pagament, neteja la selecció de regió i ho comunica al pare. */
const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}

/** Obre la subregió indicada per al pagament i ho comunica al pare. */
const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  SubRegion.value = true;
  emit('show-subregion', true);
}
</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p v-if="error.message !== t('common.no_permissions')"><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button></p>
    </div>
    <div v-else-if="data" class="transition-all duration-500 ease" :class="{ 'mr-[48%]': SubRegion }">
      <H1Region class="mb-1" icon="fa6-solid:money-bill-wave">{{ $t('billing_block.debt_detail') }}</H1Region>
      <p class="mb-3 text-sm text-slate-500">{{ $t('contract') }} {{ data.contract?.token }}</p>

      <section class="mb-4 grid grid-cols-2 gap-2 text-sm">
        <div class="rounded-lg border border-red-200 bg-red-50 px-3 py-2">
          <p class="text-xs text-red-600">{{ $t('common.debt') }}</p>
          <p class="font-semibold text-red-700">{{ formatMoneyWithCurrency(data.total_debt) }}</p>
        </div>
        <div class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
          <p class="text-xs text-emerald-700">{{ $t('billing_block.debt_settleable') }}</p>
          <p class="font-semibold text-emerald-800">{{ formatMoneyWithCurrency(data.total_settleable) }}</p>
        </div>
        <div v-if="parseFloat(data.total_in_pending_remittance) > 0"
          class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <p class="text-xs text-amber-700">{{ $t('billing_block.debt_in_pending_remittance') }}</p>
          <p class="font-semibold text-amber-800">{{ formatMoneyWithCurrency(data.total_in_pending_remittance) }}</p>
        </div>
        <div v-if="parseFloat(data.total_in_joined_payment) > 0"
          class="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2">
          <p class="text-xs text-violet-700">{{ $t('billing_block.debt_in_joined_payment') }}</p>
          <p class="font-semibold text-violet-800">{{ formatMoneyWithCurrency(data.total_in_joined_payment) }}</p>
        </div>
      </section>

      <section>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-700">{{ $t('billing_block.pending_payments') }}</h2>
          <button v-if="objectPermissions.can_change && settleablePayments.length > 0" @click="toggleAll"
            class="button-default">
            <Icon name="fa6-solid:check-double" />
            {{ allSelected ? $t('common.deselect_all') : $t('common.select_all') }}
          </button>
        </div>

        <div v-if="payments.length === 0"
          class="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
          <Icon name="fa6-solid:circle-info" class="mt-0.5 text-sky-600" />
          <p>{{ $t('informative_block.info_no_pending_payments') }}</p>
        </div>

        <div v-else class="divide-y rounded-lg border border-slate-200 text-sm">
          <div v-for="payment in payments" :key="payment.id"
            class="flex items-start gap-3 px-3 py-2"
            :class="{
              'bg-yellow-50': selectedIds.includes(payment.id),
              'cursor-pointer hover:bg-slate-50': payment.is_settleable && objectPermissions.can_change && !selectedIds.includes(payment.id),
              'bg-slate-50 text-slate-500': !payment.is_settleable,
            }"
            @click="togglePayment(payment)">
            <input type="checkbox" class="mt-1" :checked="selectedIds.includes(payment.id)"
              :disabled="!payment.is_settleable || !objectPermissions.can_change" @click.stop="togglePayment(payment)" />
            <div class="flex-1 min-w-0">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span class="font-semibold">{{ formatMoneyWithCurrency(payment.amount) }}</span>
                <span>{{ getOriginType(payment) }}: <span class="font-medium">{{ getOriginToken(payment) }}</span></span>
                <span class="text-slate-500">{{ $t('common.due_date') }}: {{ payment.due_date ? formatDate(payment.due_date) : '-' }}</span>
                <AtomsColorBadge :value="payment.status?.name || '-'" :color="payment.status?.color" />
              </div>
              <div class="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <span v-if="payment.remittance?.is_pending_send"
                  class="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-amber-700">
                  <Icon name="fa6-solid:building-columns" />
                  {{ $t('billing_block.debt_remittance_pending_send', { token: payment.remittance.token || payment.remittance.id }) }}
                </span>
                <span v-else-if="payment.remittance"
                  class="inline-flex items-center gap-1 rounded border border-slate-300 px-1.5 py-0.5 text-slate-500">
                  <Icon name="fa6-solid:building-columns" />
                  {{ $t('billing_block.debt_remittance_sent', { token: payment.remittance.token || payment.remittance.id, date: formatDate(payment.remittance.sent_at) }) }}
                </span>
                <span v-if="payment.joined_payment"
                  class="inline-flex items-center gap-1 rounded border border-violet-300 bg-violet-50 px-1.5 py-0.5 text-violet-700">
                  <Icon name="fa6-solid:layer-group" />
                  {{ $t('billing_block.debt_in_joined_payment_token', { token: payment.joined_payment.token, status: payment.joined_payment.status || '-' }) }}
                </span>
                <span v-if="!payment.in_debt"
                  class="inline-flex items-center gap-1 rounded border border-slate-300 px-1.5 py-0.5 text-slate-500">
                  {{ $t('billing_block.debt_not_in_debt') }}
                </span>
                <span v-if="!payment.is_settleable && !payment.remittance?.is_pending_send && !payment.joined_payment"
                  class="inline-flex items-center gap-1 rounded border border-slate-300 px-1.5 py-0.5 text-slate-500">
                  {{ $t('billing_block.debt_not_settleable') }}
                </span>
              </div>
            </div>
            <button @click.stop="showDetail('PaymentRegion', payment.id)" :title="$t('common.view_details')"
              class="px-2 py-1 text-slate-500 hover:text-sky-600">
              <Icon name="fa6-solid:eye" />
            </button>
          </div>
        </div>

        <p v-if="payments.some(p => !p.is_settleable)" class="mt-2 text-xs text-slate-500">
          <Icon name="fa6-solid:circle-info" class="mr-1" />
          {{ $t('billing_block.info_debt_payments_not_settleable') }}
        </p>
      </section>

      <section v-if="objectPermissions.can_change && settleablePayments.length > 0"
        class="mt-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-700">{{ $t('billing_block.debt_settle') }}</h2>
          <span v-if="selectedIds.length > 0" class="font-bold text-orange-700">
            {{ selectedIds.length }} · {{ formatMoneyWithCurrency(amountSelectedPayments) }}
          </span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <SelectPaymentType v-model="selectedPaymentMethod" :exclude-tokens="JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS"
            :invalid="attemptedSave && !selectedPaymentMethod"
            select-class="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700" :model-as-number="true">
            <template #label>
              <label class="mb-2 block text-sm font-semibold text-slate-700">{{ $t('common.payment_method') }}</label>
            </template>
          </SelectPaymentType>
          <div>
            <label class="mb-2 block text-sm font-semibold text-slate-700">{{ $t('common.due_date') }}</label>
            <AtomsInputDate v-model="dueDate" :label="''" />
          </div>
        </div>
        <div class="flex flex-row-reverse gap-x-2">
          <button @click="save" :disabled="!canSave" class="button-primary">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('billing_block.new_joined_payment') }}
          </button>
          <button @click="openPDF(null)" :disabled="!canSave" class="button-default flex items-center gap-x-1">
            <Icon name="fa6-solid:eye" />&nbsp; {{ $t('common.check_document') }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden fixed top-0 right-0 z-30 w-[48%] overflow-y-auto"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true"
          @changed="getData(false); emit('changed')" />
      </div>
    </div>
  </div>
</template>
