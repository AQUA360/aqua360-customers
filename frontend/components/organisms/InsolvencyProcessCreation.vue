<script setup>
// Alta d'un procés d'insolvència: persona i dades del procés, canvi de forma de pagament dels
// contractes on és titular, factures emeses des de la data (opcionalment vinculades) i documentació
import { ref, computed, watch, onMounted } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import PersonSearch from '~/components/organisms/PersonSearch.vue';

const props = defineProps({
  personId: { type: Number, default: null },
  startDate: { type: String, default: null },
});

const { t } = useI18n();
const toast = useToast();
const { $InsolvencyProcessApiService, $ConfiglistApiService, $PersonApiService } = useNuxtApp();

const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

const permissions = ref(null);
const person = ref(null);
const showPersonSearch = ref(false);
const kind = ref(null);
const startDate = ref(props.startDate || localToday());
const caseNumber = ref('');
const observation = ref('');
const pendingFiles = ref([]);
const fileInput = ref(null);

const paymentTypes = ref([]);
const preview = ref(null);
const previewLoading = ref(false);
const previewError = ref(false);
const selectedInvoiceIds = ref([]);
const newPaymentTypes = ref({}); // contract_id -> payment_type_id (null = mantenir)
const attemptedSave = ref(false);
const saving = ref(false);

const kindOptions = computed(() => [
  { value: 'second_chance', label: t('insolvency.kinds.second_chance') },
  { value: 'creditors', label: t('insolvency.kinds.creditors') },
]);

const personName = computed(() => {
  if (!person.value) return '';
  return person.value.full_name || [person.value.name, person.value.surname].filter(Boolean).join(' ');
});

// El tipus de procés es proposa segons si la persona és física o jurídica
watch(person, (value) => {
  if (value && !kind.value) kind.value = value.is_juridic ? 'creditors' : 'second_chance';
});

// Previsualització: es descarten les respostes antigues i es buida en canviar persona o data
let previewRequestId = 0;
const loadPreview = async () => {
  const current = ++previewRequestId;
  preview.value = null;
  previewError.value = false;
  selectedInvoiceIds.value = [];
  newPaymentTypes.value = {};
  if (!person.value?.id || !startDate.value) {
    previewLoading.value = false;
    return;
  }
  previewLoading.value = true;
  try {
    const result = await $InsolvencyProcessApiService.preview(person.value.id, startDate.value);
    if (current !== previewRequestId) return;
    preview.value = result;
  } catch (err) {
    if (current !== previewRequestId) return;
    previewError.value = true;
  } finally {
    if (current === previewRequestId) previewLoading.value = false;
  }
};
const debouncedPreview = debounce(loadPreview, 300);
watch([() => person.value?.id, startDate], () => {
  previewLoading.value = !!(person.value?.id && startDate.value);
  preview.value = null;
  debouncedPreview();
});

const allInvoicesSelected = computed(() =>
  !!preview.value?.invoices?.length && selectedInvoiceIds.value.length === preview.value.invoices.length
);
const toggleAllInvoices = () => {
  selectedInvoiceIds.value = allInvoicesSelected.value ? [] : preview.value.invoices.map((invoice) => invoice.id);
};

const paymentTypeOptions = (contract) => paymentTypes.value.map((type) => ({
  ...type,
  // Domiciliar demana compte bancari
  disabled: type.token === 'DIRECT_DEBIT' && !contract.has_iban,
}));

const canSave = computed(() =>
  !!person.value && !!kind.value && !!startDate.value
  && !!preview.value && !previewLoading.value && !previewError.value
  && !preview.value.open_process_id && !saving.value
);

const pickPerson = (item) => {
  person.value = item;
  showPersonSearch.value = false;
};

const addFiles = (event) => {
  pendingFiles.value.push(...Array.from(event.target.files || []));
  event.target.value = '';
};

const removeFile = (index) => pendingFiles.value.splice(index, 1);

const save = async () => {
  attemptedSave.value = true;
  if (!canSave.value) return;
  if (!confirm(t('insolvency.confirm_create'))) return;
  saving.value = true;
  try {
    const paymentChanges = Object.entries(newPaymentTypes.value)
      .filter(([, typeId]) => typeId)
      .map(([contractId, typeId]) => ({ contract_id: parseInt(contractId), payment_type_id: typeId }));
    const process = await $InsolvencyProcessApiService.create({
      person_id: person.value.id,
      kind: kind.value,
      start_date: startDate.value,
      case_number: caseNumber.value?.trim() || null,
      observation: observation.value?.trim() || null,
      invoice_ids: selectedInvoiceIds.value,
      payment_changes: paymentChanges,
    });
    // El procés ja és creat: si falla algun document, es pot tornar a pujar des del detall
    for (const file of pendingFiles.value) {
      try {
        await $InsolvencyProcessApiService.uploadDocument(process.id, file);
      } catch (err) {
        console.error(err);
      }
    }
    toast.success(t('insolvency.created'));
    return navigateTo({ path: '/contract/persons/', query: { id: person.value.id } });
  } catch (err) {
    console.error(err);
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  try {
    permissions.value = await $InsolvencyProcessApiService.getPermissions();
  } catch (err) {
    permissions.value = null;
  }
  if (!permissions.value?.can_add) {
    toast.error(t('common.no_permissions'));
    return navigateTo(props.personId ? { path: '/contract/persons/', query: { id: props.personId } } : '/contract/persons/');
  }
  try {
    const res = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    paymentTypes.value = (res.results || res || []).filter((type) => type.token !== 'BALANCE');
  } catch (err) {
    console.error(err);
  }
  if (props.personId) {
    try {
      person.value = await $PersonApiService.getDetail(props.personId);
    } catch (err) {
      console.error(err);
    }
  }
});
</script>

<template>
  <div class="max-w-5xl">
    <!-- Persona i dades del procés -->
    <section class="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <div class="grid md:grid-cols-2 gap-3">
        <div class="md:col-span-2">
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('insolvency.person') }}
          </label>
          <div class="flex items-center gap-2">
            <AtomsPersonBadge v-if="person" :person="person" class="font-bold max-w-md" />
            <button type="button" class="button-default-xs text-sm flex items-center gap-1"
              :class="{ 'border-red-400': attemptedSave && !person }" @click="showPersonSearch = true">
              <Icon :name="person ? 'fa6-solid:arrow-right-arrow-left' : 'fa6-solid:magnifying-glass'" />
              {{ person ? t('insolvency.change_person') : t('insolvency.select_person') }}
            </button>
          </div>
          <p v-if="preview?.open_process_id" class="mt-2 text-sm text-red-700 flex items-center gap-2">
            <Icon name="fa6-solid:triangle-exclamation" />
            {{ t('insolvency.already_open') }}
            <NuxtLink :to="{ path: '/contract/persons/', query: { id: person.id } }"
              class="underline">{{ t('insolvency.view_process') }}</NuxtLink>
          </p>
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('insolvency.kind') }}
          </label>
          <select v-model="kind" class="input w-full text-sm" :class="{ 'border-red-400': attemptedSave && !kind }">
            <option :value="null" disabled>-</option>
            <option v-for="option in kindOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" for="insolvency_start_date">
            {{ t('insolvency.start_date') }}
          </label>
          <input id="insolvency_start_date" v-model="startDate" type="date" class="input w-full text-sm"
            :class="{ 'border-red-400': attemptedSave && !startDate }" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" for="insolvency_case">
            {{ t('insolvency.case_number') }}
          </label>
          <input id="insolvency_case" v-model="caseNumber" type="text" class="input w-full text-sm" />
        </div>

        <div class="md:col-span-2">
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" for="insolvency_observation">
            {{ t('insolvency.observation') }}
          </label>
          <textarea id="insolvency_observation" v-model="observation" rows="2" class="input w-full text-sm"></textarea>
        </div>
      </div>
    </section>

    <div v-if="previewLoading" class="mt-4 flex items-center gap-2 text-slate-500">
      <Icon name="fa6-solid:spinner" class="animate-spin" />
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="previewError"
      class="mt-4 p-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded flex items-center gap-2">
      <Icon name="fa6-solid:triangle-exclamation" />
      <span>{{ t('common.error_load') }}</span>
      <button type="button" class="underline" @click="loadPreview">{{ t('common.load_again') }}</button>
    </div>

    <template v-else-if="preview">
      <!-- Contractes: canvi de forma de pagament -->
      <section class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
        <h2 class="font-semibold text-slate-700">{{ t('insolvency.contracts') }} ({{ preview.contracts.length }})</h2>
        <p class="text-sm text-slate-500 mb-2">{{ t('insolvency.contracts_help') }}</p>
        <div v-if="preview.contracts.length" class="rounded-md border border-gray-300 divide-y bg-white">
          <div class="grid grid-cols-[1fr,1fr,1.2fr,1.5fr] divide-x text-sm leading-4">
            <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.contract') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('common.status') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.current_payment_type') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.new_payment_type') }}</span>
          </div>
          <div v-for="contract in preview.contracts" :key="contract.id"
            class="grid grid-cols-[1fr,1fr,1.2fr,1.5fr] divide-x text-sm leading-4 items-center">
            <span class="footering text-slate-800 p-2">{{ contract.token }}</span>
            <span class="footering text-slate-500 p-2">{{ contract.status_name || '-' }}</span>
            <span class="footering text-slate-500 p-2">
              {{ contract.payment_type?.name || '-' }}
              <span v-if="!contract.has_iban" class="block text-xs text-slate-400">{{ t('insolvency.no_iban') }}</span>
            </span>
            <span class="p-1.5">
              <select v-model="newPaymentTypes[contract.id]" class="input w-full text-sm !py-1">
                <option :value="undefined">{{ t('insolvency.keep') }}</option>
                <option v-for="type in paymentTypeOptions(contract)" :key="type.id" :value="type.id"
                  :disabled="type.disabled || type.id === contract.payment_type?.id">
                  {{ type.name }}
                </option>
              </select>
            </span>
          </div>
        </div>
        <div v-else class="footering text-slate-500 p-2">{{ t('insolvency.no_contracts') }}</div>
      </section>

      <!-- Factures emeses des de la data -->
      <section class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
        <h2 class="font-semibold text-slate-700">{{ t('insolvency.invoices_since') }} ({{ preview.invoices.length }})</h2>
        <p class="text-sm text-slate-500 mb-2">{{ t('insolvency.invoices_help') }}</p>
        <div v-if="preview.invoices.length" class="rounded-md border border-gray-300 divide-y bg-white">
          <div class="grid grid-cols-[40px,1.2fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4">
            <span class="p-2 flex justify-center">
              <input type="checkbox" :checked="allInvoicesSelected" @change="toggleAllInvoices" />
            </span>
            <span class="p-2 pl-3 text-slate-600">{{ t('invoice') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('common.date') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.contract') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('common.total') }}</span>
            <span class="p-2 pl-3 text-slate-600">{{ t('common.status') }}</span>
          </div>
          <label v-for="invoice in preview.invoices" :key="invoice.id"
            class="grid grid-cols-[40px,1.2fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4 cursor-pointer hover:bg-slate-50">
            <span class="p-2 flex justify-center">
              <input type="checkbox" v-model="selectedInvoiceIds" :value="invoice.id" />
            </span>
            <span class="footering text-slate-800 p-2">{{ invoice.serie_final || '-' }}</span>
            <span class="footering text-slate-500 p-2">{{ formatDate(invoice.issue_date) }}</span>
            <span class="footering text-slate-500 p-2">{{ invoice.contract_token || '-' }}</span>
            <span class="footering text-slate-500 p-2">{{ formatMoneyWithCurrency(invoice.total_final) }}</span>
            <span class="footering text-slate-500 p-2">{{ invoice.status_name || '-' }}</span>
          </label>
        </div>
        <div v-else class="footering text-slate-500 p-2">{{ t('insolvency.no_invoices') }}</div>
      </section>
    </template>

    <!-- Documentació (es puja en crear el procés) -->
    <section class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-slate-700">{{ t('insolvency.documents') }}</h2>
        <button type="button" class="button-primary !px-2.5 !py-1 text-xs flex items-center" @click="fileInput?.click()">
          <Icon name="fa6-solid:plus" />
          <span class="ml-1">{{ t('insolvency.upload_document') }}</span>
        </button>
        <input ref="fileInput" type="file" multiple class="hidden" @change="addFiles" />
      </div>
      <ul v-if="pendingFiles.length" class="mt-2 rounded-md border border-gray-300 divide-y text-sm">
        <li v-for="(file, index) in pendingFiles" :key="`${file.name}-${index}`" class="flex items-center justify-between p-2">
          <span class="truncate text-slate-700">{{ file.name }}</span>
          <button type="button" class="px-1.5 py-1 text-gray-400 hover:text-red-500" @click="removeFile(index)">
            <Icon name="fa6-solid:trash" />
          </button>
        </li>
      </ul>
      <div v-else class="footering text-slate-500 p-2">{{ t('insolvency.no_documents') }}</div>
    </section>

    <div class="mt-4 flex justify-end">
      <button class="button-primary flex items-center gap-2" :disabled="!canSave" @click="save">
        <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': saving }" />
        {{ t('insolvency.save') }}
      </button>
    </div>
  </div>

  <!-- Cerca de persona al panell lateral -->
  <div role="region"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[48vw] z-50"
    :class="{ 'translate-x-0': showPersonSearch, 'translate-x-full': !showPersonSearch }">
    <div class="mb-3 px-3">
      <button @click="showPersonSearch = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 pr-4 overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 100px)' }">
      <PersonSearch v-if="showPersonSearch" :allow-create="false" :title="t('insolvency.select_person')"
        person-label="insolvency.person" @saved="pickPerson" />
    </div>
  </div>
</template>
