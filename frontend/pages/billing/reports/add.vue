<script setup>
  import H1 from '~/components/atoms/H1.vue';
  import FieldDetail from '~/components/atoms/FieldDetail.vue';
  import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
  import Tabs from '~/components/atoms/Tabs.vue';
  import { useToast } from 'vue-toastification';
  import AddBillings from '~/components/molecules/AddBillings.vue';
  import AddPersons from '~/components/molecules/AddPersons.vue';
  import AddContracts from '~/components/molecules/AddContracts.vue';
  import SEPARemittanceList from '~/components/organisms/SEPARemittanceList.vue';
  import OrganismsAcaReportForm from '~/components/organisms/AcaReportForm.vue';
  import OrganismsRatesReportForm from '~/components/organisms/RatesReportForm.vue';
  import OrganismsGenericReportForm from '~/components/organisms/GenericReportForm.vue';
  import AppLoading from '~/components/atoms/AppLoading.vue';
  import { reactive } from 'vue';
  
  const toast = useToast()
  const { t } = useI18n();
  const { $ReportsApiService, $ProductApiService, $ConfiglistApiService, $ExploitationApiService, $InvoiceSequenceApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();
  const route = useRoute();
  
  const loding = ref(false)
  const activeReports = ref([])
  const loadingReportsList = ref(true)
  const expandedReportId = ref(null)
  const loadingExploitations = ref(true)
  const downloading = ref('')
  const downloadingName = ref('')
  const products = ref(null)
  const paymentTypes = ref(null)
  const selectedDetailedProductIds = ref([])
  const selectedSupplyTypeProductIds = ref([])
  const selectedTaxesProductIds = ref([])
  const selectedTaxesDetailedProductIds = ref([])
  const selectedWalletPayments = ref([])
  const model347Year = ref(new Date().getFullYear() - 1)
  const includeTaxFreeLines = ref(false)
  
  const selectedExploitation = ref(null)
  const exploitationOptions = ref([])
  const blockSelectExploitation = ref(false)
  
  const dateRange = ref(null)
  const selectedReportType = ref(null)
  const reportTypes = ref([])

  const seriesOptions = ref([])
  const selectedSeries = ref([])
  const loadingSeries = ref(false)
  const serieIds = computed(() => selectedSeries.value.map(s => s.code))
  
  const openDetailedProducts = ref(false)
  const openRegisterBillingProducts = ref(false)
  const openSupplyTypeProducts = ref(false)
  const openTaxesProducts = ref(false)
  const openTaxesDetailedProducts = ref(false)
  const openWalletPayments = ref(false)
  
  const includePreinvoices = ref(false)

  const showExtraFilters = ref(false)

  // Filtre pel rang de numero de factura (serie_final), el mateix que a
  // billing/reports/general-billing-summary: prefix de serie opcional per acotar el
  // rang a una sola serie i els dos extrems. Val per a qualsevol informe d'aquesta
  // pantalla i, a diferencia dels altres filtres extra, tambe serveix de seleccio:
  // amb el rang omplert no cal ni lot de facturacio ni periode.
  const serieFinalPrefix = ref('')
  const serieFinalFrom = ref('')
  const serieFinalTo = ref('')
  // Els extrems s'accepten sencers ("FC/AAAAMM/001000", "D1234567") o nomes amb el
  // numero ("1000"), com el `split_serie_final` del backend: el prefix de serie es
  // tot el que hi ha abans de l'ultim grup de digits.
  const splitSerieFinal = (value) => {
    const match = /^(.*?)(\d+)$/.exec(String(value ?? '').trim())
    return match ? { prefix: match[1], number: Number(match[2]) } : null
  }

  const trimmedFrom = computed(() => String(serieFinalFrom.value ?? '').trim())
  const trimmedTo = computed(() => String(serieFinalTo.value ?? '').trim())
  // Es permet deixar un extrem buit (rang obert per aquell costat).
  const hasSerieFinalRange = computed(() => trimmedFrom.value !== '' || trimmedTo.value !== '')
  // El rang (o nomes el prefix de serie) ja identifica les factures de l'informe:
  // compta com a seleccio i no cal cap lot de facturacio ni cap periode.
  const hasSerieFinalSelection = computed(
    () => hasSerieFinalRange.value || String(serieFinalPrefix.value ?? '').trim() !== ''
  )

  const serieFinalRangeError = computed(() => {
    const parts = [trimmedFrom.value, trimmedTo.value].filter(v => v !== '').map(splitSerieFinal)
    if (parts.some(p => p === null)) return 'reports_block.serie_final_range_format'
    if (parts.length < 2) return null
    const [from, to] = parts
    if (from.prefix !== to.prefix) return 'reports_block.serie_final_range_mixed'
    if (from.number > to.number) return 'reports_block.serie_final_range_invalid'
    return null
  })
  const isSerieFinalRangeValid = computed(() => serieFinalRangeError.value === null)

  const billingObjects = ref([])
  const excludedBillingObjects = ref([])
  const remittanceObjects = ref([])
  const selectedPersons = ref([])
  const selectedContracts = ref([])

  const selectedBilling = computed(() => billingObjects.value[0] || null)
  const billingId = computed(() => billingObjects.value[0]?.id ?? null)
  const excludeBillingId = computed(() => excludedBillingObjects.value[0]?.id ?? null)
  const selectedRemittance = computed(() => remittanceObjects.value[0] || null)
  const remittanceId = computed(() => remittanceObjects.value[0]?.id ?? null)
  const personIds = computed(() => selectedPersons.value.map(p => p.id))
  const contractIds = computed(() => selectedContracts.value.map(c => c.id))

  const showRegion = ref(false)
  const showRegionDetailComponent = ref(null)
  const regionDetailId = ref(null)
  
  const activeReportsStatus = ref({}); // { [report_id]: queue_item }
  const pollIntervals = {}; // { [report_id]: interval_id }
  const activeTab = ref('billing')
  
  const setActiveTab = (tab) => {
    activeTab.value = tab;
  }

  const fullQueueList = ref([]);
  const showPendingList = ref(true);
  const showFinishedList = ref(false);
  const queueInterval = ref(null);

  const runningTasks = computed(() => fullQueueList.value.filter(item => item.status === 'running'));
  const pendingTasks = computed(() => fullQueueList.value.filter(item => item.status === 'pending'));
  const finishedTasks = computed(() => fullQueueList.value.filter(item => ['completed', 'failed', 'warning'].includes(item.status)));

  const checkQueueStatus = async () => {
    try {
      const queueList = await $ReportsApiService.getReportsQueue();
      if (queueList && Array.isArray(queueList)) {
        fullQueueList.value = queueList;
      }
    } catch (err) {
      console.error('Error checking reports queue:', err);
    }
  };

  const startPollingReport = (reportId, queueItemId, reportName = '') => {
    if (pollIntervals[reportId]) {
      clearInterval(pollIntervals[reportId]);
    }

    const poll = async () => {
      try {
        const data = await $ReportsApiService.getReportsQueueItem(queueItemId);
        if (data) {
          activeReportsStatus.value[reportId] = data;

          if (data.status === 'completed' || data.status === 'failed' || data.status === 'warning') {
            clearInterval(pollIntervals[reportId]);
            delete pollIntervals[reportId];

            if (data.status === 'completed' && data.document_url) {
              const link = document.createElement('a');
              link.href = data.document_url;
              link.download = data.document_name || `report_${reportId}.xlsx`;
              link.click();
              toast.success(t('reports_block.report_completed_success', { name: reportName || data.document_name }));
            } else if (data.status === 'completed' && data.document_id) {
              await downloadQueueDocument(data.document_id, data.document_name || `report_${reportId}.xlsx`);
              toast.success(t('reports_block.report_completed_success', { name: reportName || data.document_name }));
            } else if (data.status === 'warning') {
              toast.warning(data.error_message || t('reports_block.report_generation_failed', { name: reportName }));
            } else if (data.status === 'failed') {
              toast.error(data.error_message || t('reports_block.report_generation_failed', { name: reportName }));
            }

            checkQueueStatus();
          }
        }
      } catch (err) {
        console.error(`Error polling queue item ${queueItemId}:`, err);
      }
    };

    poll();
    pollIntervals[reportId] = setInterval(poll, 3000);
  };


  const model347YearOptions = computed(() => {
    const currentYear = new Date().getFullYear();
    return Array.from({ length: currentYear - 2020 + 1 }, (_, i) => currentYear - i);
  })
  
  const toggleProduct = (id, list) => {
    const index = list.indexOf(id);
    if (index > -1) {
      list.splice(index, 1);
    } else {
      list.push(id);
    }
  };
  
  const getProducts = async (load = true) => {
    if (load) loding.value = true;
    selectedDetailedProductIds.value = []
    selectedSupplyTypeProductIds.value = []
    selectedTaxesProductIds.value = []
    selectedTaxesDetailedProductIds.value = []
    if (billingId.value) {
      const response = await $ReportsApiService.getBillingActiveProducts(billingId.value);
      products.value = response;
    } else {
      const response = await $ProductApiService.getAll(
        "", [], 1, null, false,
        null, [],
        true, selectedExploitation.value?.code != 'all' ? selectedExploitation.value?.code : null, true
      )
      products.value = response;
    }
    selectedDetailedProductIds.value = products.value.map(product => product.id);
    selectedSupplyTypeProductIds.value = products.value.map(product => product.id);
    selectedTaxesProductIds.value = products.value.map(product => product.id);
    selectedTaxesDetailedProductIds.value = products.value.map(product => product.id);
    loding.value = false;
  };
  
  const getExploitations = async () => {
    try {
      const response = await $ExploitationApiService.getData();
      exploitationOptions.value = response.results.map(exploitation => ({
        label: exploitation.name,
        code: exploitation.id
      }));
      exploitationOptions.value.unshift({
        label: t('reports_block.no_filter_exploitation'),
        code: 'all'
      });
      const exploitation_id = localStorage.getItem('exploitation');
      if (exploitation_id) {
        selectedExploitation.value = exploitationOptions.value.find(exploitation => exploitation.code == exploitation_id);
        blockSelectExploitation.value = true;
      } else {
        selectedExploitation.value = exploitationOptions.value.find(exploitation => exploitation.code == 'all');
      }
    } catch (error) {
      console.error('Error fetching exploitations:', error);
    }
    finally {
      loadingExploitations.value = false;
    }
  }
  
  const getPaymentTypes = async () => {
    try {
      const response = await $ConfiglistApiService.getAll('contract/contract-payment-type')
      paymentTypes.value = response.results.filter(item => item.token != 'BALANCE');
      selectedWalletPayments.value = paymentTypes.value.map(payment => payment.id);
    } catch (error) {
      console.error('Error fetching payment types:', error);
    }
  }
  
  const getReportTypes = async () => {
    const response = await $ConfiglistApiService.getAll('statistics/report-type')
    response.results.forEach(type => {
      reportTypes.value.push({
        label: type.name,
        code: type.id,
        ...type
      })
    })
    let no_type = { label: t('reports_block.short_no_reports'), code: 'null' }
    reportTypes.value.unshift(no_type);
    selectedReportType.value = no_type;
  }
  
  const getSeries = async () => {
    loadingSeries.value = true;
    try {
      const response = await $InvoiceSequenceApiService.getAll('', 1);
      const results = response?.results || (Array.isArray(response) ? response : []);
      seriesOptions.value = results.map(seq => ({
        label: seq.prefix,
        code: seq.id,
        ...seq
      }));
    } catch (error) {
      console.error('Error fetching invoice sequences:', error);
    } finally {
      loadingSeries.value = false;
    }
  }

  const resetLoader = () => {
    downloading.value = '';
    loadingTaskId.value = null;
  };
  
  const downloadRegisterCelery = async () => {
    try {
      const response = await $apiManager.checkTask(loadingTaskId.value)
      console.log("response", response);
      if (response && response.result && response.result.document_id){
        console.log(`Task state:`, response.state);
        console.log('Task result:', response.result);
        const file = await $DocumentManagerApiService.viewDocument(response.result.document_id);
        const link = document.createElement('a');
        const file_url = URL.createObjectURL(file);
        link.href = file_url
        if (response.result.filename) {
          link.download = response.result.filename;
        } else {
          link.download = `${downloadingName.value
              .toLowerCase()
              .replace(/[^a-z0-9]/gi, '_')}_${selectedExploitation?.value && selectedExploitation.value.code != 'all' ? 
              (selectedExploitation.value.label).toLowerCase().replace(/[^a-z0-9]/gi, '_') : ''}.xlsx`;
        }
  
        link.click();
  
        setTimeout(() => {
          window.URL.revokeObjectURL(file_url);
        }, 250);
      }
    } catch (error) {
      console.error(error);
    } finally {
      resetLoader()
    }
  
  }

  const downloadQueueDocument = async (documentId, documentName) => {
    try {
      const file = await $DocumentManagerApiService.viewDocument(documentId);
      const link = document.createElement('a');
      const file_url = URL.createObjectURL(file);
      link.href = file_url;
      link.download = documentName || `report_${documentId}.xlsx`;
      link.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(file_url);
      }, 250);
    } catch (error) {
      console.error('Error downloading queue document:', error);
      toast.error(t('reports_block.error_downloading_document') || 'Error al descarregar el document.');
    }
  }
  
  const fetchActiveReports = async () => {
    try {
      loadingReportsList.value = true;
      const response = await $ReportsApiService.getActiveReports();
      activeReports.value = Array.isArray(response) ? response : (response?.results || []);
    } catch (error) {
      console.error('Error fetching active reports:', error);
      toast.error(t('reports_block.error_loading_reports'));
    } finally {
      loadingReportsList.value = false;
    }
  };

  const toggleReport = (id) => {
    if (expandedReportId.value === id) {
      expandedReportId.value = null;
    } else {
      expandedReportId.value = id;
    }
  };

  const customFuncs = [
    'aca_summary_report',
    'register_billing_summary',
    'mini_register_billing_summary',
    'billing_taxes_detailed_summary',
    'report_billing_347',
    'cobraments_excel_report',
    'detailed_billing_summary',
    'billing_summary_by_supply_type',
    'incident_response_time',
    'incident_response_time_report'
  ];

  const isCustomReport = (report) => {
    return report.has_custom_config || customFuncs.includes(report.function_name);
  };

  const customComponent = (report) => {
    if (report.function_name === 'getAcaSummary' || report.function_name === 'aca_summary_report') {
      return OrganismsAcaReportForm;
    }
    if (report.function_name === 'getSummaryByRate' || report.function_name === 'billing_summary_by_rates') {
      return OrganismsRatesReportForm;
    }
    return null;
  };

  const sections = computed(() => {
    const map = new Map();
    activeReports.value.forEach(report => {
      const token = report.section_token || 'other';
      const name = report.section_name || t('common.other');
      if (!map.has(token)) {
        map.set(token, { token, name, reports: [] });
      }
      map.get(token).reports.push(report);
    });
    return Array.from(map.values());
  });

  const getSectionIcon = (token) => {
    switch (token) {
      case 'billing': return 'fa6-solid:file-invoice';
      case 'wallet': return 'fa6-solid:wallet';
      case 'other': return 'fa6-solid:ellipsis';
      default: return 'fa6-solid:file-lines';
    }
  };

  watch(() => sections.value, (newSections) => {
    if (newSections.length > 0 && !newSections.some(s => s.token === activeTab.value)) {
      activeTab.value = newSections[0].token;
    }
  }, { immediate: true });


  const handleReportDownload = async (report, formData) => {
    // 1. Sincronitzar les dades del formulari local amb els refs globals per mantenir coherència a la interfície
    if (formData.date_range !== undefined) dateRange.value = formData.date_range;
    if (formData.exploitation_id !== undefined) {
      selectedExploitation.value = exploitationOptions.value.find(e => e.code == formData.exploitation_id) || selectedExploitation.value;
    }
    if (formData.report_type_id !== undefined) {
      selectedReportType.value = reportTypes.value.find(t => t.code == formData.report_type_id) || selectedReportType.value;
    }
    if (formData.include_preinvoices !== undefined) includePreinvoices.value = formData.include_preinvoices;
    if (formData.selected_product_ids !== undefined) {
      selectedDetailedProductIds.value = formData.selected_product_ids;
      selectedSupplyTypeProductIds.value = formData.selected_product_ids;
      selectedTaxesProductIds.value = formData.selected_product_ids;
      selectedTaxesDetailedProductIds.value = formData.selected_product_ids;
    }
    if (formData.selected_payment_type_ids !== undefined) {
      selectedWalletPayments.value = formData.selected_payment_type_ids;
    }
    if (formData.include_tax_free_lines !== undefined) includeTaxFreeLines.value = formData.include_tax_free_lines;
    if (formData.model_347_year !== undefined) model347Year.value = formData.model_347_year;

    // 2. Validar que la selecció és correcta
    if (!isValid()) return;

    // 3. Establir l'estat de descàrrega asíncrona
    downloading.value = report.id;
    downloadingName.value = report.name;

    // 4. Resoldre el tipus de compte si és l'informe de resum de compte
    let account_type = null;
    if (
      report.function_name === 'getAccountSummary' ||
      report.function_name === 'accounting_values_report' ||
      report.function_name === 'accounting_values_invoice_report' ||
      report.function_name === 'accounting_values_payment_report' ||
      report.function_name === 'accounting_values_commitment_report'
    ) {
      account_type = 'INVOICES';
      const nameLower = (report.name || '').toLowerCase();
      const buttonLower = (report.download_button_name || '').toLowerCase();
      if (buttonLower.includes('invoice') || nameLower.includes('invoice') || nameLower.includes('factur')) {
        account_type = 'INVOICES';
      } else if (buttonLower.includes('payment') || nameLower.includes('payment') || nameLower.includes('cobrament') || nameLower.includes('pagament')) {
        account_type = 'PAYMENT';
      } else if (buttonLower.includes('deposit') || nameLower.includes('fiança') || nameLower.includes('compromís')) {
        account_type = 'COMMITMENTDEPOSIT';
      }
    }

    // 5. Construir el payload de filtres genèrics per al trigger del back-end
    const selectedProdIds = formData.selected_product_ids || [];
    const formattedProductIds = Array.isArray(selectedProdIds) ? selectedProdIds.join(',') : selectedProdIds;

    const payload = {
      date_range: formData.date_range || dateRange.value || null,
      start_date: (formData.date_range && formData.date_range[0])
        ? new Date(formData.date_range[0]).toISOString().split('T')[0]
        : (dateRange.value && dateRange.value[0] ? new Date(dateRange.value[0]).toISOString().split('T')[0] : null),
      end_date: (formData.date_range && formData.date_range[1])
        ? new Date(formData.date_range[1]).toISOString().split('T')[0]
        : (dateRange.value && dateRange.value[1] ? new Date(dateRange.value[1]).toISOString().split('T')[0] : null),
      exploitation_id: (formData.exploitation_id && formData.exploitation_id !== 'all')
        ? formData.exploitation_id
        : (selectedExploitation.value && selectedExploitation.value.code !== 'all' ? selectedExploitation.value.code : null),
      billing_id: formData.billing_id || billingId.value || null,
      billing_ids: billingObjects.value.map(b => b.id).join(','),
      exclude_billing_id: formData.exclude_billing_id || excludeBillingId.value || null,
      serie_ids: serieIds.value.join(','),
      serie_final_from: trimmedFrom.value || null,
      serie_final_to: trimmedTo.value || null,
      prefix: (serieFinalPrefix.value || '').trim() || null,
      remittance_id: formData.remittance_id || remittanceId.value || null,
      remittance_ids: remittanceObjects.value.map(r => r.id).join(','),
      person_ids: personIds.value.join(','),
      contract_ids: contractIds.value.join(','),
      report_type_id: (formData.report_type_id && formData.report_type_id !== 'null')
        ? formData.report_type_id
        : (selectedReportType.value && selectedReportType.value.code !== 'null' ? selectedReportType.value.code : null),
      include_preinvoices: formData.include_preinvoices !== undefined ? formData.include_preinvoices : includePreinvoices.value,
      include_tax_free_lines: formData.include_tax_free_lines !== undefined ? formData.include_tax_free_lines : includeTaxFreeLines.value,
      model_347_year: formData.model_347_year || model347Year.value || null,
      year: formData.model_347_year || model347Year.value || null,
      product_ids: formattedProductIds,
      taxes_ids: formattedProductIds,
      payment_type_ids: Array.isArray(formData.selected_payment_type_ids) ? formData.selected_payment_type_ids.join(',') : (formData.selected_payment_type_ids || ''),
      version: formData.version || 1,
      account_type: account_type,
      accounting_type: account_type
    };

    try {
      // 6. Cridar l'endpoint genèric de trigger del back-end passant el ID de l'informe!
      const response = await $ReportsApiService.triggerReport(report.id, payload);
      if (response && response.queue_item_id) {
        activeReportsStatus.value[report.id] = {
          id: response.queue_item_id,
          status: response.status || 'pending',
          percent: 0,
          error_message: null,
          document_url: null,
          processed_items: 0,
          total_items: 0
        };
        startPollingReport(report.id, response.queue_item_id, report.name);
      } else {
        throw new Error("No s'ha rebut el queue_item_id de la cua.");
      }
    } catch (error) {
      console.error('Error triggering dynamic report:', error);
      toast.error(t('reports_block.error_triggering_report'));
      delete activeReportsStatus.value[report.id];
    }
  };

    const onBillingSelected = async (item) => {
    const index = billingObjects.value.findIndex(b => b.id == item.id);
    if (index > -1) {
      billingObjects.value.splice(index, 1);
    } else {
      billingObjects.value.push(item);
    }
    dateRange.value = null
    await getProducts(false);
  }

  const onRemittanceSelected = async (item) => {
    const index = remittanceObjects.value.findIndex(r => r.id == item.id);
    if (index > -1) {
      remittanceObjects.value.splice(index, 1);
    } else {
      remittanceObjects.value.push(item);
    }
  }

  const unselectBilling = async (item) => {
    billingObjects.value = billingObjects.value.filter(b => b.id !== item.id);
    await getProducts(false);
  }

  const onExcludeBillingSelected = (item) => {
    const index = excludedBillingObjects.value.findIndex(b => b.id == item.id);
    if (index > -1) {
      excludedBillingObjects.value.splice(index, 1);
    } else {
      // Only a single billing can be excluded (matches exclude_billing_id).
      excludedBillingObjects.value = [item];
    }
  }

  const unselectExcludeBilling = (item) => {
    excludedBillingObjects.value = excludedBillingObjects.value.filter(b => b.id !== item.id);
  }

  const unselectRemittance = async (item) => {
    remittanceObjects.value = remittanceObjects.value.filter(r => r.id !== item.id);
  }

  const onPersonSelected = (person) => {
    const index = selectedPersons.value.findIndex(p => p.id == person.id);
    if (index > -1) {
      selectedPersons.value.splice(index, 1);
    } else {
      selectedContracts.value = [];
      selectedPersons.value.push(person);
    }
  }

  const unselectPerson = (person) => {
    selectedPersons.value = selectedPersons.value.filter(p => p.id !== person.id);
  }

  const onContractSelected = (contract) => {
    const index = selectedContracts.value.findIndex(c => c.id == contract.id);
    if (index > -1) {
      selectedContracts.value.splice(index, 1);
    } else {
      selectedPersons.value = [];
      selectedContracts.value.push(contract);
    }
  }

  const unselectContract = (contract) => {
    selectedContracts.value = selectedContracts.value.filter(c => c.id !== contract.id);
  }
  
  const updateSelect = async (event, entity) => {
    switch (entity) {
      case 'type':
        selectedReportType.value = event;
        break;
      case 'exploitation':
        selectedExploitation.value = event;
        await getProducts(false);
        break;
    }
  }
  
  const isValid = () => {
    if (
      billingObjects.value.length == 0 &&
      dateRange.value == null &&
      remittanceObjects.value.length == 0 &&
      selectedPersons.value.length == 0 &&
      selectedContracts.value.length == 0 &&
      !hasSerieFinalSelection.value
    ) {
      toast.warning(t('warning_block.nothing_selected_warning'))
      return false
    }
    if (serieFinalRangeError.value) {
      toast.warning(t(serieFinalRangeError.value))
      return false
    }
    return true
  }
  
  const showDetail = (component, id) => {
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
  }
  
  const closeRegion = () => {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    showRegion.value = false;
  }
  
  onMounted(async () => {
    // billingId.value = route.params.id;
    await getExploitations();
    await getProducts();
    getPaymentTypes();
    getReportTypes();
    getSeries();
    fetchActiveReports();
    checkQueueStatus();
    queueInterval.value = setInterval(checkQueueStatus, 5000);
  });

  onUnmounted(() => {
    if (queueInterval.value) {
      clearInterval(queueInterval.value);
    }
    Object.values(pollIntervals).forEach(clearInterval);
  });
  
  watch(() => dateRange.value, (newValue) => {
    billingObjects.value = []
  });
  
  watch(() => activeReportsStatus.value, (newValue) => {
    if (Object.keys(newValue).length > 0) {
      openDetailedProducts.value = false
      openRegisterBillingProducts.value = false
      openSupplyTypeProducts.value = false
      openTaxesProducts.value = false
      openTaxesDetailedProducts.value = false
      openWalletPayments.value = false
    }
  }, { deep: true });
  
  const style = {
    enter: 'transition-all duration-1000 ease-out',
    enterFrom: 'opacity-0 max-h-0 overflow-hidden',
    enterTo: 'opacity-100 max-h-[500px] overflow-hidden',
    leave: 'transition-all duration-600 ease-in',
    leaveFrom: 'opacity-100 max-h-[500px] overflow-hidden',
    leaveTo: 'opacity-0 max-h-0 overflow-hidden'
  }
  </script>
  
  <template>
    <div>
  
      <div>
        <H1>{{ t('common.reports') }}</H1>
        <div v-if="loding || loadingReportsList">
          <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else>
          <!-- Cua de Processos d'Informes -->
          <div v-if="fullQueueList.length > 0" class="mb-6 border border-slate-200 rounded-md bg-slate-50 p-4">
            <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Icon name="fa6-solid:list-check" class="text-sky-600" />
              {{ $t('reports_queue_title') }}
            </h3>

            <!-- Processos Actius -->
            <div v-if="runningTasks.length > 0" class="mb-4">
              <div class="space-y-3 mt-2">
                <div v-for="item in runningTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
                  <div class="flex justify-between items-start mb-1 text-sm">
                    <span class="font-semibold text-amber-900">
                      {{ item.report_name || 'Report ' + item.report_id }}
                    </span>
                    <span class="text-xs font-bold px-2 py-0.5 rounded bg-amber-500 text-amber-800">
                      {{ $t('running') }}
                    </span>
                  </div>
                  <div class="text-xs text-amber-800 mb-1">
                    <span>{{ item.processed_items }} / {{ item.total_items }} ({{ item.percent }}%)</span>
                  </div>
                  <AtomsProgressBar :progress="item.percent" :error="false" />
                </div>
              </div>
            </div>

            <!-- Processos Pendents -->
            <div v-if="pendingTasks.length > 0" class="mb-4">
              <button type="button" @click="showPendingList = !showPendingList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
                <span>{{ $t('queued_processes') }} ({{ pendingTasks.length }})</span>
                <Icon :name="showPendingList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
              </button>
              
              <div v-if="showPendingList" class="space-y-3 mt-2">
                <div v-for="item in pendingTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
                  <div class="flex justify-between items-start mb-1 text-sm">
                    <span class="font-semibold text-amber-900">
                      {{ item.report_name || 'Report ' + item.report_id }}
                    </span>
                    <span class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                      {{ $t('queued_pending') }}
                    </span>
                  </div>
                  <div class="text-xs text-amber-800 mb-1">
                    <span>{{ $t('waiting_in_queue_turn') }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Historial de Processos Finalitzats -->
            <div v-if="finishedTasks.length > 0">
              <button type="button" @click="showFinishedList = !showFinishedList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
                <span>{{ $t('last_finished_processes') }} ({{ finishedTasks.length }})</span>
                <Icon :name="showFinishedList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
              </button>
              
              <div v-if="showFinishedList" class="max-h-60 overflow-y-auto divide-y divide-slate-200 bg-white rounded-md border border-slate-200 mt-2">
                <div v-for="item in finishedTasks" :key="item.id" class="p-3 flex justify-between items-center text-sm">
                  <div class="min-w-0">
                    <p class="font-medium text-slate-700 truncate">
                      {{ item.report_name || 'Report ' + item.report_id }}
                    </p>
                    <p v-if="item.status === 'warning' && item.error_message" class="text-xs text-amber-700 mt-1 italic">
                      {{ item.error_message }}
                    </p>
                    <p v-else-if="item.status === 'failed' && item.error_message" class="text-xs text-red-600 mt-1 italic">
                      Error: {{ item.error_message }}
                    </p>
                  </div>
                  <div class="flex items-center gap-3 shrink-0">
                    <span class="text-xs text-slate-400">
                      {{ item.completed_at ? new Date(item.completed_at).toLocaleString() : '' }}
                    </span>
                    <a v-if="item.status === 'completed' && item.document_url" :href="item.document_url.startsWith('http') ? item.document_url : useRuntimeConfig().public.apiHost + item.document_url" download class="text-sky-500 hover:text-sky-700 flex items-center gap-1 font-semibold mr-2" target="_blank">
                      <Icon name="fa6-solid:download" />
                      {{ $t('common.download') }}
                    </a>
                    <button v-else-if="item.status === 'completed' && item.document_id" @click="downloadQueueDocument(item.document_id, item.document_name)" class="text-sky-500 hover:text-sky-700 flex items-center gap-1 font-semibold mr-2">
                      <Icon name="fa6-solid:download" />
                      {{ $t('common.download') }}
                    </button>
                    <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold" 
                      :class="item.status === 'completed' ? 'bg-green-100 text-green-800' : item.status === 'warning' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'">
                      <Icon :name="item.status === 'completed' ? 'fa6-solid:circle-check' : item.status === 'warning' ? 'fa6-solid:triangle-exclamation' : 'fa6-solid:circle-xmark'" />
                      {{ item.status === 'completed' ? $t('correct') : item.status === 'warning' ? $t('common.warning') : $t('failed') }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <Tabs>
            <li v-for="sec in sections" :key="sec.token" class="me-2">
              <a href="#" @click.prevent="setActiveTab(sec.token)"
                :class="{ 'text-sky-600 border-sky-600 font-semibold': activeTab === sec.token, 'hover:text-gray-600 hover:border-gray-300': activeTab !== sec.token }">
                <Icon :name="getSectionIcon(sec.token)" class="display-inline mr-2" />{{ sec.name }}
              </a>
            </li>
          </Tabs>
  
          <div class="grid grid-cols-[2fr,1fr] gap-4 mb-10 mt-4">
            <!-- Left Panel: Lists of reports under active tab -->
            <div class="space-y-4">
              <section v-for="sec in sections" :key="sec.token" v-show="activeTab === sec.token" role="tabpanel" class="bg-white antialiased">
                <ul class="divide-y divide-slate-100 border border-slate-200 rounded-lg shadow-sm bg-white overflow-hidden">
                  <li v-for="report in sec.reports" :key="report.id" class="p-4 transition-all duration-300 hover:bg-slate-50/50">
                    
                    <!-- CAS A: Informe Estàndard (Botó de descàrrega directe, sense acordió) -->
                     <div v-if="!isCustomReport(report)" class="flex flex-col w-full">
                       <div class="flex justify-between items-center w-full">
                         <div class="flex-1 pr-4">
                           <div class="flex items-center gap-2">
                             <span class="font-semibold text-slate-800">{{ report.name }}</span>
                           </div>
                           <p class="text-xs text-slate-500 mt-1" :title="report.description">{{ report.description || t('reports_block.no_description') }}</p>
                         </div>
                         <div class="flex items-center gap-3">
                            <template v-if="activeReportsStatus[report.id] && activeReportsStatus[report.id].status === 'pending'">
                              <Icon name="mdi:loading" class="animate-spin text-sky-500 text-lg" />
                              <span class="text-xs text-slate-500">Esperant el seu torn a la cua...</span>
                            </template>
                            <template v-else>
                              <button class="button-secondary font-medium" 
                                @click="handleReportDownload(report, {})">
                                <Icon name="fa6-solid:file-excel" class="mr-2" />
                                {{ report.download_button_name || t('common.download') }}
                              </button>
                            </template>
                         </div>
                       </div>
                       
                       <!-- running progress bar for standard report -->
                       <div v-if="activeReportsStatus[report.id] && activeReportsStatus[report.id].status === 'running'" class="mt-2 w-full">
                         <div class="flex justify-between items-center text-xs text-sky-700 mb-1 px-1">
                           <span class="font-medium flex items-center gap-1">
                             <Icon name="mdi:loading" class="animate-spin text-sky-500" />
                             Generant informe...
                           </span>
                           <span>{{ activeReportsStatus[report.id].percent || 0 }}% ({{ activeReportsStatus[report.id].processed_items || 0 }} / {{ activeReportsStatus[report.id].total_items || 0 }})</span>
                         </div>
                         <div class="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
                           <div class="bg-sky-500 h-full transition-all duration-300 ease-out" :style="{ width: (activeReportsStatus[report.id].percent || 0) + '%' }"></div>
                         </div>
                       </div>
                     </div>

                    <!-- CAS B: Informe Personalitzat (Acordió expandible) -->
                    <div v-else class="w-full">
                      <div class="flex justify-between items-center cursor-pointer" @click="toggleReport(report.id)">
                        <div class="flex-1 pr-4">
                          <div class="flex items-center gap-2">
                            <span class="font-semibold text-slate-800 hover:text-sky-600 transition-colors">{{ report.name }}</span>
                            <span class="text-[10px] bg-blue-100 text-blue-800 font-bold px-1.5 py-0.5 rounded uppercase">{{ t('common.custom') }}</span>
                          </div>
                          <p class="text-xs text-slate-500 mt-1 line-clamp-2" :title="report.description">{{ report.description || t('reports_block.no_description') }}</p>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon :name="expandedReportId === report.id ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" class="text-slate-400 w-4 h-4" />
                        </div>
                      </div>

                      <Transition :enter-active-class="style.enter" :enter-from-class="style.enterFrom"
                        :enter-to-class="style.enterTo" :leave-active-class="style.leave" :leave-from-class="style.leaveFrom"
                        :leave-to-class="style.leaveTo">
                        <div v-if="expandedReportId === report.id" class="mt-4 pt-4 border-t border-slate-100">
                          <component
                            :is="customComponent(report) || OrganismsGenericReportForm"
                            :report="report"
                            :queueItem="activeReportsStatus[report.id]"
                            :exploitationOptions="exploitationOptions"
                            :loadingExploitations="loadingExploitations"
                            :reportTypes="reportTypes"
                            :paymentTypes="paymentTypes"
                            :products="products"
                            :selectedBilling="selectedBilling"
                            :selectedRemittance="selectedRemittance"
                            :globalDateRange="dateRange"
                            :globalExploitationId="selectedExploitation?.code || 'all'"
                            :globalIncludePreinvoices="includePreinvoices"
                            @download="handleReportDownload"
                            @select-billing="showDetail('BillingForm', null)"
                            @select-remittance="showDetail('SEPARemittanceList', null)"
                            @unselect-billing="unselectBilling"
                            @unselect-remittance="unselectRemittance"
                          />
                        </div>
                      </Transition>
                    </div>

                  </li>
                </ul>
              </section>
            </div>

            <!-- Right Panel: Global Selection summary dashboard -->
            <div class="bg-slate-50 border border-slate-200 rounded-lg p-5 h-fit shadow-sm space-y-4">
              <h3 class="font-bold text-slate-800 mb-1 text-xs uppercase tracking-wider border-b border-slate-200 pb-2">{{ t('reports_block.global_filters') }}</h3>
              
              <!-- Report Type dropdown -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('reports_block.report_type') }}</label>
                <v-select class="block w-full custom-select bg-white rounded" :model-value="selectedReportType" :clearable="false"
                  @update:modelValue="updateSelect($event, 'type')" :options="reportTypes" />
              </div>

              <!-- Exploitation Dropdown selection (Generic Global filter) -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('exploitation') }}</label>
                <v-select class="block w-full custom-select bg-white rounded" :model-value="selectedExploitation" :clearable="false"
                  :loading="loadingExploitations" @update:modelValue="updateSelect($event, 'exploitation')"
                  :options="exploitationOptions" />
              </div>

              <!-- Generic Datepicker filter (Generic Global filter) -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('billing_block.date_range') }}</label>
                <Datepicker class="block w-full custom-select bg-white rounded" :placeholder="t('reports_block.select_dates')"
                  v-model="dateRange" range :enable-time-picker="false" format="dd-MM-yyyy" />
              </div>
  
              <!-- Billing selected box (multi-select) -->
              <div v-if="billingObjects.length > 0 || !dateRange">
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('billing') }}</label>
                <div v-for="billing in billingObjects" :key="billing.id" class="relative group mb-2">
                  <div role="row" class="pt-2 pb-2 px-4 text-xs bg-green-50 border border-green-300 rounded font-medium text-green-800">
                    <FieldDetail :label='$t("common.code")' :value="billing.token"></FieldDetail>
                    <FieldDetail :label='$t("common.name")' :value="billing.name"></FieldDetail>
                  </div>
                  <button @click="unselectBilling(billing)"
                    class="absolute cursor-pointer shadow-md border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                    <Icon name="fa6-solid:xmark" class="m-auto text-red-500" />
                  </button>
                </div>
                <ButtonOutline class="w-full text-xs" @click="showDetail('BillingForm', null)">
                  {{ billingObjects.length > 0 ? t('reports_block.select_billing') + ' (+)' : t('reports_block.select_billing') }}
                </ButtonOutline>
              </div>

              <!-- Remittance selected box (multi-select) -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('common.remittance') }}</label>
                <div v-for="remittance in remittanceObjects" :key="remittance.id" class="relative group mb-2">
                  <div role="row"
                    class="py-2 px-4 text-xs bg-green-50 border border-green-300 rounded font-medium text-green-800 grid grid-cols-2 gap-x-2">
                    <FieldDetail class="col-span-2" :label='$t("common.remittance")' :value="remittance.token">
                    </FieldDetail>
                    <FieldDetail :label='$t("billing_block.payments")'
                      :value="(remittance.total_payments).toString()"></FieldDetail>
                    <AtomsColorBadge :value="remittance.status_name" :color="remittance.status_color" />
                  </div>
                  <button @click="unselectRemittance(remittance)"
                    class="absolute cursor-pointer shadow-md border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                    <Icon name="fa6-solid:xmark" class="m-auto text-red-500" />
                  </button>
                </div>
                <ButtonOutline class="w-full text-xs" @click="showDetail('SEPARemittanceList', null)">
                  {{ remittanceObjects.length > 0 ? t('reports_block.select_remittance') + ' (+)' : t('reports_block.select_remittance') }}
                </ButtonOutline>
              </div>

              <!-- Person selected box (multi-select) -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('person') }}</label>
                <div v-for="p in selectedPersons" :key="p.id" class="relative group mb-2">
                  <div role="row" class="pt-2 pb-2 px-4 text-xs bg-green-50 border border-green-300 rounded font-medium text-green-800">
                    <FieldDetail :label='$t("common.code")' :value="p.token"></FieldDetail>
                    <FieldDetail :label='$t("common.name")' :value="p.full_name"></FieldDetail>
                  </div>
                  <button @click="unselectPerson(p)"
                    class="absolute cursor-pointer shadow-md border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                    <Icon name="fa6-solid:xmark" class="m-auto text-red-500" />
                  </button>
                </div>
                <ButtonOutline class="w-full text-xs" :disabled="selectedContracts.length > 0" :class="{ 'opacity-50 cursor-not-allowed': selectedContracts.length > 0 }" @click="selectedContracts.length === 0 && showDetail('AddPersons', null)">
                  {{ selectedPersons.length > 0 ? t('reports_block.select_person') + ' (+)' : t('reports_block.select_person') }}
                </ButtonOutline>
              </div>

              <!-- Contract selected box (multi-select) -->
              <div>
                <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('contract') }}</label>
                <div v-for="c in selectedContracts" :key="c.id" class="relative group mb-2">
                  <div role="row" class="pt-2 pb-2 px-4 text-xs bg-green-50 border border-green-300 rounded font-medium text-green-800">
                    <FieldDetail :label='$t("common.code")' :value="c.token"></FieldDetail>
                    <FieldDetail :label='$t("contract_block.holder")' :value="c.holder_full_name"></FieldDetail>
                  </div>
                  <button @click="unselectContract(c)"
                    class="absolute cursor-pointer shadow-md border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                    <Icon name="fa6-solid:xmark" class="m-auto text-red-500" />
                  </button>
                </div>
                <ButtonOutline class="w-full text-xs" :disabled="selectedPersons.length > 0" :class="{ 'opacity-50 cursor-not-allowed': selectedPersons.length > 0 }" @click="selectedPersons.length === 0 && showDetail('AddContracts', null)">
                  {{ selectedContracts.length > 0 ? t('reports_block.select_contract') + ' (+)' : t('reports_block.select_contract') }}
                </ButtonOutline>
              </div>

              <!-- Preinvoices globally -->
              <div class="flex items-center gap-2 pt-2 border-t border-slate-200">
                <input v-model="includePreinvoices" type="checkbox" id="include_preinvoices_global" name="include_preinvoices"
                  class="checkbox text-sky-600 focus:ring-sky-500" />
                <label for="include_preinvoices_global" class="text-xs font-medium text-slate-700 cursor-pointer">{{
                  t('reports_block.include_preinvoices') }}</label>
              </div>
  
              <!-- Extra filters (collapsible) -->
              <div class="pt-2 border-t border-slate-200">
                <button type="button" @click="showExtraFilters = !showExtraFilters"
                  class="w-full flex justify-between items-center text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-800 transition-colors focus:outline-none">
                  <span>{{ t('reports_block.extra_filters') }}</span>
                  <Icon :name="showExtraFilters ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                </button>

                <div v-if="showExtraFilters" class="mt-3 space-y-4">
                  <!-- Rang de numero de factura (mateix filtre que general-billing-summary) -->
                  <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('reports_block.serie_final_range_group') }}</label>
                    <input v-model="serieFinalPrefix" type="text" class="input text-xs mb-2"
                      :placeholder="t('reports_block.serie_final_prefix')" />
                    <div class="grid grid-cols-2 gap-2">
                      <input v-model="serieFinalFrom" type="text" class="input text-xs"
                        :placeholder="t('reports_block.serie_final_from')" />
                      <input v-model="serieFinalTo" type="text" class="input text-xs"
                        :placeholder="t('reports_block.serie_final_to')" />
                    </div>
                    <p v-if="serieFinalRangeError" class="text-[11px] text-red-600 mt-1">
                      {{ t(serieFinalRangeError) }}
                    </p>
                    <p v-else class="text-[11px] text-slate-400 mt-1 leading-relaxed">
                      {{ t('reports_block.serie_final_range_hint') }}
                    </p>
                  </div>

                  <!-- Serie multi-select -->
                  <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('billing_block.serie') }}</label>
                    <v-select class="block w-full custom-select bg-white rounded" v-model="selectedSeries"
                      :options="seriesOptions" :loading="loadingSeries" :multiple="true"
                      :placeholder="t('billing_block.serie')" />
                  </div>

                  <!-- Excluded billing box (single-select) -->
                  <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('reports_block.exclude_billing') }}</label>
                    <div v-for="billing in excludedBillingObjects" :key="billing.id" class="relative group mb-2">
                      <div role="row" class="pt-2 pb-2 px-4 text-xs bg-red-50 border border-red-300 rounded font-medium text-red-800">
                        <FieldDetail :label='$t("common.code")' :value="billing.token"></FieldDetail>
                        <FieldDetail :label='$t("common.name")' :value="billing.name"></FieldDetail>
                      </div>
                      <button @click="unselectExcludeBilling(billing)"
                        class="absolute cursor-pointer shadow-md border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                        <Icon name="fa6-solid:xmark" class="m-auto text-red-500" />
                      </button>
                    </div>
                    <ButtonOutline class="w-full text-xs" @click="showDetail('ExcludeBillingForm', null)">
                      {{ t('reports_block.select_exclude_billing') }}
                    </ButtonOutline>
                  </div>
                </div>
              </div>

              <div class="text-[11px] text-slate-400 bg-slate-100 p-3 rounded border border-slate-200/50 leading-relaxed">
                <Icon name="fa6-solid:circle-info" class="text-slate-500 mr-1" />
                {{ t('reports_block.global_filters_info') }}
              </div>
            </div>
          </div>
  
        </div>
      </div>

      <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2"
        :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="closeRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10">
          <AddBillings v-if="showRegionDetailComponent == 'BillingForm'" :selected_items="billingObjects"
            @item-clicked="onBillingSelected" :multiple="true" />
          <AddBillings v-if="showRegionDetailComponent == 'ExcludeBillingForm'" :selected_items="excludedBillingObjects"
            @item-clicked="onExcludeBillingSelected" :multiple="false" />
          <SEPARemittanceList v-if="showRegionDetailComponent == 'SEPARemittanceList'" :selected_items="remittanceObjects"
            @item-clicked="onRemittanceSelected" :allow_select="true" :multiple="true" />
          <AddPersons v-if="showRegionDetailComponent == 'AddPersons'" :selected_items="selectedPersons"
            @item-clicked="onPersonSelected" :multiple="true" />
          <AddContracts v-if="showRegionDetailComponent == 'AddContracts'" :selected_items="selectedContracts"
            @item-clicked="onContractSelected" :multiple="true" />
        </div>
      </div>
    </div>
  </template>