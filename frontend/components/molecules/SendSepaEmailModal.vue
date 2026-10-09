<script setup>
// components/molecules/SendSepaEmailModal.vue
// Envia per correu al client el document SEPA (autorització de domiciliació)
// ja generat. El backend crea una Communication amb el PDF adjunt i l'envia.
import { computed, ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t, locale } = useI18n();
const toast = useToast();
const { $GeneralPaymentApiService, $ConfiglistApiService, $PersonApiService } = useNuxtApp();

const languages = AVAILABLE_LANGUAGES;

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  /** Id del GeneralPaymentSepaDocument retornat en generar el document. */
  sepaDocumentId: {
    type: Number,
    default: null,
  },
  /** Contracte o sol·licitud al qual pertany el document. */
  contract: {
    type: Object,
    default: null,
  },
  /** true si `contract` és una sol·licitud (ContractRequest). */
  isRequest: {
    type: Boolean,
    default: false,
  },
  /** Persona (objecte o id) de qui es proposen els correus de contacte. */
  person: {
    type: [Object, Number],
    default: null,
  },
});

const emit = defineEmits(['close', 'sent']);

const OTHER = '__other__';

// ---------------------------------------------------------
// CONTACTS
// ---------------------------------------------------------

const personContacts = ref([]);

const currentEmail = computed(() => {
  if (props.contract?.person_contact_email?.email) {
    return props.contract.person_contact_email.email;
  }
  const contacts = [...(props.contract?.contacts || []), ...personContacts.value];
  return contacts.find((c) => c.email && c.is_default)?.email || null;
});

const contactEmails = computed(() => {
  const emails = [...(props.contract?.contacts || []), ...personContacts.value]
    .map((c) => c.email)
    .filter(Boolean);
  if (currentEmail.value) {
    emails.unshift(currentEmail.value);
  }
  return [...new Set(emails)];
});

const selectedEmail = ref(null);
const customEmail = ref('');

const applyDefaultEmail = () => {
  selectedEmail.value = currentEmail.value || contactEmails.value[0] || OTHER;
  customEmail.value = '';
};

const loadPersonContacts = async () => {
  personContacts.value = [];
  const personId = props.person?.id ?? props.person
    ?? props.contract?.holder?.id ?? props.contract?.holder ?? null;

  if (personId && typeof personId === 'number') {
    try {
      const person = await $PersonApiService.getFullDetail(personId);
      personContacts.value = person?.contacts || [];
    } catch (err) {
      console.error(err);
    }
  }
  applyDefaultEmail();
};

const email = computed(() =>
  (selectedEmail.value === OTHER ? customEmail.value : selectedEmail.value) || null
);

// ---------------------------------------------------------
// LANGUAGE / SUBJECT / BODY
// ---------------------------------------------------------

const selectedLang = ref(locale.value);
const subject = ref('');
const body = ref('');

const applyDefaultTexts = (lang) => {
  subject.value = t('contract_block.sepa_email_default_subject', {}, { locale: lang });
  body.value = t('contract_block.sepa_email_default_body', {}, { locale: lang });
};

watch(selectedLang, applyDefaultTexts);

// ---------------------------------------------------------
// COMPANY CONFIG
// ---------------------------------------------------------

const companyConfigs = ref([]);
// null: el backend la dedueix de l'explotació del contracte
const selectedCompanyConfig = ref(null);
const loadingCompanyConfigs = ref(false);

const getCompanyConfigs = async () => {
  loadingCompanyConfigs.value = true;
  try {
    const result = await $ConfiglistApiService.getAll('service/company-config');
    companyConfigs.value = (result?.results || []).map((config) => ({
      label: config.name,
      value: config.id,
    }));
  } catch (err) {
    console.error(err);
  } finally {
    loadingCompanyConfigs.value = false;
  }
};

onMounted(getCompanyConfigs);

watch(
  () => props.show,
  (isOpen) => {
    if (!isOpen) return;
    selectedLang.value = props.contract?.language || locale.value;
    applyDefaultTexts(selectedLang.value);
    selectedCompanyConfig.value = null;
    applyDefaultEmail();
    loadPersonContacts();
  }
);

// ---------------------------------------------------------
// SEND
// ---------------------------------------------------------

const sending = ref(false);

const handleClose = () => {
  if (sending.value) return;
  emit('close');
};

const sendEmail = async () => {
  if (!email.value || !props.sepaDocumentId || !props.contract?.id) return;

  sending.value = true;
  try {
    const response = await $GeneralPaymentApiService.sendSepaEmail(props.sepaDocumentId, {
      email: email.value,
      subject: subject.value,
      body: body.value,
      contract_id: props.contract.id,
      is_request: props.isRequest,
      company_config_id: selectedCompanyConfig.value,
    });
    toast.success(t('contract_block.sepa_email_sent'));
    emit('sent', response);
    emit('close');
  } catch (err) {
    console.error(err);
    toast.error(t('contract_block.sepa_email_error'));
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <Teleport to="body">
    <div v-if="show">
      <!-- Modal Backdrop -->
      <div class="fixed inset-0 bg-black bg-opacity-50 z-40" @click="handleClose" />

      <!-- Modal Content -->
      <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative pointer-events-auto">
          <button type="button" @click="handleClose" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <!-- Header -->
          <div class="mb-6">
            <h3 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2">
              <Icon name="fa6-solid:envelope" class="text-slate-500" />
              {{ t('contract_block.sepa_send_email') }}
            </h3>
            <p v-if="contract?.token" class="text-sm text-slate-500">
              {{ t('contract') }}: <span class="font-medium text-slate-700">{{ contract.token }}</span>
            </p>
          </div>

          <!-- Company config -->
          <div class="mb-6">
            <h4 class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
              {{ t('service_block.company_config') }}
            </h4>
            <select v-model="selectedCompanyConfig" :disabled="loadingCompanyConfigs"
              class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 disabled:opacity-50">
              <option :value="null">{{ t('contract_block.sepa_email_default_sender') }}</option>
              <option v-for="config in companyConfigs" :key="config.value" :value="config.value">
                {{ config.label }}
              </option>
            </select>
          </div>

          <!-- Contact email -->
          <div class="mb-6">
            <h4 class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
              {{ t('common.email_long') }}
            </h4>
            <select v-model="selectedEmail"
              class="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500">
              <option v-for="opt in contactEmails" :key="opt" :value="opt">{{ opt }}</option>
              <option :value="OTHER">{{ t('common.other') }}</option>
            </select>
            <input v-if="selectedEmail === OTHER" v-model="customEmail" type="email" :placeholder="t('common.email_long')"
              class="w-full border border-slate-300 rounded-lg p-2 mt-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500" />
          </div>

          <!-- Subject / body -->
          <div class="mb-8">
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-slate-500 uppercase tracking-wide">
                {{ t('billing_block.email_body') }}
              </h4>
              <select v-model="selectedLang" :title="t('common.language')"
                class="border border-slate-300 rounded-md text-sm text-slate-700 py-1 px-2 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500">
                <option v-for="lang in languages" :key="lang.code" :value="lang.code">{{ t(lang.name) }}</option>
              </select>
            </div>
            <input v-model="subject" type="text" :placeholder="t('contract_block.sepa_email_subject')"
              class="w-full border border-slate-300 rounded-lg p-2 mb-2 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500" />
            <textarea v-model="body" rows="6"
              class="w-full border border-slate-300 rounded-lg p-3 text-sm text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 resize-y" />
          </div>

          <!-- Footer -->
          <div class="flex justify-end gap-3">
            <button type="button" @click="handleClose" :disabled="sending"
              class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors">
              {{ t('common.close') }}
            </button>
            <button type="button" @click="sendEmail" :disabled="!email || !sepaDocumentId || sending"
              class="button-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:paper-plane'" :class="{ 'animate-spin': sending }" />
              {{ t('common.send') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
