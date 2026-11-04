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
import { invoiceHasPdf, openInvoicePdf } from '~/utils/open-authenticated-file';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t, locale } = useI18n();
const toast = useToast();

const {
  $InvoiceApiService,
  $ConfiglistApiService,
  $ConfigProjectApiService,
  $MessageTemplateApiService,
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
  },

  // IDs de factures ja enviades (el pare ho controla)
  sentIds: {
    type: Array,
    default: () => []
  },

  // Factures seleccionades (per aplicar a totes / enviar totes)
  invoices: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits([
  'close',
  'previous',
  'next',
  'sent',
  'sent-all'
]);

const OTHER = '__other__';

// Origen de les plantilles de missatge de facturació
const BILLING_ORIGIN_TOKEN = 'billing';

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

// Carrega els contactes de la persona de la factura.
// - Descarta la resposta si mentrestant s'ha canviat de factura.
// - Només reseteja el correu si no hi ha esborrany (resetEmail).
const loadPersonContacts = async (invoice, resetEmail = true) => {
  personContacts.value = [];

  let contacts = [];

  try {
    let person = null;

    const personId =
      invoice?.person_id ??
      invoice?.person?.id ??
      (typeof invoice?.person === 'number' ? invoice.person : null);

    if (personId) {
      person = await $PersonApiService.getFullDetail(personId);
    } else if (invoice?.customer_token_final) {
      person = await $PersonApiService.getFullDetailByToken(
        invoice.customer_token_final
      );
    }

    contacts = person?.contacts || [];
  } catch (err) {
    console.error(err);
  }

  // Si mentrestant s'ha canviat de factura, descartem la resposta
  if (currentInvoiceId.value !== invoice?.id) return;

  personContacts.value = contacts;

  if (resetEmail) applyDefaultEmail();
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

const defaultSubjectFor = (lang, invoice = props.invoice) =>
  [
    t('invoice', {}, { locale: lang }),
    invoice?.serie_final
  ]
    .filter(Boolean)
    .join(' ');

const subject = ref(
  defaultSubjectFor(
    selectedLang.value
  )
);

const body = ref(
  defaultBodyFor(
    selectedLang.value
  )
);

// ---------------------------------------------------------
// MESSAGE TEMPLATES (origen facturació)
// ---------------------------------------------------------

const messageTemplates = ref([]);
const selectedTemplate = ref(null);
const loadingTemplates = ref(false);
const emailTypeToken = ref(null);

// Plantilla del tipus email de la plantilla seleccionada
const templateContent = ref(null);

const getMessageTemplates = async () => {
  loadingTemplates.value = true;

  try {
    const [origins, emailToken] =
      await Promise.all([
        $ConfiglistApiService.getAll(
          'communication/message-origin'
        ),
        $ConfigProjectApiService.get(
          'message_type_email_token'
        )
      ]);

    emailTypeToken.value = emailToken;

    const billingOrigin =
      (origins?.results || []).find(
        (o) => o.token === BILLING_ORIGIN_TOKEN
      );

    if (!billingOrigin) {
      messageTemplates.value = [];
      return;
    }

    const result =
      await $MessageTemplateApiService.getAll(
        '',
        [],
        1,
        null,
        false,
        billingOrigin.id
      );

    messageTemplates.value =
      (result?.results || [])
        .filter((tpl) => tpl.is_active !== false)
        .map((tpl) => ({
          label: tpl.name || tpl.token,
          value: tpl.id
        }));
  } catch (err) {
    console.error(err);
  } finally {
    loadingTemplates.value = false;
  }
};

const loadTemplateContent = async (templateId) => {
  templateContent.value = null;

  if (!templateId) {
    return;
  }

  try {
    const result =
      await $MessageTemplateApiService
        .getMessageTypeTemplates(templateId);

    // No filtrem per is_active: la UI de plantilles no el gestiona i en
    // desar amb FormData DRF el posa a false (com fa la resta de
    // pantalles de comunicacions, l'ignorem)
    const typeTemplates =
      (result?.results || []).filter(
        (tt) => !tt.unused
      );

    templateContent.value =
      typeTemplates.find(
        (tt) =>
          tt.type?.token ===
          emailTypeToken.value
      ) || null;

    if (!templateContent.value) {
      toast.warning(
        t('billing_block.template_without_email')
      );
    }
  } catch (err) {
    console.error(err);
  }
};

// Omple l'assumpte i el cos amb la plantilla seleccionada
// o, si no n'hi ha, amb els textos per defecte de l'idioma
const applyMessageContent = () => {
  const lang = selectedLang.value;

  subject.value =
    templateContent.value?.subject ||
    defaultSubjectFor(lang);

  body.value =
    templateContent.value?.body ||
    defaultBodyFor(lang);
};

// ---------------------------------------------------------
// COMPANY CONFIG
// ---------------------------------------------------------

const companyConfigs = ref([]);
const selectedCompanyConfig = ref(null);
const loadingCompanyConfigs = ref(false);

const companyConfigFor = (invoice) => {
  const invoiceCompanyId =
    invoice?.company?.id ??
    invoice?.company ??
    invoice?.company_id ??
    null;

  const match = companyConfigs.value.find(
    (c) => c.companyId != null && c.companyId === invoiceCompanyId
  );

  return match?.value ?? companyConfigs.value[0]?.value ?? null;
};

const applyDefaultCompanyConfig = () => {
  selectedCompanyConfig.value = companyConfigFor(props.invoice);
};

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

onMounted(() => {
  getCompanyConfigs();
  getMessageTemplates();
});

// ---------------------------------------------------------
// DRAFTS PER FACTURA
// ---------------------------------------------------------

const drafts = ref({});
const currentInvoiceId = ref(null);

const isSent = computed(() =>
  props.sentIds.includes(props.invoice?.id)
);

const saveDraft = (invoiceId) => {
  if (!invoiceId) return;

  drafts.value[invoiceId] = {
    selectedEmail: selectedEmail.value,
    customEmail: customEmail.value,
    subject: subject.value,
    body: body.value,
    selectedLang: selectedLang.value,
    selectedTemplate: selectedTemplate.value,
    templateContent: templateContent.value,
    selectedCompanyConfig: selectedCompanyConfig.value
  };
};

const initInvoice = async (invoice) => {
  if (!invoice) return;

  // Síncron, abans de qualsevol await
  currentInvoiceId.value = invoice.id;
  applyToAll.value = false; // abans de restaurar valors

  const draft = drafts.value[invoice.id];

  if (draft) {
    selectedEmail.value = draft.selectedEmail;
    customEmail.value = draft.customEmail;
    subject.value = draft.subject;
    body.value = draft.body;
    selectedLang.value = draft.selectedLang;
    selectedTemplate.value = draft.selectedTemplate;
    templateContent.value = draft.templateContent;
    selectedCompanyConfig.value = draft.selectedCompanyConfig;
  } else {
    selectedTemplate.value = null;
    templateContent.value = null;
    selectedLang.value = props.contract?.language || locale.value;

    applyMessageContent();
    applyDefaultEmail();
    applyDefaultCompanyConfig();
  }

  if (!props.contract?.person_contact_email?.email) {
    await loadPersonContacts(invoice, !draft);
  }
};

const onLangChange = () => applyMessageContent();

const onTemplateChange = async () => {
  await loadTemplateContent(selectedTemplate.value);
  applyMessageContent();
};

// Esborrany per defecte d'una factura que no s'ha visitat
const buildDefaultDraft = (invoice) => {
  const lang = props.contract?.language || locale.value;

  return {
    selectedEmail: currentEmail.value || contactEmails.value[0] || OTHER,
    customEmail: '',
    subject: defaultSubjectFor(lang, invoice),
    body: defaultBodyFor(lang),
    selectedLang: lang,
    selectedTemplate: null,
    templateContent: null,
    selectedCompanyConfig: companyConfigFor(invoice)
  };
};

// Factures de la selecció pendents d'enviar (sense comptar l'actual)
const pendingOthers = computed(() =>
  props.invoices.filter(
    (inv) =>
      inv.id !== props.invoice?.id &&
      !props.sentIds.includes(inv.id)
  )
);

// Factures de la selecció pendents d'enviar (incloent l'actual)
const pendingAll = computed(() =>
  props.invoices.filter(
    (inv) => !props.sentIds.includes(inv.id)
  )
);

const applyToAll = ref(false);

// Copia el correu actual a la resta de factures pendents
const applyEmailToOthers = () => {
  saveDraft(currentInvoiceId.value);

  pendingOthers.value.forEach((inv) => {
    const base = drafts.value[inv.id] || buildDefaultDraft(inv);

    drafts.value[inv.id] = {
      ...base,
      selectedEmail: selectedEmail.value,
      customEmail: customEmail.value
    };
  });
};

const onApplyToAllChange = () => {
  if (applyToAll.value) {
    applyEmailToOthers();
    toast.success(t('billing_block.email_applied_to_all'));
  }
};

// Mentre el quadradet està marcat, qualsevol canvi de correu es propaga
watch([selectedEmail, customEmail], () => {
  if (applyToAll.value) applyEmailToOthers();
});

const sendingAll = ref(false);

const sendAll = async () => {
  saveDraft(currentInvoiceId.value);

  const targets = pendingAll.value.map((inv) => {
    const draft = drafts.value[inv.id] || buildDefaultDraft(inv);
    const to =
      (draft.selectedEmail === OTHER
        ? draft.customEmail
        : draft.selectedEmail) || null;

    return { invoice: inv, draft, to };
  });

  if (!targets.length) return;

  if (targets.some((x) => !x.to || !x.draft.selectedCompanyConfig)) {
    toast.error(t('billing_block.error_send_email'));
    return;
  }

  // Agrupem per destinatari + config d'empresa (el remitent ha de ser el mateix)
  const groupsMap = new Map();

  targets.forEach((x) => {
    const key = `${x.to.trim().toLowerCase()}|${x.draft.selectedCompanyConfig}`;

    if (!groupsMap.has(key)) {
      groupsMap.set(key, { to: x.to.trim(), items: [] });
    }

    groupsMap.get(key).items.push(x);
  });

  const groups = [...groupsMap.values()];

  // Confirmació: un correu per grup, amb les factures que hi van dins
  const summary = groups
    .map(
      (g) =>
        `${g.to}: ${g.items.map((x) => x.invoice.serie_final).join(', ')}`
    )
    .join('\n');

  if (
    !window.confirm(
      `${groups.length} ${t('billing_block.emails_to_send')}\n\n${summary}`
    )
  ) {
    return;
  }

  sendingAll.value = true;

  const okIds = [];
  let failed = 0;

  for (const group of groups) {
    const first = group.items[0];

    try {
      if (group.items.length === 1) {
        // Un sol document: l'endpoint actual, sense canvis
        await $InvoiceApiService.sendEmail(first.invoice.id, {
          email: group.to,
          subject: first.draft.subject,
          body: first.draft.body,
          company_config_id: first.draft.selectedCompanyConfig
        });
      } else {
        // Diverses factures al mateix destinatari: un sol correu
        const lang = first.draft.selectedLang;

        await $InvoiceApiService.sendGroupedEmail({
          invoice_ids: group.items.map((x) => x.invoice.id),
          email: group.to,
          subject: `${t('invoices', {}, { locale: lang })} ${group.items
            .map((x) => x.invoice.serie_final)
            .join(', ')}`,
          body: first.draft.body,
          company_config_id: first.draft.selectedCompanyConfig
        });
      }

      group.items.forEach((x) => okIds.push(x.invoice.id));
    } catch (err) {
      console.error(err);
      failed++;
    }
  }

  sendingAll.value = false;

  if (failed) {
    toast.error(`${t('billing_block.error_send_email')} (${failed})`);
  } else {
    toast.success(t('billing_block.correct_send_email'));
  }

  if (okIds.length) emit('sent-all', okIds);
};

// ---------------------------------------------------------
// WATCHERS
// ---------------------------------------------------------

watch(
  () => props.show,
  async (isOpen) => {
    if (!isOpen) {
      drafts.value = {};
      currentInvoiceId.value = null;
      applyToAll.value = false;
      return;
    }

    await initInvoice(props.invoice);
  }
);

// Quan canviem de factura mitjançant les fletxes
watch(
  () => props.invoice,
  async (newInvoice) => {
    if (!props.show || !newInvoice) return;

    // Mateixa factura (p. ex. refetch del pare): no resetegem res
    if (newInvoice.id === currentInvoiceId.value) return;

    saveDraft(currentInvoiceId.value); // ABANS d'initInvoice
    await initInvoice(newInvoice);
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
  if (!invoiceHasPdf(props.invoice)) {
    return;
  }

  try {
    await openInvoicePdf(props.invoice);
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
    !props.invoice?.id ||
    isSent.value
  ) {
    return;
  }

  const invoiceId = props.invoice.id;
  sending.value = true;

  try {
    await $InvoiceApiService.sendEmail(
      invoiceId,
      {
        email: email.value,
        subject: subject.value,
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

    if (props.invoices.length) {
      // Mode agrupat: el pare decideix si passa a la següent o tanca
      emit('sent', invoiceId);
    } else {
      // Ús d'una sola factura (com abans): tanquem
      emit('close');
    }
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
                :disabled="sending || sendingAll"
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
                :disabled="sending || sendingAll"
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
              v-if="invoiceHasPdf(invoice)"
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

          <!-- Aplicar el correu a totes les factures -->
          <label
            v-if="selectedEmail === OTHER && invoices.length > 1"
            class="mt-2 flex items-center gap-2 text-sm text-slate-600 cursor-pointer"
          >
            <input
              type="checkbox"
              v-model="applyToAll"
              @change="onApplyToAllChange"
              :disabled="!customEmail"
              class="w-4 h-4 rounded border-slate-300 text-sky-500 focus:ring-sky-500 disabled:opacity-50"
            />
            {{ t('billing_block.apply_email_to_all') }}
          </label>
        </div>

        <!-- Message template -->
        <div class="mb-8">
          <h4
            class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2"
          >
            {{ t('common.template') }}
          </h4>

          <select
            v-model="selectedTemplate"
            @change="onTemplateChange"
            :disabled="loadingTemplates"
            class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 disabled:opacity-50"
          >
            <option :value="null">
              {{ t('default') }}
            </option>

            <option
              v-for="tpl in messageTemplates"
              :key="tpl.value"
              :value="tpl.value"
            >
              {{ tpl.label }}
            </option>
          </select>
        </div>

        <!-- Email subject -->
        <div class="mb-8">
          <h4
            class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2"
          >
            {{ t('customer_service_block.subject') }}
          </h4>

          <input
            v-model="subject"
            type="text"
            class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
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

            <!-- L'idioma només aplica als textos per defecte -->
            <select
              v-model="selectedLang"
              @change="onLangChange"
              :disabled="!!templateContent"
              class="border border-slate-300 rounded-md text-sm text-slate-700 py-1 px-2 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 disabled:opacity-50"
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

          <!-- Enviar totes les factures pendents -->
          <button
            v-if="invoices.length > 1"
            type="button"
            @click="sendAll"
            :disabled="sending || sendingAll || !pendingAll.length"
            class="button-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon
              v-if="sendingAll"
              name="fa6-solid:spinner"
              class="animate-spin"
            />

            <span
              v-else
              class="flex items-center -space-x-1"
            >
              <Icon
                name="fa6-solid:paper-plane"
                class="text-xs"
              />
              <Icon name="fa6-solid:paper-plane" />
            </span>

            {{ t('billing_block.send_all') }}
            ({{ pendingAll.length }})
          </button>

          <!-- Enviar només aquesta factura -->
          <button
            type="button"
            @click="sendEmail"
            :disabled="
              !email ||
              !selectedCompanyConfig ||
              sending ||
              sendingAll ||
              isSent
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