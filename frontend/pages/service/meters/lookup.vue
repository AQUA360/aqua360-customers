<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import MeterLookupModal from '~/components/molecules/MeterLookupModal.vue';

const LOOKUP_CODES_KEY = 'meter_lookup_codes';

const { t } = useI18n();
const toast = useToast();
const router = useRouter();
const { $MeterApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const codes = ref([]);
const found = ref([]);
const notFound = ref([]);
const foundCount = ref(0);
const notFoundCount = ref(0);

const showLookupModal = ref(false);
const lookupModalRef = ref(null);

const downloadingCsv = ref(false);
const csvExportProgress = ref(0);
const csvExportTaskId = ref(null);
let csvExportInterval = null;

const hasResults = computed(() => found.value.length > 0 || notFound.value.length > 0);

const activeTab = ref('found');

const setActiveTab = (tab) => {
  activeTab.value = tab;
};

const selectDefaultTab = () => {
  if (found.value.length) {
    activeTab.value = 'found';
  } else if (notFound.value.length) {
    activeTab.value = 'not_found';
  } else {
    activeTab.value = 'found';
  }
};

const copyNotFoundCodes = async () => {
  if (!notFound.value.length) return;
  const text = notFound.value.join('\n');
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'absolute';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    toast.success(t('service_block.meter_lookup_copied'));
  } catch (err) {
    console.error(err);
    toast.error(t('service_block.meter_lookup_copy_error'));
  }
};

const formatContracts = (contracts) => {
  if (!contracts?.length) return '-';
  return contracts
    .map((c) => {
      const parts = [c.token];
      if (c.status) parts.push(c.status);
      if (c.facturable === true) parts.push(t('common.yes'));
      else if (c.facturable === false) parts.push(t('common.no'));
      return parts.filter(Boolean).join(' · ');
    })
    .join('; ');
};

const formatLastReading = (reading) => {
  if (!reading) return '-';
  const parts = [];
  if (reading.reading_date) parts.push(formatDate(reading.reading_date));
  if (reading.reading_value != null) parts.push(String(reading.reading_value));
  if (reading.consumption != null) parts.push(`${t('consumption')}: ${reading.consumption}`);
  if (reading.batch_token) parts.push(reading.batch_token);
  return parts.join(' · ') || '-';
};

const loadCodesFromStorage = () => {
  try {
    const raw = sessionStorage.getItem(LOOKUP_CODES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((c) => typeof c === 'string' && c.trim()) : [];
  } catch {
    return [];
  }
};

const saveCodesToStorage = (list) => {
  sessionStorage.setItem(LOOKUP_CODES_KEY, JSON.stringify(list));
};

const fetchLookup = async (codesList) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $MeterApiService.lookupByCodes(codesList);
    found.value = data.found || [];
    notFound.value = data.not_found || [];
    foundCount.value = data.found_count ?? found.value.length;
    notFoundCount.value = data.not_found_count ?? notFound.value.length;
    selectDefaultTab();
  } catch (err) {
    error.value = err;
    toast.error(t('service_block.meter_lookup_error'));
  } finally {
    pending.value = false;
  }
};

const handleLookupSearch = async (codesList) => {
  if (!codesList?.length) return;
  saveCodesToStorage(codesList);
  codes.value = codesList;
  showLookupModal.value = false;
  lookupModalRef.value?.setSearching(false);
  await fetchLookup(codesList);
};

const exportCsv = async () => {
  if (downloadingCsv.value || !codes.value.length) return;
  downloadingCsv.value = true;
  csvExportProgress.value = 0;

  try {
    const response = await $MeterApiService.lookupByCodesCsv(codes.value);

    if (response && response.task_id) {
      csvExportTaskId.value = response.task_id;

      csvExportInterval = setInterval(async () => {
        try {
          const res = await $apiManager.checkTask(csvExportTaskId.value);
          if (!res) return;

          if (res.state === 'PENDING' || res.state === 'RUNNING') {
            csvExportProgress.value = res.percent || 0;
          } else if (res.state === 'SUCCESS') {
            clearInterval(csvExportInterval);
            csvExportProgress.value = 100;

            if (res.result?.document_id) {
              const fileBlob = await $DocumentManagerApiService.viewDocument(res.result.document_id);
              const url = window.URL.createObjectURL(fileBlob);
              const a = document.createElement('a');
              a.href = url;
              a.download = res.result.filename || `meter_lookup_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              window.URL.revokeObjectURL(url);
              toast.success(t('common.export_completed'));
            } else {
              toast.error(t('common.export_error'));
            }
            downloadingCsv.value = false;
            csvExportTaskId.value = null;
          } else if (res.state === 'FAILURE') {
            clearInterval(csvExportInterval);
            toast.error(res.error || t('common.export_error'));
            downloadingCsv.value = false;
            csvExportTaskId.value = null;
          }
        } catch (pollErr) {
          clearInterval(csvExportInterval);
          console.error(pollErr);
          toast.error(t('common.export_error'));
          downloadingCsv.value = false;
          csvExportTaskId.value = null;
        }
      }, 2000);
    } else {
      throw new Error('No task_id');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.export_error'));
    downloadingCsv.value = false;
    csvExportTaskId.value = null;
  }
};

onMounted(async () => {
  try {
    const permissions = await $MeterApiService.getPermissions();
    if (!permissions?.can_view) {
      toast.error(t('common.no_permissions'));
      return navigateTo('/');
    }
  } catch {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }

  const stored = loadCodesFromStorage();
  if (!stored.length) {
    pending.value = false;
    showLookupModal.value = true;
    return;
  }
  codes.value = stored;
  await fetchLookup(stored);
});

onUnmounted(() => {
  if (csvExportInterval) clearInterval(csvExportInterval);
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2 gap-2 flex-wrap">
      <div class="flex items-center gap-3">
        <button type="button" class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded"
          :title="t('service_block.meter_lookup_back')" @click="router.push('/service/meters/')">
          <Icon name="fa6-solid:arrow-left" class="text-slate-500" />
        </button>
        <H1>{{ t('service_block.meter_lookup_title') }}</H1>
      </div>
      <div class="flex gap-2">
        <button type="button" class="button-default flex items-center gap-1.5"
          @click="showLookupModal = true"
          :title="t('service_block.meter_lookup_new_search')">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
          <span class="text-sm">{{ t('service_block.meter_lookup_new_search') }}</span>
        </button>
        <button type="button" class="button-default flex items-center gap-1.5"
          @click="exportCsv" :disabled="downloadingCsv || !codes.length"
          :title="t('export_csv')">
          <Icon :name="downloadingCsv ? 'fa6-solid:spinner' : 'fa6-solid:file-csv'" class="text-slate-500"
            :class="{ 'animate-spin': downloadingCsv }" />
          <span v-if="downloadingCsv" class="text-xs text-slate-500 font-semibold">
            {{ csvExportProgress }}%
          </span>
          <span v-else class="text-sm">{{ t('export_csv') }}</span>
        </button>
      </div>
    </div>

    <div v-if="pending">
      <AppLoading :text="t('common.loading')" />
    </div>

    <div v-else-if="error" class="my-3">
      <p class="text-red-600">{{ error.message || t('service_block.meter_lookup_error') }}</p>
      <button type="button" class="underline text-sky-500 hover:no-underline mt-2"
        @click="fetchLookup(codes)" v-if="codes.length">
        {{ t('common.load_again') }}
      </button>
    </div>

    <div v-else-if="!hasResults && !codes.length" class="my-6 text-slate-600">
      <p>{{ t('service_block.meter_lookup_empty') }}</p>
    </div>

    <template v-else>
      <div class="flex flex-wrap gap-3 mb-3 text-sm">
        <span class="px-3 py-1 rounded bg-slate-100 text-slate-700">
          {{ t('service_block.meter_lookup_codes_count', { count: codes.length }) }}
        </span>
      </div>

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_found" @click.prevent="setActiveTab('found')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'found', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'found' }">
            <Icon name="fa6-solid:circle-check" class="display-inline mr-2" />
            {{ t('service_block.meter_lookup_found') }} ({{ foundCount }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_not_found" @click.prevent="setActiveTab('not_found')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'not_found', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'not_found' }">
            <Icon name="fa6-solid:circle-xmark" class="display-inline mr-2" />
            {{ t('service_block.meter_lookup_not_found') }} ({{ notFoundCount }})
          </a>
        </li>
      </AtomsTabs>

      <section v-show="activeTab === 'found'" role="tabpanel" id="tab_found" class="mt-3">
        <div v-if="!found.length" class="my-3 text-slate-600">
          {{ t('common.no_records') }}
        </div>
        <div v-else class="overflow-x-auto border border-slate-200 rounded">
          <div class="min-w-max">
            <div
              class="grid grid-cols-[110px,140px,110px,80px,100px,100px,70px,100px,70px,90px,180px,160px,200px] gap-2 text-sm border-b bg-slate-50 px-2 py-2 font-medium text-slate-600 items-center">
              <span>{{ t('common.code') }}</span>
              <span>{{ t('common.exploitation') }}</span>
              <span>{{ t('common.status') }}</span>
              <span>{{ t('service_block.caliber') }}</span>
              <span>{{ t('service_block.install_date') }}</span>
              <span>{{ t('service_block.short_uninstall_date') }}</span>
              <span>{{ t('service_block.telecontrol') }}</span>
              <span>{{ t('service_block.manufacturer') }}</span>
              <span>{{ t('service_block.manufacturing_year') }}</span>
              <span>{{ t('service_block.tech') }}</span>
              <span>{{ t('supply_point') }}</span>
              <span>{{ t('contracts') }}</span>
              <span>{{ t('common.last_reading') }}</span>
            </div>
            <div v-for="(item, idx) in found" :key="item.code + '-' + idx"
              class="grid grid-cols-[110px,140px,110px,80px,100px,100px,70px,100px,70px,90px,180px,160px,200px] gap-2 text-sm border-b px-2 py-1.5 items-center bg-white hover:bg-slate-50">
              <span class="font-mono truncate" :title="item.code">{{ item.code }}</span>
              <span class="truncate" :title="item.exploitation || ''">{{ item.exploitation || '-' }}</span>
              <span class="truncate">
                <AtomsColorBadge v-if="item.status?.name" :value="item.status.name" :color="item.status.color" />
                <span v-else>-</span>
              </span>
              <span class="truncate" :title="item.caliber?.name || item.caliber?.token || ''">
                {{ item.caliber?.token || item.caliber?.name || '-' }}
              </span>
              <span class="text-nowrap">{{ item.installation_at ? formatDate(item.installation_at) : '-' }}</span>
              <span class="text-nowrap">{{ item.uninstallation_at ? formatDate(item.uninstallation_at) : '-' }}</span>
              <span>
                <Icon v-if="item.has_remote_reading" name="fa6-solid:circle-check" class="text-green-500" />
                <span v-else>-</span>
              </span>
              <span class="truncate" :title="item.manufacturer || ''">{{ item.manufacturer || '-' }}</span>
              <span>{{ item.manufacturing_year || '-' }}</span>
              <span class="truncate" :title="item.comm_technology || ''">{{ item.comm_technology || '-' }}</span>
              <span class="truncate min-w-0"
                :title="item.supply_point?.address_search || item.supply_point?.token || ''">
                <template v-if="item.supply_point">
                  <span class="text-slate-500 mr-1">{{ item.supply_point.token }}</span>
                  {{ item.supply_point.address_search || '' }}
                </template>
                <template v-else>-</template>
              </span>
              <span class="truncate text-xs" :title="formatContracts(item.contracts)">
                {{ formatContracts(item.contracts) }}
              </span>
              <span class="truncate text-xs" :title="formatLastReading(item.last_reading)">
                {{ formatLastReading(item.last_reading) }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'not_found'" role="tabpanel" id="tab_not_found" class="mt-3">
        <div class="flex justify-end mb-2" v-if="notFound.length">
          <button type="button" class="button-default flex items-center gap-1.5"
            @click="copyNotFoundCodes"
            :title="t('service_block.meter_lookup_copy_not_found')">
            <Icon name="fa6-solid:copy" class="text-slate-500" />
            <span class="text-sm">{{ t('service_block.meter_lookup_copy_not_found') }}</span>
          </button>
        </div>
        <div v-if="!notFound.length" class="my-3 text-slate-600">
          {{ t('common.no_records') }}
        </div>
        <div v-else class="overflow-x-auto border border-slate-200 rounded bg-white">
          <div class="grid grid-cols-[1fr] text-sm">
            <div class="border-b bg-slate-50 px-3 py-2 font-medium text-slate-600">
              {{ t('common.code') }}
            </div>
            <div v-for="code in notFound" :key="code"
              class="border-b px-3 py-1.5 font-mono text-red-700 hover:bg-red-50">
              {{ code }}
            </div>
          </div>
        </div>
      </section>
    </template>

    <MeterLookupModal ref="lookupModalRef" v-model:open="showLookupModal" @search="handleLookupSearch" />
  </div>
</template>
