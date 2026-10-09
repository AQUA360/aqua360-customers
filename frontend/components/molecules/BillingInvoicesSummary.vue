<script setup>
import { ref, onMounted, onBeforeUnmount, provide } from 'vue';
import { useI18n } from 'vue-i18n';
import InvoiceSummaryDetail from '~/components/atoms/InvoiceSummaryDetail.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import _ from 'lodash';
import { useExportJobsStore } from '~/stores/useExportJobs';

const { t } = useI18n();
const { $BillingApiService, $ReportsApiService, $apiManager, $DocumentManagerApiService, $ConfigProjectApiService } = useNuxtApp();

const props = defineProps({
  billing_id: Number,
  billing_name: String
});

const emit = defineEmits(['change', 'show-subregion', 'batch_id']);

const loading = ref(false);
const billingSummary = ref([])

const usesAca = ref(false);
// Only used by backends that still answer with a bare `task_id` (no downloads queue).
const downloadDocCeleryId = ref(null);
const exportJobsStore = useExportJobsStore();

// Name of the report in the downloads queue: "<report> – <billing token>".
const reportExportName = (labelKey) => [t(labelKey), props.billing_name].filter(Boolean).join(' – ');

// The register reports go to the user's downloads queue (`export_job_id`): the
// file is downloaded when ready even if the user leaves the billing, and stays
// in the Downloads menu. Returns false if the response is not an async task.
const handleReportTask = (response, name) => {
  if (response?.export_job_id) {
    exportJobsStore.track(response.export_job_id, name);
    return true;
  }
  if (response && typeof response === 'object' && 'task_id' in response) {
    downloadDocCeleryId.value = response.task_id;
    return true;
  }
  return false;
};
const showReportsDropdown = ref(false);
const reportsDropdownRef = ref(null);

const closeReportsDropdown = () => {
  showReportsDropdown.value = false;
};

const toggleReportsDropdown = () => {
  showReportsDropdown.value = !showReportsDropdown.value;
};

const handleReportsDropdownClickOutside = (event) => {
  if (reportsDropdownRef.value && !reportsDropdownRef.value.contains(event.target)) {
    closeReportsDropdown();
  }
};

provide('closeOptionsDropdown', closeReportsDropdown);

const loadPreinvoicesSummary = async () => {
  loading.value = true;
  billingSummary.value = await $BillingApiService.getSummary(props.billing_id)

  try {
    usesAca.value = await $ConfigProjectApiService.get('uses_aca');
  } catch (error) {
    console.error(error);
  }

  loading.value = false;
}
const downloadSummary = async () => {
  loading.value = true;
  $BillingApiService.downloadSummary(props.billing_id).then(response => response.arrayBuffer())
    .then(buffer => {
      const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `billing_${new Date().toLocaleString('default', { month: '2-digit', year: '2-digit' }).replace(/\//g, '_')}.xlsx`;
      a.click();
    })
    .finally(() => {
      loading.value = false;
    });
}

const downloadRegisterAca = async () => {
  const exportName = reportExportName('reports_block.no_aca_summary');
  let params = {
    export_name: exportName,
    id: props.billing_id || null,
    product_ids: null,
    exploitation_id: null,
    name: `${t('reports_block.register_billing').toLowerCase().replace(' ', '_')}`,
    type_id: null,
    include_preinvoices: true,
    generate_object: false,
  }

  $ReportsApiService.getIndividualReport('no-aca-register-billing-summary', params).then(response => {
    handleReportTask(response, exportName);
  })
    .finally(() => {
      loading.value = false;
    });
}

const downloadRegister = async () => {
  const exportName = reportExportName('reports_block.register_billing');
  let params = {
    export_name: exportName,
    id: props.billing_id || null,
    product_ids: null,
    exploitation_id: null,
    name: `${t('reports_block.register_billing').toLowerCase().replace(' ', '_')}`,
    type_id: null,
    include_preinvoices: true,
    generate_object: false,
  }
  $ReportsApiService.getIndividualReport('register-billing-summary', params).then(async response => {
    if (handleReportTask(response, exportName)) return;

    // Try to parse as JSON first to check for task_id
    const contentType = response.headers?.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const jsonData = await response.json();
      if (jsonData?.task_id) {
        downloadDocCeleryId.value = jsonData.task_id;
        return;
      }
    }

    // Otherwise, treat as binary data
    const buffer = await response.arrayBuffer();
    downloadFile(
      buffer,
      `${t('reports_block.register_billing')
        .toLowerCase()
        .replace(/[^a-z0-9]/gi, '_')}_${props.billing_name
          .toLowerCase()
          .replace(/[^a-z0-9]/gi, '_')}.xlsx`
    );
  })
    .finally(() => {
      loading.value = false;
    });
};
const downloadMiniRegister = async () => {
  const exportName = reportExportName('reports_block.reduced_register_billing');
  let params = {
    export_name: exportName,
    id: props.billing_id || null,
    product_ids: null,
    exploitation_id: null,
    name: `${t('reports_block.register_billing').toLowerCase().replace(' ', '_')}`,
    type_id: null,
    include_preinvoices: true,
    generate_object: false,
  }
  $ReportsApiService.getIndividualReport('mini-register-billing-summary', params).then(response => {
    handleReportTask(response, exportName);
  })
    .finally(() => {
      loading.value = false;
    });
};

const downloadRegisterCelery = async () => {
  try {
    const response = await $apiManager.checkTask(downloadDocCeleryId.value)
    if (response && response.result && response.result.document_id) {
      const file = await $DocumentManagerApiService.viewDocument(response.result.document_id);
      const link = document.createElement('a');
      const file_url = URL.createObjectURL(file);
      link.href = file_url
      link.download = `${t('reports_block.register_billing')
        .toLowerCase()
        .replace(/[^a-z0-9]/gi, '_')}_${props.billing_name
          .toLowerCase()
          .replace(/[^a-z0-9]/gi, '_')}.xlsx`;

      link.click();

      setTimeout(() => {
        window.URL.revokeObjectURL(file_url);
      }, 250);
    }
  } catch (error) {
    console.error(error);
  } finally {
    downloadDocCeleryId.value = null;
  }

}

const downloadFile = (buffer, fileName) => {
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
}

onMounted(() => {
  loadPreinvoicesSummary();
  document.addEventListener('mousedown', handleReportsDropdownClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleReportsDropdownClickOutside);
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between mb-4">
      <h2 class="text-xl font-semibold">{{ $t('reports_block.billing_summary') }}</h2>
      <div class="flex items-center gap-2">
        <AtomsProcessColorBadge v-if="downloadDocCeleryId" class="w-[200px]" @refresh="downloadRegisterCelery"
          :value="t('common.loading')" :color="'green'" :taskId="downloadDocCeleryId" />
        <div ref="reportsDropdownRef" class="relative">
          <button type="button" class="button-secondary" @click="toggleReportsDropdown">
            <Icon name="fa6-solid:file-excel" />
            {{ $t('reports_block.available_reports') }}
            <Icon name="fa6-solid:chevron-down" class="ml-1 h-3 w-3 transition-transform"
              :class="{ 'rotate-180': showReportsDropdown }" />
          </button>
          <div v-if="showReportsDropdown"
            class="absolute right-0 z-10 mt-1 min-w-[16rem] rounded divide-y divide-gray-100 border border-gray-200 bg-white shadow">
            <ul class="py-1 text-sm text-gray-700">
              <DropdownOption v-if="usesAca" :name="t('reports_block.no_aca_summary')"
                :disabled="!!downloadDocCeleryId" @click="downloadRegisterAca">
                <Icon name="fa6-solid:file-excel" class="display-inline mr-2" />
                {{ $t('common.download') }} {{ $t('reports_block.no_aca_summary') }}
              </DropdownOption>
              <DropdownOption :name="t('reports_block.register_billing')" :disabled="!!downloadDocCeleryId"
                @click="downloadRegister">
                <Icon name="fa6-solid:file-excel" class="display-inline mr-2" />
                {{ $t('common.download') }} {{ $t('reports_block.register_billing') }}
              </DropdownOption>
              <DropdownOption :name="t('reports_block.reduced_register_billing')"
                :disabled="!!downloadDocCeleryId" @click="downloadMiniRegister">
                <Icon name="fa6-solid:file-excel" class="display-inline mr-2" />
                {{ $t('common.download') }} {{ $t('reports_block.reduced_register_billing') }}
              </DropdownOption>
              <DropdownOption :name="t('common.summary')" @click="downloadSummary">
                <Icon name="fa6-solid:file-excel" class="display-inline mr-2" />
                {{ $t('common.download') }} {{ $t('common.summary') }}
              </DropdownOption>
            </ul>
          </div>
        </div>
      </div>
    </div>
    <div class="mb-4">
      <div v-if="billingSummary.length == 0">
        <div class="border border-gray-300 rounded-b p-4 bg-white">
          <div class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2">{{ $t('common.loading') }}...</span>
          </div>
        </div>
      </div>
      <div v-else class="grid gap-px overflow-hidden rounded-lg bg-slate-200 grid-cols-2">
        <div class="bg-white px-2">
          <InvoiceSummaryDetail :billingSummary="billingSummary[0]" />
          <hr class="my-4" />
          <InvoiceSummaryDetail :billingSummary="billingSummary[1]" />
          <hr class="my-4" />
          <InvoiceSummaryDetail :billingSummary="billingSummary[3]" />
        </div>
        <div class="bg-white px-2">
          <InvoiceSummaryDetail :billingSummary="billingSummary[2]" />
        </div>
      </div>
    </div>
  </div>
</template>
