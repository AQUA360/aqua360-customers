<script setup>

import { computed, ref, watch, onMounted } from 'vue';

import { useI18n } from 'vue-i18n';

import { useToast } from 'vue-toastification';

import { formatDate } from '~/utils/date';

import IBAN from '../atoms/IBAN.vue';

import SendInvoiceModal from './SendInvoiceModal.vue';

const { t } = useI18n();

const toast = useToast();

const props = defineProps({

  item: Object, // invoices

  contract: {
    type: Object,
    default: null
  },

  isSubRegion: {
    type: Boolean,
    default: false
  },

  is_info: {
    type: Boolean,
    default: false
  },

  show_payments: {
    type: Boolean,
    default: false
  },

  autoCols: {
    type: Boolean,
    default: false
  },

  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: false
  },

  exportFileName: {
    type: String,
    default: 'invoices'
  },

  // Activates grouped invoice selection mode.
  groupedInvoiceMode: {
    type: Boolean,
    default: false
  },

});

const emit = defineEmits(['show-detail']);

const {
  $PaymentApiService
} = useNuxtApp();

const showDetail = function (component, id) {
  selectedId.value = id;
  emit('show-detail', component, id);
};

// ---------------------------------------------------------
// XLSX EXPORT
// ---------------------------------------------------------

const exportColumns = computed(() => {

  const cols = [
    {
      header: t('common.date'),
      value: (row) => row.issue_date ? formatDate(row.issue_date) : '',
      key: 'issue_date'
    },

    {
      header: t('invoice'),
      value: (row) => row.serie_final,
      key: 'serie'
    },

    {
      header: t('billing_block.payment'),
      value: (row) => row.paid_at ? formatDate(row.paid_at) : '',
      key: 'paid_at'
    },
  ];

  if (!props.is_info) {

    cols.push({
      header: t('common.status'),
      value: (row) => row.status_name,
      key: 'status'
    });

    cols.push({
      header: t('contract_block.holder'),
      value: (row) => [
        row.customer_final,
        row.customer_token_final
      ].filter(Boolean).join(' ')
    });

  } else {

    cols.push({
      header: t('common.title'),
      value: (row) => row.title_final,
      key: 'number'
    });

  }

  cols.push({
    header: t('billing_block.total_to_pay'),
    value: (row) => Number(row.left_to_pay ?? 0),
    key: 'left_to_pay'
  });

  cols.push({
    header: t('common.total'),
    value: (row) => Number(row.total_final ?? 0),
    key: 'total_final'
  });

  return cols;
});

// ---------------------------------------------------------
// SEND / GROUPED INVOICE MODE
// ---------------------------------------------------------

const showSend = computed(() => !!props.contract);

const gridTemplateColumns = computed(() => {

  // minmax(0, 1fr) keeps every row's tracks identical to the header's,
  // regardless of each row's content width (each row is its own grid).
  const fr = 'minmax(0, 1fr)';

  const cols = [
    '80px', // date
    // Invoice number + redirect icon must fit on one line.
    'minmax(170px, 1fr)', // invoice
    '80px', // payment date
    // The title column (info mode) needs more room than the status badge.
    props.is_info ? '200px' : '120px',
  ];

  // Holder column only exists outside info mode.
  if (!props.is_info) {
    cols.push(fr);
  }

  cols.push(fr, fr); // left to pay, total

  if (props.show_payments) {
    cols.unshift('50px');
  }

  if (showSend.value) {
    cols.push('70px');
  }

  return cols.join(' ');
});

// IDs of invoices selected for grouped sending.
const selectedInvoiceIds = ref([]);

// Invoice currently displayed by the send modal.
const invoiceToSend = ref(null);

const sendModalOpen = ref(false);

// Current position inside the selected invoices list.
const currentSendIndex = ref(0);

// Only invoices that are currently loaded can be used here.
// The parent can later move this state to the parent component
// if selections must survive pagination.
const selectedInvoices = computed(() => {

  if (!localData.value) {
    return [];
  }

  return localData.value.filter((invoice) =>
    selectedInvoiceIds.value.includes(invoice.id)
  );
});

const hasSelectedInvoices = computed(() =>
  selectedInvoices.value.length > 0
);

const hasMultipleSelectedInvoices = computed(() =>
  selectedInvoices.value.length > 1
);

const canGoPrevious = computed(() =>
  currentSendIndex.value > 0
);

const canGoNext = computed(() =>
  currentSendIndex.value < selectedInvoices.value.length - 1
);

// An invoice can only be selected if it has a document to send.
const canSelectInvoice = (invoice) =>
  !!invoice?.invoice_file_template;

const isInvoiceSelected = (invoice) =>
  selectedInvoiceIds.value.includes(invoice.id);

const toggleInvoiceSelection = (invoice) => {

  // Sending is disabled for invoices without a document.
  if (!canSelectInvoice(invoice)) {
    return;
  }

  const index = selectedInvoiceIds.value.indexOf(invoice.id);

  if (index === -1) {

    selectedInvoiceIds.value.push(invoice.id);

  } else {

    selectedInvoiceIds.value.splice(index, 1);

  }
};

// ---------------------------------------------------------
// INDIVIDUAL SEND
// ---------------------------------------------------------

const openSendModal = (invoice) => {

  if (!invoice.invoice_file_template) {

    toast.warning(
      t('billing_block.invoice_no_document')
    );

    return;
  }

  invoiceToSend.value = invoice;
  currentSendIndex.value = 0;
  sendModalOpen.value = true;
};

// ---------------------------------------------------------
// GROUPED SEND
// ---------------------------------------------------------

const openGroupedSendModal = () => {

  if (!selectedInvoices.value.length) {
    return;
  }

  currentSendIndex.value = 0;

  invoiceToSend.value =
    selectedInvoices.value[0];

  sendModalOpen.value = true;
};

// ---------------------------------------------------------
// MODAL NAVIGATION
// ---------------------------------------------------------

const previousInvoice = () => {

  if (!canGoPrevious.value) {
    return;
  }

  currentSendIndex.value--;

  invoiceToSend.value =
    selectedInvoices.value[
      currentSendIndex.value
    ];
};

const nextInvoice = () => {

  if (!canGoNext.value) {
    return;
  }

  currentSendIndex.value++;

  invoiceToSend.value =
    selectedInvoices.value[
      currentSendIndex.value
    ];
};

const closeSendModal = () => {

  sendModalOpen.value = false;

  invoiceToSend.value = null;

  currentSendIndex.value = 0;
};

// ---------------------------------------------------------
// PAYMENTS
// ---------------------------------------------------------

const selectedId = ref(null);

const localData = ref(null);

const paymentSelected = ref(null);

const showPayments = (item) => {

  if (paymentSelected.value === item) {

    paymentSelected.value = null;

    return;
  }

  paymentSelected.value = item;
};

const getPaymentsFromInvoice = async (invoice) => {

  try {

    const result = await $PaymentApiService.getAll(
      '',
      [],
      1,
      null,
      false,
      invoice.id
    );

    return result.results;

  } catch (err) {

    console.error(
      'Error obtaining data:',
      err
    );

    return [];
  }
};

const loadLocalDataWithPayments = async (items) => {

  let localItems = items || [];

  if (!props.show_payments) {

    localData.value = localItems;

    return;
  }

  const enriched = await Promise.all(
    localItems.map(async (invoice) => {

      const payments =
        await getPaymentsFromInvoice(invoice);

      return {
        ...invoice,
        payments
      };

    })
  );

  localData.value = enriched;
};

// ---------------------------------------------------------
// LIFECYCLE
// ---------------------------------------------------------

onMounted(async () => {

  await loadLocalDataWithPayments(
    props.item
  );

});

watch(
  () => props.item,
  async (newVal) => {

    await loadLocalDataWithPayments(
      newVal
    );

    // Remove selections for invoices that no longer exist
    // in the current local data.
    //
    // IMPORTANT:
    // If you want selection to survive pagination,
    // move selectedInvoiceIds to the parent component.
  }
);

// When grouped mode is disabled, clear the current selection.
watch(
  () => props.groupedInvoiceMode,
  (enabled) => {

    if (!enabled) {

      selectedInvoiceIds.value = [];

      sendModalOpen.value = false;

      invoiceToSend.value = null;

      currentSendIndex.value = 0;
    }

  }
);

</script>

<template>

  <!-- Toolbar -->
  <div
    v-if="exportable && localData && localData.length > 0"
    class="flex justify-end items-center gap-2 mb-1"
  >
    <!-- Grouped send -->
    <button
      v-if="groupedInvoiceMode && showSend"
      type="button"
      @click="openGroupedSendModal"
      :disabled="!hasSelectedInvoices"
      class="button-primary"
      :class="{ 'opacity-60 cursor-not-allowed': !hasSelectedInvoices }"
      :title="t('common.send')"
    >
      <Icon name="fa6-solid:paper-plane" />
      <span class="ml-1">
        {{ t('common.send') }}
        <span v-if="selectedInvoices.length">
          ({{ selectedInvoices.length }})
        </span>
      </span>
    </button>
  
    <!-- Download XLSX -->
    <AtomsDownloadXlsxButton
      :rows="localData"
      :columns="exportColumns"
      :file-name="exportFileName"
      :sheet-name="t('invoices')"
    />
  </div>

  <!-- Invoice table -->
  <div
    v-if="localData && localData.length > 0"
    class="min-w-full text-sm text-slate-800 mt-2 overflow-x-auto"
  >

    <!-- Header -->
    <div
      class="group grid bg-gray-100 border-b text-left"
      :style="{
        gridTemplateColumns: gridTemplateColumns
      }"
    >

      <span v-if="show_payments"></span>

      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">
        {{ t('common.date') }}
      </span>

      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">
        {{ t('invoice') }}
      </span>

      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">
        {{ t('billing_block.payment') }}
      </span>

      <span
        v-if="!props.is_info"
        class="p-2 pl-2 text-slate-900 font-bold"
      >
        {{ t('common.status') }}
      </span>

      <span
        v-else
        class="p-2 pl-2 text-slate-900 font-bold flex items-center"
      >
        {{ t('common.title') }}
      </span>

      <span
        v-if="!props.is_info"
        class="p-2 pl-2 text-slate-900 font-bold flex items-center"
      >
        {{ t('contract_block.holder') }}
      </span>

      <span
        class="p-2 pl-2 text-slate-900 font-bold flex items-center"
      >
        {{ t('billing_block.total_to_pay') }}
      </span>

      <span
        class="p-2 pl-2 text-slate-900 font-bold flex items-center"
      >
        {{ t('common.total') }}
      </span>

      <span
        v-if="showSend"
        class="p-2 pl-2 text-slate-900 font-bold flex items-center justify-center"
      >
        {{ t('common.send') }}
      </span>

    </div>

    <!-- Rows -->
    <div
      v-for="item in localData"
      :key="item.id"
      class="border-b group grid text-sm leading-4 transition-all flex items-center duration-100"
      :style="{
        gridTemplateColumns: gridTemplateColumns
      }"
      :class="{
        'bg-yellow-50': item.id === selectedId,
        'bg-sky-50': groupedInvoiceMode && isInvoiceSelected(item)
      }"
    >

      <!-- Payments -->
      <div
        v-if="show_payments"
        class="text-slate-500 p-2 w-full"
      >

        <button
          @click="showPayments(item)"
          class="text-start text-sky-500 underline"
        >

          <Icon
            name="fa6-solid:angle-down"
            class="text-slate-500 transition-all duration-200 ease"
            :class="{
              'rotate-180':
                paymentSelected === item
            }"
          />

        </button>

      </div>

      <!-- Date -->
      <div class="footering text-slate-500 p-2 w-full">

        <p>
          {{
            item.issue_date
              ? formatDate(item.issue_date)
              : '-'
          }}
        </p>

      </div>

      <!-- Invoice -->
      <div
        class="footering text-slate-500 p-2 w-full min-w-0 flex items-center gap-x-2"
      >

        <button
          v-if="!props.isSubRegion"
          @click="showDetail(
            'InvoiceRegion',
            item.id
          )"
          class="text-start text-sky-500 underline whitespace-nowrap"
        >
          {{ item.serie_final }}
        </button>

        <span
          v-else
          class="whitespace-nowrap"
        >
          {{ item.serie_final }}
        </span>

        <AtomsRedirectButton
          :id="item.id"
          :path="'/billing/invoice/'"
        />

      </div>

      <!-- Payment date -->
      <div class="footering text-slate-500 p-2 w-full">

        <p>
          {{
            item.paid_at
              ? formatDate(item.paid_at)
              : '-'
          }}
        </p>

      </div>

      <!-- Status -->
      <div
        v-if="!props.is_info"
        class="footering text-slate-500 p-2 w-full"
      >

        <AtomsColorBadge
          :value="item.status_name"
          :color="item.status_color"
        />

      </div>

      <!-- Title -->
      <div
        v-else
        class="footering text-slate-500 p-2 w-full min-w-0"
      >

        <p
          class="truncate"
          :title="item.title_final"
        >
          {{ item.title_final }}
        </p>

      </div>

      <!-- Holder -->
      <div
        v-if="!props.is_info"
        class="footering text-slate-500 p-2 w-full"
      >

        <p>
          {{ item.customer_final }}
        </p>

        <p class="text-slate-500 text-xs">
          {{ item.customer_token_final }}
        </p>

      </div>

      <!-- Left to pay -->
      <div class="footering text-slate-500 p-2 w-full">

        <p>
          {{
            formatMoneyWithCurrency(
              item.left_to_pay
            )
          }}
        </p>

      </div>

      <!-- Total -->
      <div class="footering text-slate-500 p-2 w-full">

        <p>
          {{
            formatMoneyWithCurrency(
              item.total_final
            )
          }}
        </p>

      </div>

      <!-- Send / Select -->
      <div
        v-if="showSend"
        class="footering text-slate-500 p-2 w-full flex items-center justify-center"
      >

        <!-- GROUPED MODE -->
        <template v-if="groupedInvoiceMode">

          <button
            type="button"
            @click="toggleInvoiceSelection(item)"
            :disabled="!canSelectInvoice(item)"
            class="w-6 h-6 rounded border flex items-center justify-center transition-colors"
            :class="
              !canSelectInvoice(item)
                ? 'bg-slate-200 border-slate-300 text-slate-400 cursor-not-allowed'
                : isInvoiceSelected(item)
                  ? 'bg-sky-500 border-sky-500 text-white'
                  : 'bg-white border-slate-400 text-transparent hover:border-sky-500'
            "
            :title="
              canSelectInvoice(item)
                ? t('common.send')
                : t('billing_block.invoice_no_document')
            "
          >

            <Icon
              v-if="isInvoiceSelected(item)"
              name="fa6-solid:check"
              class="text-xs"
            />

          </button>

        </template>

        <!-- NORMAL MODE -->
        <template v-else>

          <button
            type="button"
            @click="openSendModal(item)"
            :disabled="!item.invoice_file_template"
            class="flex items-center justify-center w-8 h-8 rounded-full transition-colors disabled:cursor-not-allowed"
            :class="
              item.invoice_file_template
                ? 'bg-sky-500 text-white hover:bg-sky-600'
                : 'bg-slate-300 text-slate-500'
            "
            :title="t('common.send')"
          >

            <Icon name="fa6-solid:envelope" />

          </button>

        </template>

      </div>

      <!-- Payments detail -->
      <div
        v-if="paymentSelected === item"
        class="col-span-full mx-auto transition-all duration-200 ease"
      >

        <div
          class="text-slate-500 font-semibold p-2 w-full grid grid-cols-[100px,100px,200px,100px] gap-3 border-y border-slate-300"
        >

          <p>
            {{ t('common.identification') }}
          </p>

          <p>
            {{ t('common.total') }}
          </p>

          <p class="truncate">
            {{ t('common.payment_method') }}
          </p>

          <p>
            {{ t('common.status') }}
          </p>

        </div>

        <div
          v-for="payment in item.payments"
          :key="payment.id"
          class="footering text-slate-500 p-2 w-full grid grid-cols-[100px,100px,200px,100px] gap-3 bg-white"
        >

          <p v-if="isSubRegion">
            {{ payment.token }}
          </p>

          <button
            v-else
            class="text-start text-sky-500 underline"
            @click="showDetail(
              'PaymentRegion',
              payment.id
            )"
          >
            {{ payment.token }}
          </button>

          <p>
            {{
              formatMoneyWithCurrency(
                payment.amount
              )
            }}
          </p>

          <p>
            {{ payment.payment_type }}
          </p>

          <AtomsColorBadge
            :value="payment.status?.name"
            :color="payment.status?.color"
          />

        </div>

      </div>

    </div>

  </div>

  <!-- Empty state -->
  <div v-else>

    <div class="footering text-slate-500 p-2">
      {{ t('common.no_records') }}
    </div>

  </div>

  <!-- Send invoice modal -->
  <SendInvoiceModal
    :show="sendModalOpen"
    :invoice="invoiceToSend"
    :contract="contract"
    :show-navigation="hasMultipleSelectedInvoices"
    :can-go-previous="canGoPrevious"
    :can-go-next="canGoNext"
    @previous="previousInvoice"
    @next="nextInvoice"
    @close="closeSendModal"
  />

</template>