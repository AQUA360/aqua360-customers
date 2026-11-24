<script setup>
// Detall d'un procés d'insolvència: dades, factures (totes les emeses des de la data), contractes
// (gestió d'impagats i forma de pagament), documentació i tancament
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate, formatDateTime } from '~/utils/date';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';

const props = defineProps({
  id: { type: Number, required: true },
  permissions: { type: Object, default: null },
  // Dins la pestanya de la persona: capçalera compacta en lloc del títol de regió
  embedded: { type: Boolean, default: false },
});

const emit = defineEmits(['change']);

const { t } = useI18n();
const toast = useToast();
const { $InsolvencyProcessApiService, $DocumentManagerApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const data = ref(null);
const uploading = ref(false);
const fileInput = ref(null);

const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

// Tancament: data i, si s'hi va canviar, tornar a la forma de pagament anterior
const showClose = ref(false);
const closeDate = ref(localToday());
const restorePayment = ref(false);
const closing = ref(false);
const paymentChanges = computed(() => (data.value?.contracts || []).filter((row) => row.new_payment_type_name));
const invalidCloseDate = computed(() => !closeDate.value || (!!data.value?.start_date && closeDate.value < data.value.start_date));

const getData = async () => {
  const currentId = props.id;
  showClose.value = false;
  pending.value = true;
  error.value = null;
  try {
    const result = await $InsolvencyProcessApiService.getDetail(currentId);
    if (currentId === props.id) data.value = result;
  } catch (err) {
    if (currentId === props.id) error.value = err;
  } finally {
    if (currentId === props.id) pending.value = false;
  }
};

const userName = (user) => {
  if (!user) return '-';
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username;
};

const openClose = () => {
  closeDate.value = localToday();
  restorePayment.value = false;
  showClose.value = true;
};

const closeProcess = async () => {
  if (invalidCloseDate.value || closing.value) return;
  if (!confirm(t('insolvency.confirm_close'))) return;
  const currentId = props.id;
  closing.value = true;
  try {
    const result = await $InsolvencyProcessApiService.close(currentId, {
      end_date: closeDate.value,
      restore_payment: restorePayment.value,
    });
    if (currentId !== props.id) return;
    data.value = result;
    showClose.value = false;
    emit('change');
  } catch (err) {
    console.error(err);
  } finally {
    closing.value = false;
  }
};

const uploadDocument = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    data.value = await $InsolvencyProcessApiService.uploadDocument(props.id, file);
    toast.success(t('common.doc_correct_upload'));
  } catch (err) {
    console.error(err);
  } finally {
    uploading.value = false;
    event.target.value = '';
  }
};

const showDocument = async (document) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(document.id);
    window.open(file.file_url, '_blank');
  } catch (err) {
    console.error(err);
  }
};

onMounted(getData);
watch(() => props.id, getData);
</script>

<template>
  <div class="region__content" :class="{ 'pb-24': !embedded }">
    <div v-if="pending" class="footering text-slate-500 p-2">{{ t('common.loading') }}...</div>
    <div v-else-if="error" class="footering text-red-600 p-2">{{ t('common.error_load') }}</div>
    <template v-else-if="data">
      <div class="flex justify-between relative" :class="{ 'min-h-[32px] mb-2': embedded }">
        <H1Region v-if="!embedded" class="mb-3">{{ t('insolvency.title') }}</H1Region>
        <h2 v-else class="font-semibold text-slate-700 flex items-center gap-2">
          <Icon name="fa6-solid:scale-balanced" :class="data.status === 'open' ? 'text-red-600' : 'text-slate-400'" />
          {{ t(`insolvency.kinds.${data.kind}`) }} · {{ formatDate(data.start_date) }}
        </h2>
        <OptionsDropdown v-if="permissions?.can_add && data.status === 'open'" id="InsolvencyProcessRegionOptions">
          <DropdownOption @click="openClose">
            <Icon name="fa6-solid:lock" class="display-inline mr-2" />
            {{ t('insolvency.close') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="showClose" class="mb-3 rounded-md border border-slate-300 bg-slate-50 p-3 text-sm">
        <p class="text-slate-600 mb-2">{{ t('insolvency.close_help') }}</p>
        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" for="insolvency_close_date">
              {{ t('insolvency.closed_at') }}
            </label>
            <input id="insolvency_close_date" v-model="closeDate" type="date" :min="data.start_date" class="input text-sm"
              :class="{ 'border-red-400': invalidCloseDate }" />
          </div>
          <label v-if="paymentChanges.length" class="flex items-center gap-2 pb-2 text-slate-700 cursor-pointer">
            <input v-model="restorePayment" type="checkbox" />
            {{ t('insolvency.restore_payment') }}
          </label>
          <div class="ml-auto flex gap-2">
            <button type="button" class="button-default-xs text-sm" @click="showClose = false">{{ t('insolvency.cancel') }}</button>
            <button type="button" class="button-primary !px-2.5 !py-1 text-sm flex items-center gap-1"
              :disabled="invalidCloseDate || closing" @click="closeProcess">
              <Icon :name="closing ? 'fa6-solid:spinner' : 'fa6-solid:lock'" :class="{ 'animate-spin': closing }" />
              {{ t('insolvency.confirm_close_button') }}
            </button>
          </div>
        </div>
      </div>
      <p v-else-if="data.status === 'open'" class="mb-3 text-sm text-red-700 flex items-center gap-2">
        <Icon name="fa6-solid:circle-info" />
        {{ t('insolvency.open_process_help') }}
      </p>

      <div class="grid grid-cols-2 gap-x-3">
        <FieldDetail :label="t('insolvency.person')" :value="`${data.person_name} (${data.person_token})`" />
        <FieldDetail :label="t('insolvency.status')">
          <span class="inline-block rounded px-2 py-0.5 text-xs w-fit"
            :class="data.status === 'open' ? 'badge-red' : 'badge-gray'">
            {{ t(`insolvency.statuses.${data.status}`) }}
          </span>
        </FieldDetail>
        <FieldDetail :label="t('insolvency.kind')" :value="t(`insolvency.kinds.${data.kind}`)" />
        <FieldDetail :label="t('insolvency.start_date')" :value="formatDate(data.start_date)" />
        <FieldDetail :label="t('insolvency.case_number')" :value="data.case_number || '-'" />
        <FieldDetail :label="t('insolvency.user')" :value="userName(data.user)" />
        <FieldDetail :label="t('insolvency.created_at')" :value="formatDateTime(data.created_at)" />
        <!-- La data de tancament triada; el moment de l'operació va amb qui l'ha fet -->
        <FieldDetail v-if="data.closed_at" :label="t('insolvency.closed_at')" :value="formatDate(data.end_date)" />
        <FieldDetail v-if="data.closed_at" :label="t('insolvency.closed_by')"
          :value="`${userName(data.closed_by)} · ${formatDateTime(data.closed_at)}`" />
        <FieldDetail v-if="data.observation" class="col-span-2" :label="t('insolvency.observation')">
          <span class="whitespace-pre-line">{{ data.observation }}</span>
        </FieldDetail>
      </div>

      <h2 class="mt-4 mb-1 font-semibold text-slate-700">{{ t('insolvency.invoices') }} ({{ data.invoices.length }})</h2>
      <div v-if="data.invoices.length" class="rounded-md border border-gray-300 divide-y bg-white">
        <div class="grid grid-cols-[1.2fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4">
          <span class="p-2 pl-3 text-slate-600">{{ t('invoice') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('common.date') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.contract') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('common.total') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('common.status') }}</span>
        </div>
        <div v-for="invoice in data.invoices" :key="invoice.id"
          class="grid grid-cols-[1.2fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4">
          <span class="footering text-slate-800 p-2">{{ invoice.serie_final || '-' }}</span>
          <span class="footering text-slate-500 p-2">{{ formatDate(invoice.issue_date) }}</span>
          <span class="footering text-slate-500 p-2">{{ invoice.contract_token || '-' }}</span>
          <span class="footering text-slate-500 p-2">{{ formatMoneyWithCurrency(invoice.total_final) }}</span>
          <span class="footering text-slate-500 p-2">{{ invoice.status_name || '-' }}</span>
        </div>
      </div>
      <div v-else class="footering text-slate-500 p-2">{{ t('common.no_records') }}</div>

      <h2 class="mt-4 mb-1 font-semibold text-slate-700">{{ t('insolvency.contracts') }} ({{ data.contracts.length }})</h2>
      <div v-if="data.contracts.length" class="rounded-md border border-gray-300 divide-y bg-white">
        <div class="grid grid-cols-[1fr,1.3fr,1.6fr] divide-x text-sm leading-4">
          <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.contract') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.previous_debt_management') }}</span>
          <span class="p-2 pl-3 text-slate-600">{{ t('insolvency.payment_changes') }}</span>
        </div>
        <div v-for="row in data.contracts" :key="row.id" class="grid grid-cols-[1fr,1.3fr,1.6fr] divide-x text-sm leading-4">
          <span class="footering text-slate-800 p-2">{{ row.contract_token }}</span>
          <span class="footering text-slate-500 p-2">
            {{ row.previous_debt_management_name || '-' }}
            <span v-if="row.debt_management_restored" class="ml-1 inline-block rounded px-1.5 text-xs badge-gray">
              {{ t('insolvency.restored') }}
            </span>
          </span>
          <span class="footering text-slate-500 p-2">
            <template v-if="row.new_payment_type_name">
              {{ row.previous_payment_type_name || '-' }}
              <Icon name="fa6-solid:arrow-right" class="mx-1 text-slate-400" />
              {{ row.new_payment_type_name }}
              <span v-if="row.payment_restored" class="ml-1 inline-block rounded px-1.5 text-xs badge-gray">
                {{ t('insolvency.restored') }}
              </span>
            </template>
            <template v-else>-</template>
          </span>
        </div>
      </div>
      <div v-else class="footering text-slate-500 p-2">{{ t('common.no_records') }}</div>

      <div class="mt-4 mb-1 flex items-center justify-between">
        <h2 class="font-semibold text-slate-700">{{ t('insolvency.documents') }} ({{ data.documents.length }})</h2>
        <template v-if="permissions?.can_add">
          <button type="button" class="button-primary !px-2.5 !py-1 text-xs flex items-center" :disabled="uploading"
            @click="fileInput?.click()">
            <Icon :name="uploading ? 'fa6-solid:spinner' : 'fa6-solid:plus'" :class="{ 'animate-spin': uploading }" />
            <span class="ml-1">{{ t('insolvency.upload_document') }}</span>
          </button>
          <input ref="fileInput" type="file" class="hidden" @change="uploadDocument" />
        </template>
      </div>
      <ul v-if="data.documents.length" class="rounded-md border border-gray-300 divide-y bg-white text-sm">
        <li v-for="document in data.documents" :key="document.id" class="flex items-center justify-between p-2">
          <span class="text-slate-700 truncate">{{ document.document_name }}</span>
          <button type="button" class="text-sky-500 hover:underline flex items-center gap-1" @click="showDocument(document)">
            <Icon name="fa6-regular:file" />
            {{ t('common.show') }}
          </button>
        </li>
      </ul>
      <div v-else class="footering text-slate-500 p-2">{{ t('insolvency.no_documents') }}</div>
    </template>
  </div>
</template>
