<script setup>
import {
  computed,
  ref,
  watch,
  onMounted
} from 'vue';

import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t, locale } = useI18n();
const toast = useToast();

const {
  $InvoiceApiService,
  $ConfiglistApiService,
  $PersonApiService
} = useNuxtApp();

const languages = AVAILABLE_LANGUAGES;

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },

  invoice: {
    type: Object,
    default: null
  },

  contract: {
    type: Object,
    default: null
  },

  // Mostra navegació entre factures seleccionades
  showNavigation: {
    type: Boolean,
    default: false
  },

  // Hi ha una factura anterior seleccionada
  canGoPrevious: {
    type: Boolean,
    default: false
  },

  // Hi ha una factura posterior seleccionada
  canGoNext: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits([
  'close',
  'previous',
  'next'
]);

const OTHER = '__other__';

// ---------------------------------------------------------
// CONTACTS
// ---------------------------------------------------------

const personContacts = ref([]);

const sourceContacts = computed(() => {
  const contractContacts =
    props.contract?.contacts || [];

  return [
    ...contractContacts,
    ...(personContacts.value || [])
  ];
});

const currentEmail = computed(() => {
  if (
    props.contract
      ?.person_contact_email
      ?.email
  ) {
    return props.contract
      .person_contact_email
      .email;
  }

  const defaultContact =
    sourceContacts.value.find(
      (c) => c.email && c.is_default
    );

  return defaultContact?.email || null;
});

const contactEmails = computed(() => {
  const emails =
    sourceContacts.value
      .map((c) => c.email)
      .filter(Boolean);

  if (currentEmail.value) {
    emails.unshift(
      currentEmail.value
    );
  }

  return [
    ...new Set(emails)
  ];
});

const selectedEmail = ref(null);
const customEmail = ref('');

const applyDefaultEmail = () => {
  selectedEmail.value =
    currentEmail.value ||
    contactEmails.value[0] ||
    OTHER;

  customEmail.value = '';
};

const loadPersonContacts = async () => {
  personContacts.value = [];

  try {
    let person = null;

    const personId =
      props.invoice?.person_id ??
      props.invoice?.person?.id ??
      (
        typeof props.invoice?.person === 'number'
          ? props.invoice.person
          : null
      );

    if (personId) {
      person =
        await $PersonApiService
          .getFullDetail(personId);
    } else if (
      props.invoice?.customer_token_final
    ) {
      person =
        await $PersonApiService
          .getFullDetailByToken(
            props.invoice
              .customer_token_final
          );
    }

    personContacts.value =
      person?.contacts || [];
  } catch (err) {
    console.error(err);
  }

  applyDefaultEmail();
};

const email = computed(() =>
  (
    selectedEmail.value === OTHER
      ? customEmail.value
      : selectedEmail.value
  ) || null
);

// ---------------------------------------------------------
// LANGUAGE / BODY
// ---------------------------------------------------------

const selectedLang = ref(
  locale.value
);

const defaultBodyFor = (lang) =>
  t(
    'billing_block.invoice_email_default_body',
    {},
    {
      locale: lang
    }
  );

const body = ref(
  defaultBodyFor(
    selectedLang.value
  )
);

// ---------------------------------------------------------
// COMPANY CONFIG
// ---------------------------------------------------------

const companyConfigs = ref([]);
const selectedCompanyConfig = ref(null);
const loadingCompanyConfigs = ref(false);

const getCompanyConfigs = async () => {
  loadingCompanyConfigs.value = true;

  try {
    const result =
      await $ConfiglistApiService.getAll(
        'service/company-config'
      );

    companyConfigs.value =
      (result?.results || []).map(
        (config) => ({
          label: config.name,
          value: config.id,
          companyId:
            config.company?.id ??
            config.company ??
            null
        })
      );
  } catch (err) {
    console.error(err);
  } finally {
    loadingCompanyConfigs.value = false;
  }

  applyDefaultCompanyConfig();
};

const applyDefaultCompanyConfig = () => {
  const invoiceCompanyId =
    props.invoice?.company?.id ??
    props.invoice?.company ??
    props.invoice?.company_id ??
    null;

  const match =
    companyConfigs.value.find(
      (c) =>
        c.companyId != null &&
        c.companyId === invoiceCompanyId
    );

  selectedCompanyConfig.value =
    match?.value ??
    companyConfigs.value[0]?.value ??
    null;
};

onMounted(
  getCompanyConfigs
);

// ---------------------------------------------------------
// WATCHERS
// ---------------------------------------------------------

watch(
  () => props.show,
  (isOpen) => {
    if (!isOpen) {
      return;
    }

    selectedLang.value =
      props.contract?.language ||
      locale.value;

    body.value =
      defaultBodyFor(
        selectedLang.value
      );

    applyDefaultEmail();

    if (
      !props.contract
        ?.person_contact_email
        ?.email
    ) {
      loadPersonContacts();
    }

    applyDefaultCompanyConfig();
  }
);

watch(
  selectedLang,
  (lang) => {
    body.value =
      defaultBodyFor(lang);
  }
);

// Quan canviem de factura mitjançant
// les fletxes, actualitzem les dades
watch(
  () => props.invoice,
  (newInvoice) => {
    if (!props.show || !newInvoice) {
      return;
    }

    selectedLang.value =
      props.contract?.language ||
      locale.value;

    body.value =
      defaultBodyFor(
        selectedLang.value
      );

    applyDefaultEmail();
    applyDefaultCompanyConfig();

    if (
      !props.contract
        ?.person_contact_email
        ?.email
    ) {
      loadPersonContacts();
    }
  }
);

// ---------------------------------------------------------
// BACKEND-APPENDED INFORMATION
// ---------------------------------------------------------

const sentInfoLines = computed(() => {
  const lines = [];

  if (props.invoice?.serie_final) {
    lines.push({
      label: t('invoice'),
      value: props.invoice.serie_final
    });
  }

  if (props.contract?.token) {
    lines.push({
      label: t('contract'),
      value: props.contract.token
    });
  }

  return lines;
});

// ---------------------------------------------------------
// INVOICE FILE
// ---------------------------------------------------------

const openInvoiceFileTemplate = async () => {
  if (
    !props.invoice
      ?.invoice_file_template
  ) {
    return;
  }

  try {
    await openAuthenticatedFileUrl(
      props.invoice
        .invoice_file_template
    );
  } catch (err) {
    console.error(err);
  }
};

// ---------------------------------------------------------
// NAVIGATION
// ---------------------------------------------------------

const goPrevious = () => {
  if (!props.canGoPrevious) {
    return;
  }

  emit('previous');
};

const goNext = () => {
  if (!props.canGoNext) {
    return;
  }

  emit('next');
};

// ---------------------------------------------------------
// CLOSE
// ---------------------------------------------------------

const handleClose = () => {
  emit('close');
};

// ---------------------------------------------------------
// SEND
// ---------------------------------------------------------

const sending = ref(false);

const sendEmail = async () => {
  if (
    !email.value ||
    !props.invoice?.id
  ) {
    return;
  }

  sending.value = true;

  try {
    await $InvoiceApiService.sendEmail(
      props.invoice.id,
      {
        email: email.value,
        body: body.value,
        company_config_id:
          selectedCompanyConfig.value
      }
    );

    toast.success(
      t(
        'billing_block.correct_send_email'
      )
    );

    /*
     * Tanquem el modal després d'enviar.
     *
     * InvoiceMiniDetail controla la navegació
     * entre les factures seleccionades.
     */
    emit('close');
  } catch (err) {
    console.error(err);

    toast.error(
      t(
        'billing_block.error_send_email'
      )
    );
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <div v-if="show">

    <!-- Modal Backdrop -->
    <div
      class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40 flex items-center justify-center"
      @click="handleClose"
    />

    <!-- Modal Content -->
    <div
      class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none"
    >
      <div
        class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative pointer-events-auto"
      >

        <!-- Close -->
        <button
          type="button"
          @click="handleClose"
          class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
        >
          <Icon
            name="fa6-solid:xmark"
            class="text-xl"
          />
        </button>

        <!-- Header -->
        <div class="mb-6">
          <h3
            class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"
          >
            <Icon
              name="fa6-solid:envelope"
              class="text-slate-500"
            />

            {{ t('common.send') }}
            {{ t('invoice') }}
          </h3>

          <!-- Invoice navigation -->
          <div
            v-if="showNavigation"
            class="flex items-center justify-center gap-3 mt-4"
          >

            <!-- Previous -->
            <div class="w-8 flex justify-center">
              <button
                v-if="canGoPrevious"
                type="button"
                @click="goPrevious"
                :disabled="sending"
                class="flex items-center justify-center w-8 h-8 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                :title="t('common.previous')"
              >
                <Icon name="fa6-solid:chevron-left" />
              </button>
            </div>
            
            <!-- Current invoice -->
            <span
              class="text-sm text-slate-500 font-medium min-w-[100px] text-center"
            >
              {{ invoice?.serie_final || '-' }}
            </span>
            
            <!-- Next -->
            <div class="w-8 flex justify-center">
              <button
                v-if="canGoNext"
                type="button"
                @click="goNext"
                :disabled="sending"
                class="flex items-center justify-center w-8 h-8 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                :title="t('common.next')"
              >
                <Icon name="fa6-solid:chevron-right" />
              </button>
            </div>
          </div>
        </div>

        <!-- Invoice information -->
        <div class="mb-6">
          <h4
            class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2"
          >
            {{ t('invoice') }}
          </h4>

          <div
            class="border rounded-lg divide-y divide-slate-100"
          >
            <div
              class="flex justify-between px-3 py-2"
            >
              <span class="text-slate-500 text-sm">
                {{ t('invoice') }}
              </span>

              <span class="text-slate-800 text-sm font-medium">
                {{ invoice?.serie_final || '-' }}
              </span>
            </div>

            <div
              class="flex justify-between px-3 py-2"
            >
              <span class="text-slate-500 text-sm">
                {{ t('common.date') }}
              </span>

              <span class="text-slate-800 text-sm font-medium">
                {{
                  invoice?.issue_date
                    ? formatDate(invoice.issue_date)
                    : '-'
                }}
              </span>
            </div>

            <div
              class="flex justify-between px-3 py-2"
            >
              <span class="text-slate-500 text-sm">
                {{ t('common.status') }}
              </span>

              <span class="text-slate-800 text-sm font-medium">
                {{
                  invoice?.status_name ||
                  invoice?.status?.name ||
                  '-'
                }}
              </span>
            </div>

            <div
              class="flex justify-between px-3 py-2"
            >
              <span class="text-slate-500 text-sm">
                {{ t('common.total') }}
              </span>

              <span class="text-slate-800 text-sm font-medium">
                {{
                  formatMoneyWithCurrency(
                    invoice?.total_final
                  )
                }}
              </span>
            </div>

            <div
              v-if="invoice?.invoice_file_template"
              class="flex justify-between px-3 py-2"
            >
              <span class="text-slate-500 text-sm">
                {{ t('common.doc') }}
              </span>

              <button
                type="button"
                @click="openInvoiceFileTemplate"
                class="text-sky-500 underline flex items-center gap-2 text-sm"
              >
                <Icon
                  name="fa6-solid:file-pdf"
                />

                {{ t('common.download') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Company config -->
        <div class="mb-8">
          <h4
            class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2"
          >
            {{ t('service_block.company_config') }}
          </h4>

          <select
            v-model="selectedCompanyConfig"
            :disabled="loadingCompanyConfigs"
            class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 disabled:opacity-50"
          >
            <option
              v-for="config in companyConfigs"
              :key="config.value"
              :value="config.value"
            >
              {{ config.label }}
            </option>
          </select>
        </div>

        <!-- Contact email -->
        <div class="mb-8">
          <h4
            class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2"
          >
            {{ t('common.email_long') }}
          </h4>

          <select
            v-model="selectedEmail"
            class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
          >
            <option
              v-for="opt in contactEmails"
              :key="opt"
              :value="opt"
            >
              {{ opt }}
            </option>

            <option :value="OTHER">
              {{ t('common.other') }}
            </option>
          </select>

          <input
            v-if="selectedEmail === OTHER"
            v-model="customEmail"
            type="email"
            :placeholder="t('common.email_long')"
            class="w-full border border-slate-300 rounded-lg p-2 mt-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
          />
        </div>

        <!-- Email body -->
        <div class="mb-8">
          <div
            class="flex items-center justify-between mb-2"
          >
            <h4
              class="text-sm font-semibold text-slate-500 uppercase tracking-wide"
            >
              {{ t('billing_block.email_body') }}
            </h4>

            <select
              v-model="selectedLang"
              class="border border-slate-300 rounded-md text-sm text-slate-700 py-1 px-2 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
              :title="t('common.language')"
            >
              <option
                v-for="lang in languages"
                :key="lang.code"
                :value="lang.code"
              >
                {{ t(lang.name) }}
              </option>
            </select>
          </div>

          <textarea
            v-model="body"
            rows="6"
            class="w-full border border-slate-300 rounded-lg p-3 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 resize-y"
          />

          <p
            v-if="sentInfoLines.length"
            class="text-xs text-slate-500 mt-2"
          >
            {{ t('billing_block.email_body_included_info') }}

            <span
              v-for="(line, index) in sentInfoLines"
              :key="line.label"
              class="font-medium text-slate-700"
            >
              {{ line.label }}:
              {{ line.value }}

              <span
                v-if="
                  index <
                  sentInfoLines.length - 1
                "
              >
                ,
              </span>
            </span>
          </p>
        </div>

        <!-- Footer -->
        <div class="flex justify-end gap-3">
          <button
            type="button"
            @click="handleClose"
            class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors"
          >
            {{ t('common.close') }}
          </button>

          <button
            type="button"
            @click="sendEmail"
            :disabled="
              !email ||
              !selectedCompanyConfig ||
              sending
            "
            class="button-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon
              :name="
                sending
                  ? 'fa6-solid:spinner'
                  : 'fa6-solid:paper-plane'
              "
              :class="{
                'animate-spin': sending
              }"
            />

            {{ t('common.send') }}
          </button>
        </div>

      </div>
    </div>
  </div>
</template>