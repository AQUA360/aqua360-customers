<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ContractRequestRegion from '~/components/organisms/ContractRequestRegion.vue';
import { useConfigStore } from '~/stores/useConfigStore';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import DataTable from '~/components/organisms/DataTable.vue';
import { DocumentSignStatus, DocumentSignStatusLabels, documentSignStatusColor, documentSignStatusCode } from '~/utils/document-sign';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $DocumentSignApiService } = useNuxtApp();
const configStore = useConfigStore();
const router = useRouter();

const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');

const showRegion = ref(false);
const regionComponent = ref(null);
const regionDetailId = ref(null);
const isSubRegionOpen = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    regionComponent.value = null;
    regionDetailId.value = null;
  }
}

/** Obre ContractRegion si el DocumentSign ja té contracte, o ContractRequestRegion si encara és una sol·licitud. */
const showLinkedEntity = (item) => {
  if (item.contract) {
    regionComponent.value = 'ContractRegion';
    regionDetailId.value = item.contract;
  } else if (item.contract_request) {
    regionComponent.value = 'ContractRequestRegion';
    regionDetailId.value = item.contract_request;
  } else {
    return;
  }
  toggleRegion(true);
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const selectedFilters = ref([]);
const statuses = ref([]);

const filter_status = ref(
  Object.entries(DocumentSignStatusLabels).map(([id, key]) => ({ id: Number(id), name: t(key) }))
);

const isFilterOpen = ref(false);

const statusColor = (status) => documentSignStatusColor(status);

/** `status_display` arriba en anglès des de Django; l'etiqueta es tradueix pel codi. */
const statusLabel = (status) => (DocumentSignStatusLabels[documentSignStatusCode(status)] ? t(DocumentSignStatusLabels[documentSignStatusCode(status)]) : '');

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const status = statuses.value.length > 0 ? statuses.value[0] : null;
    const res = await $DocumentSignApiService.getAllSummary(status);
    items.value = res?.document_signs || [];
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = [];
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  });
  getData();
};

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  statuses.value = [];
  isFilterOpen.value = false;
  getData();
};

const downloadUrl = (item) => {
  if (documentSignStatusCode(item.status) !== DocumentSignStatus.SIGNED) return null;
  return item.contract_file_signed_url || $DocumentSignApiService.getDownloadUrl(item.id);
};

const canRequestSigned = (item) => {
  const status = documentSignStatusCode(item.status);
  return status === DocumentSignStatus.SENDED || status === DocumentSignStatus.EXPIRED;
};

const requestingId = ref(null);

const requestSignedDocument = async (item) => {
  requestingId.value = item.id;
  try {
    await $DocumentSignApiService.requestSignedDocument(item.id);
    await getData();
    const updated = items.value.find(i => i.id === item.id);
    if (documentSignStatusCode(updated?.status) === DocumentSignStatus.SIGNED) {
      toast.success(t('contract_block.document_sign_retrieved'));
    } else {
      toast.info(t('contract_block.document_sign_not_ready'));
    }
  } catch (error) {
    console.error('Error sol·licitant el document signat:', error);
    await getData();
  } finally {
    requestingId.value = null;
  }
};

const downloadDocument = async (item) => {
  const url = downloadUrl(item);
  if (!url) return;
  await openAuthenticatedFileUrl(url, false);
};

/**
 * L'endpoint `document-signs-all/` només admet filtre per `status`, sense cerca de text,
 * per la qual cosa la cerca es fa en client sobre les dades ja carregades.
 */
const filteredItems = computed(() => {
  const query = searchInput.value.trim().toLowerCase();
  if (!query) return items.value;
  return items.value.filter(item => (
    (item.contract_token || '').toLowerCase().includes(query)
    || (item.otp_name || '').toLowerCase().includes(query)
    || (item.otp_email || '').toLowerCase().includes(query)
  ));
});

onMounted(async () => {
  await configStore.fetchDocumentSignEnabled();
  if (!configStore.documentSignEnabled) {
    router.replace('/');
    return;
  }
  getData();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('contract_block.document_signs') }}</H1>
    </div>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="getData">

      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <FilterSelect :plain="true" :options="filter_status" :filters="selectedFilters" :multiple="true"
        :placeholder="t(`common.statuses`)" @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <span>
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="150px,1fr,1fr,120px,120px,220px"
      :height-offset="240"
      :pending="pending"
      :error="error"
      :is-empty="filteredItems.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('contract')" :sortable="false" />
        <TableHeader :label="$t('contract_block.document_sign_otp')" :sortable="false" />
        <TableHeader :label="$t('common.status')" :sortable="false" />
        <TableHeader :label="$t('common.date')" :sortable="false" />
        <TableHeader :label="$t('contract_block.signed_at')" :sortable="false" />
        <TableHeader :label="''" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in filteredItems" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle">
          <span class="p-1">
            <button v-if="item.contract || item.contract_request" type="button"
              class="text-sky-500 underline hover:no-underline text-left"
              @click="showLinkedEntity(item)">
              {{ item.contract_token || item.contract_request_token || `#${item.contract_request}` }}
            </button>
            <span v-else>-</span>
          </span>
          <span class="p-1">
            {{ item.otp_name }}
            <span class="text-slate-400 text-xs block">{{ item.otp_email }}</span>
          </span>
          <span>
            <AtomsColorBadge :value="statusLabel(item.status)" :color="statusColor(item.status)" />
          </span>
          <span class="p-1">{{ item.created_at ? formatDate(item.created_at) : '-' }}</span>
          <span class="p-1">{{ item.signed_at ? formatDate(item.signed_at) : '-' }}</span>
          <span class="p-1 flex flex-col gap-1 items-stretch">
            <button v-if="downloadUrl(item)" @click="downloadDocument(item)"
              class="button-default-xs flex items-center gap-1 justify-center">
              <Icon name="fa6-solid:download" />
              {{ $t('common.download') }}
            </button>
            <button v-else-if="canRequestSigned(item)" @click="requestSignedDocument(item)"
              :disabled="requestingId === item.id"
              class="button-default-xs flex items-center gap-1 justify-center">
              <Icon :name="requestingId === item.id ? 'fa6-solid:spinner' : 'fa6-solid:cloud-arrow-down'"
                :class="{ 'animate-spin': requestingId === item.id }" />
              {{ $t('contract_block.document_sign_request_signed') }}
            </button>
          </span>
        </div><!-- end for items -->
      </template>
    </DataTable>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-20"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="regionComponent" class="pl-10 h-full">
      <ContractRegion v-if="regionComponent === 'ContractRegion'" :id="regionDetailId" :isSubRegion="true"
        :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)" />
      <ContractRequestRegion v-if="regionComponent === 'ContractRequestRegion'" :id="regionDetailId" :isSubRegion="true"
        :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)" />
    </div>
  </div>
</template>
