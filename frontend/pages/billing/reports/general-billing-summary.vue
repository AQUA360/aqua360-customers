<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import H1 from '~/components/atoms/H1.vue';
import InputNumber from '~/components/atoms/InputNumber.vue';
import InputText from '~/components/atoms/InputText.vue';

const { t } = useI18n();
const toast = useToast();
const { $ReportsApiService, $InvoiceApiService, $ConfigProjectApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();

// Quin informe es genera des d'aquesta pàgina: el resum general (per rang de serie_final)
// o el padró de facturació (mateix rang, mateix flux de previsualització/revisió, però
// generant l'informe register_billing_summary en lloc del resum general).
const activeSection = ref('general');

// La previsualització (cercar abans de generar) només es mostra quan el
// ConfigProject `general_billing_summary_preview_enabled` ho permet. És el mateix
// per a les dues pestanyes.
const previewEnabled = ref(false);

const loadPreviewConfig = async () => {
  try {
    // Fem servir getAll() en lloc de get(): get() llegeix primer d'una cache a
    // localStorage sense caducitat, així que si l'usuari havia carregat l'app abans
    // que aquesta config s'activés al backend, es quedaria amb el valor antic ('false'
    // o inexistent) indefinidament. getAll() sempre consulta el backend.
    const response = await $ConfigProjectApiService.getAll('general_billing_summary_preview_enabled');
    const value = Array.isArray(response) && response.length > 0 ? response[0].value : null;
    previewEnabled.value = value === true || value === 'true';
  } catch (error) {
    console.error(error);
    previewEnabled.value = false;
  }
};

// ---------------------------------------------------------------------------
// Estat i lògica compartits pels dos informes (resum general / padró de
// facturació): rang de serie_final, previsualització, marcar com a revisat i
// generació de l'Excel. Cada pestanya té la seva pròpia instància perquè cada
// una manté el seu propi rang i el seu propi informe seleccionat, però el
// comportament és exactament el mateix.
function useBillingSummaryRange(reportDir, reportNameKey, downloadPrefix) {
  const prefix = ref('');
  const serieFinalFrom = ref(null);
  const serieFinalTo = ref(null);
  // Filtre d'usuari: per defecte les factures ja revisades no es tornen a
  // incloure ni a la previsualització ni a l'informe generat.
  const excludeReviewed = ref(true);

  const isRangeValid = computed(() => {
    return serieFinalFrom.value !== null && serieFinalTo.value !== null && serieFinalFrom.value <= serieFinalTo.value;
  });

  const previewLoading = ref(false);
  const previewData = ref(null);
  const previewedRangeKey = ref(null);

  const currentRangeKey = computed(() => `${prefix.value || ''}|${serieFinalFrom.value}|${serieFinalTo.value}|${excludeReviewed.value}`);
  const isPreviewStale = computed(() => previewedRangeKey.value !== currentRangeKey.value);
  const hasValidPreview = computed(() => previewEnabled.value && previewData.value && !isPreviewStale.value);

  const activeTab = ref('to_generate');
  const tabs = computed(() => previewData.value ? [
    { key: 'to_generate', label: t('reports_block.preview_tab_to_generate'), items: previewData.value.to_generate, count: previewData.value.to_generate_count },
    { key: 'excluded', label: t('reports_block.preview_tab_excluded'), items: previewData.value.excluded, count: previewData.value.excluded_count },
    { key: 'missing', label: t('reports_block.preview_tab_missing'), items: previewData.value.missing, count: previewData.value.missing_count },
    { key: 'already_reviewed', label: t('reports_block.preview_tab_already_reviewed'), items: previewData.value.already_reviewed, count: previewData.value.already_reviewed_count },
  ] : []);
  const activeTabItems = computed(() => tabs.value.find(tab => tab.key === activeTab.value)?.items || []);

  // Paginació via scroll (de 50 en 50): la previsualització pot tornar milers
  // de factures i renderitzar-les totes de cop penja el navegador.
  const PAGE_SIZE = 50;
  const visibleCount = ref(PAGE_SIZE);
  const visibleTabItems = computed(() => activeTabItems.value.slice(0, visibleCount.value));
  const hasMoreTabItems = computed(() => visibleCount.value < activeTabItems.value.length);
  const loadMoreTabItems = () => {
    if (hasMoreTabItems.value) visibleCount.value += PAGE_SIZE;
  };
  watch([activeTab, previewData], () => {
    visibleCount.value = PAGE_SIZE;
  });
  const onTableScroll = (event) => {
    const el = event.target;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) {
      loadMoreTabItems();
    }
  };

  const runPreview = async () => {
    if (!isRangeValid.value) return;
    previewLoading.value = true;
    try {
      const response = await $InvoiceApiService.previewReviewedRange({
        serie_final_from: serieFinalFrom.value,
        serie_final_to: serieFinalTo.value,
        prefix: prefix.value || null,
        exclude_reviewed: excludeReviewed.value,
      });
      previewData.value = response;
      previewedRangeKey.value = currentRangeKey.value;
      activeTab.value = 'to_generate';
    } catch (error) {
      console.error(error);
      toast.error(t('reports_block.error_preview_reviewed_range'));
    } finally {
      previewLoading.value = false;
    }
  };

  const markingReviewed = ref(false);

  const setReviewedRange = async (reviewed) => {
    if (!isRangeValid.value || (previewEnabled.value && !hasValidPreview.value)) return;
    const confirmKey = reviewed ? 'confirmation_text_block.confirm_mark_reviewed_range' : 'confirmation_text_block.confirm_unmark_reviewed_range';
    if (!confirm(t(confirmKey))) return;

    markingReviewed.value = true;
    try {
      await $InvoiceApiService.markReviewedRange({
        serie_final_from: serieFinalFrom.value,
        serie_final_to: serieFinalTo.value,
        prefix: prefix.value || null,
        reviewed,
      });
      toast.success(t(reviewed ? 'billing_block.correct_mark_reviewed_range' : 'billing_block.correct_unmark_reviewed_range'));
      // Actualitza l'estat "revisada" de les factures ja carregades a la previsualització
      // (totes pertanyen al mateix rang/prefix que s'acaba de marcar) sense re-categoritzar-les
      // entre pestanyes ni tornar a fer la cerca: només canvia la columna "Revisades".
      if (previewData.value) {
        ['to_generate', 'excluded', 'missing', 'already_reviewed'].forEach(key => {
          (previewData.value[key] || []).forEach(invoice => {
            invoice.reviewed = reviewed;
          });
        });
      }
    } catch (error) {
      console.error(error);
      toast.error(t('billing_block.error_mark_reviewed_range'));
    } finally {
      markingReviewed.value = false;
    }
  };

  // Generació de l'informe (Excel), seguint el mateix patró de polling que la
  // resta d'informes individuals (getIndividualReport -> task_id -> checkTask -> viewDocument).
  const generatingReport = ref(false);
  const reportTaskId = ref(null);

  const generateReport = async () => {
    if (!isRangeValid.value || (previewEnabled.value && !hasValidPreview.value)) return;
    generatingReport.value = true;
    try {
      const response = await $ReportsApiService.getIndividualReport(reportDir, {
        serie_final_from: serieFinalFrom.value,
        serie_final_to: serieFinalTo.value,
        prefix: prefix.value || null,
        name: t(reportNameKey),
        exclude_reviewed: excludeReviewed.value,
      });
      if (response && typeof response === 'object' && 'task_id' in response) {
        reportTaskId.value = response.task_id;
      }
    } catch (error) {
      console.error(error);
      toast.error(t('reports_block.report_generation_failed', { name: t(reportNameKey) }));
    } finally {
      generatingReport.value = false;
    }
  };

  const downloadReport = async () => {
    try {
      const response = await $apiManager.checkTask(reportTaskId.value);
      if (response && response.result && response.result.document_id) {
        const file = await $DocumentManagerApiService.viewDocument(response.result.document_id);
        const link = document.createElement('a');
        const file_url = URL.createObjectURL(file);
        link.href = file_url;
        link.download = `${downloadPrefix}_${serieFinalFrom.value}_${serieFinalTo.value}.xlsx`;
        link.click();
        setTimeout(() => {
          window.URL.revokeObjectURL(file_url);
        }, 250);
      } else if (response && response.state === 'FAILURE') {
        toast.error(t('reports_block.report_generation_failed', { name: t(reportNameKey) }));
      }
    } catch (error) {
      console.error(error);
    } finally {
      reportTaskId.value = null;
    }
  };

  return {
    prefix, serieFinalFrom, serieFinalTo, excludeReviewed, isRangeValid,
    previewLoading, previewData, isPreviewStale, hasValidPreview, activeTab, tabs, activeTabItems, runPreview,
    visibleTabItems, hasMoreTabItems, loadMoreTabItems, onTableScroll,
    markingReviewed, setReviewedRange,
    generatingReport, reportTaskId, generateReport, downloadReport,
  };
}

const general = useBillingSummaryRange('general-billing-summary', 'reports_block.general_billing_summary', 'resum_facturacio_general');
const register = useBillingSummaryRange('register-billing-summary', 'reports_block.register_billing_summary', 'padro_facturacio');

onMounted(() => {
  loadPreviewConfig();
});
</script>

<template>
  <div id="wrapper" class="text-base" :class="{ 'pb-24': previewEnabled }">
    <H1 class="mb-2">{{ $t('reports_block.reports_between_dates_title') }}</H1>
    <p class="text-slate-500 mb-6 max-w-2xl">{{ $t('reports_block.reports_between_dates_description') }}</p>

    <!-- Selector de tipus d'informe a generar -->
    <div class="flex gap-2 border-b border-slate-200 mb-6">
      <button type="button" @click="activeSection = 'general'"
        class="px-3 py-2 text-sm font-medium border-b-2 -mb-px"
        :class="activeSection === 'general' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-700'">
        {{ $t('reports_block.general_billing_summary') }}
      </button>
      <button type="button" @click="activeSection = 'register'"
        class="px-3 py-2 text-sm font-medium border-b-2 -mb-px"
        :class="activeSection === 'register' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-700'">
        {{ $t('reports_block.register_billing_summary') }}
      </button>
    </div>

    <!-- El contingut de les dues pestanyes és idèntic (filtre, previsualització,
         revisió i footer amb el cercador) — l'únic que canvia és l'informe que
         es genera al final (general vs padró de facturació), gestionat per
         `useBillingSummaryRange`. -->
    <template v-for="(section, sectionKey) in { general, register }" :key="sectionKey">
      <div v-if="activeSection === sectionKey">
        <H1 class="mb-2">{{ $t(`reports_block.${sectionKey}_billing_summary`) }}</H1>
        <p class="text-slate-500 mb-6 max-w-2xl">{{ $t(`reports_block.${sectionKey}_billing_summary_description`) }}</p>

        <div class="max-w-xl border border-slate-200 rounded-md p-4 mb-6">
          <InputText v-model="section.prefix.value" :label="$t('reports_block.serie_final_prefix')"
            :placeholder="$t('reports_block.serie_final_prefix_placeholder')" />
          <div class="grid grid-cols-2 gap-4">
            <InputNumber v-model="section.serieFinalFrom.value" :label="$t('reports_block.serie_final_from')" :min="0" required />
            <InputNumber v-model="section.serieFinalTo.value" :label="$t('reports_block.serie_final_to')" :min="0" required />
          </div>
          <label class="flex items-center gap-2 mt-4 text-sm font-medium text-gray-700">
            <input v-model="section.excludeReviewed.value" type="checkbox" class="checkbox" />
            {{ $t('reports_block.exclude_already_reviewed_invoices') }}
          </label>
        </div>

        <!-- Flux amb previsualització (cercar abans de generar), només si el ConfigProject ho permet -->
        <div v-if="previewEnabled">
          <div v-if="!section.previewData.value && !section.previewLoading.value" class="text-slate-400 text-sm mb-6">
            {{ $t('reports_block.preview_empty_hint') }}
          </div>
          <div v-else-if="section.previewLoading.value" class="text-slate-400 text-sm flex items-center gap-2 mb-6">
            <Icon name="fa6-solid:spinner" class="animate-spin" />
            {{ $t('common.loading') }}
          </div>
          <div v-else>
            <p v-if="section.isPreviewStale.value" class="text-xs text-amber-600 mb-3 flex items-center gap-1">
              <Icon name="fa6-solid:triangle-exclamation" />
              {{ $t('reports_block.preview_stale_hint') }}
            </p>

            <div class="flex gap-2 border-b border-slate-200 mb-3">
              <button v-for="tab in section.tabs.value" :key="tab.key" type="button" @click="section.activeTab.value = tab.key"
                class="px-3 py-2 text-sm font-medium border-b-2 -mb-px flex items-center gap-1"
                :class="section.activeTab.value === tab.key ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-700'">
                {{ tab.label }}
                <span class="rounded-full px-1.5 text-xs"
                  :class="[tab.count > 0 && tab.key !== 'to_generate' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600']">
                  {{ tab.count }}
                </span>
              </button>
            </div>

            <div class="border border-slate-200 rounded-md max-h-[36rem] overflow-y-auto" @scroll="section.onTableScroll">
              <table class="w-full text-sm">
                <thead class="sticky top-0 z-10 bg-white shadow-sm">
                  <tr class="border-b border-slate-200 text-left text-slate-500">
                    <th class="p-2">{{ $t('invoice') }}</th>
                    <th class="p-2">{{ $t('common.date') }}</th>
                    <th class="p-2">{{ $t('common.holder') }}</th>
                    <th class="p-2 text-right">{{ $t('common.amount') }}</th>
                    <th class="p-2 text-center">{{ $t('reports_block.reviewed_column') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="invoice in section.visibleTabItems.value" :key="invoice.id" class="border-b border-slate-100 last:border-0">
                    <td class="p-2 font-medium">{{ invoice.serie_final }}</td>
                    <td class="p-2">{{ formatDate(invoice.issue_date) }}</td>
                    <td class="p-2 truncate max-w-xs">{{ invoice.customer_final }}</td>
                    <td class="p-2 text-right">{{ formatMoneyWithCurrency(invoice.total_final) }}</td>
                    <td class="p-2 text-center">
                      <span v-if="invoice.reviewed"
                        class="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800"
                        :title="$t('reports_block.reviewed_yes')">
                        <Icon name="fa6-solid:check" /> {{ $t('reports_block.reviewed_yes') }}
                      </span>
                      <span v-else
                        class="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold bg-slate-100 text-slate-500"
                        :title="$t('reports_block.reviewed_no')">
                        <Icon name="fa6-solid:xmark" /> {{ $t('reports_block.reviewed_no') }}
                      </span>
                    </td>
                  </tr>
                  <tr v-if="section.activeTabItems.value.length === 0">
                    <td colspan="5" class="p-4 text-center text-slate-400">{{ $t('common.no_results') }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="section.hasMoreTabItems.value" class="text-center py-2 text-xs text-slate-400 flex items-center justify-center gap-2">
                <Icon name="fa6-solid:spinner" class="animate-spin" />
                {{ $t('common.loading') }}
              </div>
            </div>
          </div>
        </div>

        <!-- Flux simple (sense previsualització), quan el ConfigProject ho té desactivat -->
        <div v-else class="max-w-xl border border-slate-200 rounded-md p-4 mb-6">
          <div class="flex items-center gap-2 mb-4">
            <button type="button" class="button-primary" :disabled="!section.isRangeValid.value || section.generatingReport.value || !!section.reportTaskId.value"
              @click="section.generateReport">
              <Icon :name="section.generatingReport.value ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'" :class="{ 'animate-spin': section.generatingReport.value }" />
              {{ $t('reports_block.generate_report') }}
            </button>
            <AtomsProcessColorBadge v-if="section.reportTaskId.value" class="w-[200px]" @refresh="section.downloadReport"
              :value="t('common.loading')" :color="'green'" :taskId="section.reportTaskId.value" />
          </div>
          <div class="flex items-center gap-2">
            <button type="button" class="button-primary" :disabled="!section.isRangeValid.value || section.markingReviewed.value"
              @click="section.setReviewedRange(true)">
              <Icon name="fa6-solid:check" />
              {{ $t('reports_block.mark_reviewed_range') }}
            </button>
            <button type="button" class="button-secondary" :disabled="!section.isRangeValid.value || section.markingReviewed.value"
              @click="section.setReviewedRange(false)">
              <Icon name="fa6-solid:xmark" />
              {{ $t('reports_block.unmark_reviewed_range') }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- Barra de navegació fixada al footer, mateix patró que ClaimRequestEdit.vue -->
    <div v-if="previewEnabled" class="fixed right-0 bottom-0 border-t border-gray-200 py-4 px-4 shadow-lg bg-white"
      style="width: calc(100% - 250px)">
      <div class="mx-auto flex justify-between items-center px-4">
        <template v-for="(section, sectionKey) in { general, register }" :key="sectionKey">
          <template v-if="activeSection === sectionKey">
            <div class="grid auto-cols-max grid-flow-col items-center gap-x-8">
              <div class="flex flex-col">
                <div class="text-lg font-bold text-sky-700">{{ section.previewData.value?.to_generate_count ?? '-' }}</div>
                <div class="text-sm font-semibold text-slate-700">{{ $t('reports_block.preview_tab_to_generate') }}</div>
              </div>
              <div class="flex flex-col">
                <div class="text-lg font-bold" :class="section.previewData.value?.excluded_count ? 'text-red-600' : 'text-sky-700'">{{ section.previewData.value?.excluded_count ?? '-' }}</div>
                <div class="text-sm font-semibold text-slate-700">{{ $t('reports_block.preview_tab_excluded') }}</div>
              </div>
              <div class="flex flex-col">
                <div class="text-lg font-bold" :class="section.previewData.value?.missing_count ? 'text-red-600' : 'text-sky-700'">{{ section.previewData.value?.missing_count ?? '-' }}</div>
                <div class="text-sm font-semibold text-slate-700">{{ $t('reports_block.preview_tab_missing') }}</div>
              </div>
              <div class="flex flex-col">
                <div class="text-lg font-bold" :class="section.previewData.value?.already_reviewed_count ? 'text-amber-600' : 'text-sky-700'">{{ section.previewData.value?.already_reviewed_count ?? '-' }}</div>
                <div class="text-sm font-semibold text-slate-700">{{ $t('reports_block.preview_tab_already_reviewed') }}</div>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <button type="button" class="button-default flex items-center gap-2" :disabled="!section.isRangeValid.value || section.previewLoading.value"
                @click="section.runPreview">
                {{ $t('common.search') }}
                <Icon :name="section.previewLoading.value ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'" :class="{ 'animate-spin': section.previewLoading.value }" />
              </button>
              <button type="button" class="button-primary flex items-center gap-2" :disabled="!section.hasValidPreview.value || section.generatingReport.value || !!section.reportTaskId.value"
                @click="section.generateReport">
                <Icon :name="section.generatingReport.value ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'" :class="{ 'animate-spin': section.generatingReport.value }" />
                {{ $t('reports_block.generate_report') }}
              </button>
              <AtomsProcessColorBadge v-if="section.reportTaskId.value" class="w-fit" @refresh="section.downloadReport"
                :value="t('common.loading')" :color="'green'" :taskId="section.reportTaskId.value" />
              <button type="button" class="button-secondary flex items-center gap-2" :disabled="!section.hasValidPreview.value || section.markingReviewed.value"
                @click="section.setReviewedRange(true)">
                <Icon name="fa6-solid:check" />
                {{ $t('reports_block.mark_reviewed_range') }}
              </button>
            </div>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>
