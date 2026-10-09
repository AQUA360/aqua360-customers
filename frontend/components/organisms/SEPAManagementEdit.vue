<script setup>
import { add, format } from 'date-fns';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import AddInvoices from '../molecules/AddInvoices.vue';
import AddContracts from '../molecules/AddContracts.vue';
import SelectorType from '../atoms/SelectorType.vue';	
import ButtonOutline from '../atoms/ButtonOutline.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import ContractRegion from './ContractRegion.vue';
import SEPAPaymentsList from './SEPAPaymentsList.vue';
import SEPAAnomalyPaymentsList from './SEPAAnomalyPaymentsList.vue';
import SEPADocumentsPreviewList from './SEPADocumentsPreviewList.vue';
import CompanyBankRouting from '../molecules/CompanyBankRouting.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast();
const objectPermissions = ref(null);
const { $apiManager, $ConfiglistApiService, $PaymentApiService, $ConfigProjectApiService, $ExploitationApiService, $DocumentManagerApiService, $BillingApiService } = useNuxtApp();

const emit = defineEmits(['refresh']);

const props = defineProps({
  onlyReturn: {
    type: Boolean,
    default: false,
  },
  onlySEPA: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(true);
const loadingPayment = ref(false)

const is_fetching = ref(false)
const saving = ref(false)
const attemptedSave = ref(false)

const loadingExploitations = ref(false)
const loadingBillings = ref(false)
const loadingOrigins = ref(false)
const loadingBanks = ref(false)
const loadingInvoiceStatuses = ref(false)
const loadingPaymentStatuses = ref(false)

const paymentsType = ref( props.onlyReturn ? 'return' : 'invoice')
const include_excluded = ref(false)
// En cercar, marca com a exclosos els pagaments de contractes amb factures
// pendents de pagar (vençudes/impagades), sense comptar les de despeses
// d'impagats. No els treu del llistat: queden a la pestanya "Exclosos".
const excludeContractsWithPendingInvoices = ref(false)
const useRemittanceDate = ref(false)

const paymentsTypeOptions = ref([])

// Empreses emissores de la remesa. El repartiment entre els comptes de cada
// empresa el decideix el seu mapa d'encaminament (fitxa d'empresa > Encaminament
// de remeses), segons l'entitat bancària del pagador: es genera un fitxer SEPA
// per cada compte que hi acabi tenint rebuts.
const companies = ref([])
const selectedCompanies = ref([])
// { id_pagament: id_compte } per als rebuts que l'usuari mou a mà, per sobre
// del que digui el mapa.
const bankAssignments = ref({})
// ConfigProject `use_manual_bank_remittance`: es tria a mà un únic compte i tots
// els rebuts es remesen per aquell compte, com abans de l'encaminament per
// entitat del pagador. No es filtra per empresa ni es fa servir el mapa.
const useManualBankRemittance = ref(false)
const selectedBank = ref(null)
const selectedSendDate = ref(new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
const maxTotalRemittance = ref(0);

// Part del payload comuna a la cerca, la previsualització i la generació: així
// els recomptes de fitxers i la remesa final es calculen amb el mateix repartiment.
const banksPayload = () => {
  if (useManualBankRemittance.value) {
    return { selected_bank: selectedBank.value ? selectedBank.value.value : null }
  }
  return {
    selected_companies: selectedCompanies.value.map(company => company.value),
    bank_assignments: { ...bankAssignments.value },
  }
}

// Sense encaminament hi ha un sol compte, així que el que cal tenir triat és el
// compte i no l'empresa emissora.
const hasRemittanceTarget = computed(() =>
  useManualBankRemittance.value ? Boolean(selectedBank.value) : selectedCompanies.value.length > 0
)

const filter_send_date_start = ref(null)
const filter_send_date_end = ref(null)
const filter_issue_date_start = ref(null)
const filter_issue_date_end = ref(null)
const filter_due_date_start = ref(null)
const filter_due_date_end = ref(null)

const company_banks = ref([])
const exploitations = ref([])
const billings = ref([])
const invoiceStatuses = ref([])
const paymentStatuses = ref([])
const origins = ref([])

const selectedExploitation = ref(null)
const selectedBilling = ref(null)
const selectedOrigins = ref(null);
const selectedInvoiceStatuses = ref([])
const selectedPaymentStatuses = ref([])
const selectedContracts = ref([])
const selectedInvoices = ref([])
const selectedCommitment = ref(null)        //DE MOMENT NOMÉS INFO, NO FILTRAR DIRECTAMENT

const payments = ref([]);
const anomalies = ref([]);
const sepa_files_preview = ref([]);
const total_anomalies = ref(0);
const total_amount = ref(0);
const total_excluded = ref(0);
const total_invoices = ref(0);
const total_sepa_files = ref(0);
// Avisos de l'encaminament (rebuts sense IBAN, empreses sense compte per
// defecte...). No bloquegen mai la generació, només informen.
const routingWarnings = ref([]);

// Empresa que s'està revisant a la region d'encaminament. Es pot obrir des
// d'aquí mateix per repassar o retocar el mapa abans de generar la remesa.
const routingCompanyId = ref(null);
const lastSearchData = ref(null);

// Pestanyes del llistat de pagaments: 'included' és el que es remesarà i
// 'excluded' el que no, per poder revisar-ho abans de generar el document.
const paymentsListTab = ref('included')
const showRegionDetailComponent = ref(null)
const regionDetailId = ref(null)
const isSubRegionOpen = ref(false);

const showAdditionalFilters = ref(false);

const highlightFooter = ref(false);

const taskId = ref(null);
const loadingTask = ref(false);

/* ---- NOU: mesura dinàmica de l'alçada del footer fix ---- */
const footerRef = ref(null)
const footerHeight = ref(96) // valor per defecte raonable mentre no s'ha mesurat encara
let footerResizeObserver = null


const includedPaymentsSearchData = computed(() => (
  lastSearchData.value ? { ...lastSearchData.value, include_excluded: false, only_excluded: false } : null
))
const excludedPaymentsSearchData = computed(() => (
  lastSearchData.value ? { ...lastSearchData.value, include_excluded: true, only_excluded: true } : null
))
const totalToRemit = computed(() => Math.max(0, (Number(total_invoices.value) || 0) - (Number(total_excluded.value) || 0)))

const computedAllowSearch = computed(() => {
  const anyEspecificFilter = selectedInvoices.value.length > 0 || selectedContracts.value.length > 0 || filter_send_date_start.value || (filter_send_date_start.value && filter_send_date_end.value);
  /* if (selectedBilling.value || (selectedExploitation.value && selectedOrigins.value) || anyEspecificFilter) return false; */
  if (selectedBilling.value || selectedExploitation.value || anyEspecificFilter) return false;
  return true;
})

// `applyPendingInvoicesExclusion`: només les cerques que fa l'usuari tornen a
// marcar els rebuts de contractes amb impagats. Els refrescos que demana el
// llistat (`@change`) no ho fan, si no seria impossible tornar a incloure'n un:
// el refresc posterior el tornaria a excloure.
const search = async (applyPendingInvoicesExclusion = true) => {
  is_fetching.value = true;
  try {
    const searchData = {
      exploitation: selectedExploitation.value ? selectedExploitation.value.value : null,
      billing: selectedBilling.value ? selectedBilling.value.value : null,
      origin: selectedOrigins.value ? selectedOrigins.value.value : null,

      payments_type: paymentsType.value,

      contracts: selectedContracts.value.map(contract => contract.id),
      invoices: selectedInvoices.value.map(invoice => invoice.id),
      commitment: selectedCommitment.value ? selectedCommitment.value.id : null,

      invoice_statuses: selectedInvoiceStatuses.value.map(status => status.value),
      payment_statuses: selectedPaymentStatuses.value.map(status => status.value),

      send_date_start: filter_send_date_start.value,
      send_date_end: filter_send_date_end.value,
      issue_date_start: filter_issue_date_start.value,
      issue_date_end: filter_issue_date_end.value,
      due_date_start: filter_due_date_start.value,
      due_date_end: filter_due_date_end.value,
      use_remittance_date: useRemittanceDate.value,

      ...banksPayload(),
    }

    // El filtre de contractes amb impagats no redueix el llistat: marca aquests
    // pagaments com a exclosos, de manera que compten al comptador d'exclosos i
    // es poden revisar (i tornar a incloure) des de la pestanya "Exclosos".
    if (excludeContractsWithPendingInvoices.value && applyPendingInvoicesExclusion) {
      try {
        await $PaymentApiService.bulkExcludeSEPAInvoices(
          { ...searchData, only_contracts_with_pending_invoices: true }, true
        );
      } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
      }
    }

    const result = await $PaymentApiService.getSEPADocData(searchData)
    
    total_invoices.value = result.total_invoices || 0;
    total_amount.value = result.total_amount || 0;
    total_anomalies.value = result.total_anomalies || 0;
    total_excluded.value = result.total_excluded || 0;
    total_sepa_files.value = result.total_sepa_files || 0;
    routingWarnings.value = result.routing_warnings || [];
    
    lastSearchData.value = { ...searchData };

  } catch (error) {
    console.error(error);
  }
  finally {
    is_fetching.value = false;
  }
}

const loadDataFromPaymentQuery = async (payment_id) => {
  loadingPayment.value = true;
  try {
    const result = await $PaymentApiService.getDetail(payment_id);
    console.log("result", result);
    if (result.invoice) {
      selectedInvoices.value = [{ id: result.invoice.id, serie_final: result.invoice.serie_final }];
      console.log("result.invoice.send_at", result.invoice);
      if (result.invoice.send_at) {
        selectedSendDate.value = result.invoice.send_at.split('T')[0];
      }
    } else if (result.commitment_deposit) {
      await nextTick(() => {
        paymentsType.value = 'commitment';
      });
      selectedCommitment.value = { id: result.commitment_deposit.id, token: result.commitment_deposit.token };
    }
    search();
  } catch (error) {
    console.error(error);
  }
  finally {
    loadingPayment.value = false;
  }
}

const clickFinalize = async () => {
  attemptedSave.value = true;
  if (!isValid()) return
  if (total_anomalies.value > 0){
    if (!confirm(t('warning_block.warning_anomalies_found'))) return
  }
  saving.value = true;
  try {
    const searchData = {
      
      ...banksPayload(),
      selected_send_date: selectedSendDate.value,
      maxTotalRemittance: maxTotalRemittance.value,

      exploitation: selectedExploitation.value ? selectedExploitation.value.value : null,
      billing: selectedBilling.value ? selectedBilling.value.value : null,
      origin: selectedOrigins.value ? selectedOrigins.value.value : null,

      payments_type: paymentsType.value,

      contracts: selectedContracts.value.map(contract => contract.id),
      invoices: selectedInvoices.value.map(invoice => invoice.id),
      commitment: selectedCommitment.value ? selectedCommitment.value.id : null,

      invoice_statuses: selectedInvoiceStatuses.value.map(status => status.value),
      payment_statuses: selectedPaymentStatuses.value.map(status => status.value),

      send_date_start: filter_send_date_start.value,
      send_date_end: filter_send_date_end.value,
      issue_date_start: filter_issue_date_start.value,
      issue_date_end: filter_issue_date_end.value,
      due_date_start: filter_due_date_start.value,
      due_date_end: filter_due_date_end.value,

      include_excluded: include_excluded.value,
      use_remittance_date: useRemittanceDate.value,
      create_doc: true,
    }

    if (selectedBilling.value && selectedSendDate.value) {
      try {
        await $BillingApiService.patch(selectedBilling.value.value, {
          send_at: new Date(selectedSendDate.value).toISOString()
        });
      } catch (err) {
        console.error("Error actualitzant send_at a la facturació", err);
      }
    }

    const result = await $PaymentApiService.getSEPADocData(searchData)
    
    if (result){
      // console.log("result", result);
      // console.log("result.document_ids", result.document_ids);
      // await downloadSEPADocument(result.document_ids);

      //return navigateTo('/billing/sepa');
      taskId.value = result.task_id;
    }

  } catch (error) {
    console.error(error);
  }
  finally {
    saving.value = false;
  }
}

const downloadSEPADocument = async (document_ids) => {
  try {
    let save_data = {
      doc_ids: document_ids
    }
    const file = await $DocumentManagerApiService.downloadDocuments(save_data);
    const blob = new Blob([file], { type: 'application/zip' });

    const url = window.URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `${paymentsType.value == 'return' ? 'TRF' : 'SEPA'} ${selectedSendDate.value.replace(/-/g, '')}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error(error);
  }
}

// Els comptes es carreguen igualment, però ja no per triar-los: serveixen per
// al desplegable d'excepcions del llistat de rebuts i per etiquetar els fitxers.
const getCompanyBanks = async () => {
  if (useManualBankRemittance.value) return getManualCompanyBanks();
  loadingBanks.value = true;
  try {
    const result = await $ExploitationApiService.getCompanyBanks('', { is_active: true });
    company_banks.value = [];
    result.results.forEach(bank => {
      if (company_banks.value.find(c => c.value == bank.id)) return
      let bank_name = bank.bank.name + ' - ' + bank.iban.slice(-4)
      if (bank.company_name) bank_name = bank.company_name + ' · ' + bank_name
      company_banks.value.push({
        value: bank.id,
        label: bank.is_sepa ? bank_name + ' - (SEPA)' : bank_name,
        company: bank.company,
      })
    })
  } catch (err) {
    console.error(err);
  }
  finally {
    loadingBanks.value = false;
  }
}

// Mode manual (`use_manual_bank_remittance`): els comptes de l'empresa de
// l'explotació, amb el compte SEPA preseleccionat.
const getManualCompanyBanks = async () => {
  loadingBanks.value = true;
  try {
    const result = await $ExploitationApiService.getCompanyBanks(selectedExploitation?.value?.company || '');
    company_banks.value = [];
    result.results.forEach(bank => {
      if (company_banks.value.find(c => c.value == bank.id)) return
      let bank_name = bank.bank.name + ' - ' + bank.iban.slice(-4)
      company_banks.value.push({
        value: bank.id,
        label: bank.is_sepa ? bank_name + ' - (SEPA)' : bank_name,
        company: bank.company,
      })
      if (bank.is_sepa) {
        selectedBank.value = { value: bank.id, label: bank_name + ' - (SEPA)', company: bank.company }
      }
    })
  } catch (err) {
    console.error(err);
  }
  finally {
    loadingBanks.value = false;
  }
}

// getAll() i no get(): get() llegeix d'una cache a localStorage sense caducitat
// i no veuria un canvi del valor al backend.
const loadManualBankRemittanceConfig = async () => {
  try {
    const response = await $ConfigProjectApiService.getAll('use_manual_bank_remittance');
    const value = Array.isArray(response) && response.length > 0 ? response[0].value : null;
    useManualBankRemittance.value = value === true || value === 'true' || value === 'True';
  } catch (error) {
    console.error(error);
    useManualBankRemittance.value = false;
  }
}

const getCompanies = async () => {
  try {
    const result = await $ExploitationApiService.getCompanies('', 1, null, false, { page_size: 200 });
    companies.value = (result.results || []).map(company => ({
      value: company.id,
      label: company.alias || company.name,
    }))
    // Amb una sola empresa emissora no hi ha res a triar.
    if (!selectedCompanies.value.length && companies.value.length === 1) {
      selectedCompanies.value = [companies.value[0]]
    }
  } catch (err) {
    console.error(err);
  }
}

const selectedExploitationCompany = computed(() => selectedExploitation.value?.company || null)

// L'encaminament només s'ofereix per a les empreses amb més d'un compte: amb
// un de sol no hi ha res a repartir.
const routableCompanies = computed(() =>
  useManualBankRemittance.value ? [] : selectedCompanies.value.filter(company =>
    company_banks.value.filter(bank => String(bank.company) === String(company.value)).length > 1
  )
)

// Comptes que pot triar l'usuari com a excepció: els de les empreses de la
// remesa. Si encara no n'ha triat cap, tots.
const assignableBanks = computed(() => {
  // En mode manual no hi ha excepcions per rebut: tot va al compte triat.
  if (useManualBankRemittance.value) return []
  if (!selectedCompanies.value.length) return company_banks.value
  const companyIds = selectedCompanies.value.map(company => String(company.value))
  return company_banks.value.filter(bank => companyIds.includes(String(bank.company)))
})

// Si es treu una empresa de la selecció, les excepcions cap als seus comptes
// deixen de tenir sentit i es netegen.
watch(selectedCompanies, () => {
  const values = assignableBanks.value.map(bank => String(bank.value))
  const next = {}
  Object.entries(bankAssignments.value).forEach(([paymentId, bankId]) => {
    if (values.includes(String(bankId))) next[paymentId] = bankId
  })
  bankAssignments.value = next
}, { deep: true })

const getExploitations = async () => {
  loadingExploitations.value = true;
  try {
    const result = await $ExploitationApiService.getData();
    result.results;
    result.results.forEach(exploitation => {
      exploitations.value.push({
        value: exploitation.id,
        label: exploitation.name,
        company: exploitation.company.id
      })
    })
    exploitations.value.unshift({
      value: null,
      label: `--`,
    })
    if (exploitations.value.length === 1) {
      selectedExploitation.value = { value: exploitations.value[0].value, label: exploitations.value[0].label, company: exploitations.value[0].company }
    }
    getCompanyBanks()
  } catch (err) {
    console.error(err);
  } finally {
    loadingExploitations.value = false;
  }
}
const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name || data.token,
          value: data.id
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  } finally {
    loading.value = false;
  }
}

const getPaymentStatus = async () => {
  try {
    loadingPaymentStatuses.value = true;
    const payment_status_payoff_token = await $ConfigProjectApiService.get('payment_status_payoff_token')
    const payment_status_piggy_token = await $ConfigProjectApiService.get('payment_status_piggy_token')
    const payment_status_cancelled_token = await $ConfigProjectApiService.get('payment_status_cancelled_token')
    const payment_status_irrecoverable_token = await $ConfigProjectApiService.get('payment_status_irrecoverable_token')
    const payment_status_commitment_token = await $ConfigProjectApiService.get('payment_status_commitment_token')
    const payment_status_paid_token = await $ConfigProjectApiService.get('payment_status_paid_token')

    const data = await $ConfiglistApiService.getAll('billing/payment-status');
    paymentStatuses.value = [];

    if (data.results) {
      data.results.forEach(data => {
        if (
          data.token != payment_status_payoff_token &&
          data.token != payment_status_piggy_token &&
          data.token != payment_status_cancelled_token &&
          data.token != payment_status_irrecoverable_token &&
          data.token != payment_status_commitment_token &&
          data.token != payment_status_paid_token
        ){
          paymentStatuses.value.push({
            label: data.name || data.token,
            value: data.id
          })
        }
      });
    }
  } catch (error) {
    console.error(`Error fetching payment statuses:`, error);
  } finally {
    loadingPaymentStatuses.value = false;
  }
}

const getData = async () => {
  // Abans de carregar els comptes: el mode decideix quins es demanen.
  await loadManualBankRemittanceConfig();
  getExploitations();
  getCompanyBanks();
  if (!useManualBankRemittance.value) getCompanies();
  fetchConfigData('billing', 'invoice-status', invoiceStatuses, loadingInvoiceStatuses);
  getPaymentStatus()
  fetchConfigData('pricing', 'product-origin', origins, loadingOrigins);
  fetchConfigData('billing', 'billing', billings, loadingBillings);
}

const isValid = () => {
  if (!hasRemittanceTarget.value) return false
  if (!selectedSendDate.value || selectedSendDate.value == "") return false
  return true
}

const save = async (create_document = false) => {
  try {
    let saveData = {

    }
    let data = await $PaymentApiService.getSEPADocData(saveData);
  } catch (error) {
    console.error(error);
  }
}

const onInvoiceSelected = (invoice) => {
  selectedContracts.value = [];
  if (selectedInvoices.value.find(x => x.id == invoice.id)) {
    selectedInvoices.value = selectedInvoices.value.filter(x => x.id != invoice.id);
  } else {
    selectedInvoices.value.push({
      id: invoice.id,
      serie_final: invoice.serie_final,
      send_at: invoice.send_at || null,
    });
  }
}


const onContractSelected = (contract) => {
  selectedInvoices.value = [];
  if (selectedContracts.value.find(x => x.id == contract.id)) {
    selectedContracts.value = selectedContracts.value.filter(x => x.id != contract.id);
  } else {
    selectedContracts.value.push({
      id: contract.id,
      token: contract.token,
      send_at: contract.send_at || null,
    });
  }
}

const onExcludeChange = (payment) => {
  const amountValue = typeof payment.amount === 'string' ? parseFloat(payment.amount) : payment.amount;
  const currentTotal = typeof total_amount.value === 'string' ? parseFloat(total_amount.value) : (Number(total_amount.value) || 0);
  if (payment.is_excluded) {
    total_excluded.value++;
    total_amount.value = currentTotal - amountValue;
  } else {
    total_excluded.value--;
    total_amount.value = currentTotal + amountValue;
  }
}



const openRegion = (component, id, tab = 'included') => {
  closeSubRegion();
  paymentsListTab.value = tab;
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  if (component == 'AddContracts' || component == 'AddInvoices' || component == 'PaymentsList' || component == 'AnomalyPaymentsList' || component == 'SEPADocumentsPreviewList' || component == 'CompanyBankRouting') {
    handleSubRegionEvent(true);
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const openRoutingRegion = () => {
  if (!routableCompanies.value.length) return;
  routingCompanyId.value = routableCompanies.value[0].value;
  openRegion('CompanyBankRouting', null);
}

// En tancar l'encaminament es refà la cerca: si s'hi ha tocat res, els
// comptadors i el repartiment per compte han de reflectir-ho de seguida.
const closeRoutingRegion = () => {
  closeSubRegion();
  if (lastSearchData.value) search(false);
}

const closeSubRegion = () => {
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
}


const toggleAdditional = () => {
  showAdditionalFilters.value = !showAdditionalFilters.value;
};

const triggerFooterHighlight = () => {
  highlightFooter.value = false;
  nextTick(() => {
    highlightFooter.value = true;
    setTimeout(() => (highlightFooter.value = false), 1800);
  });
};

const resetFilters = (reset_all = true) => {
  if (reset_all) {
    selectedExploitation.value = null;
    filter_send_date_start.value = null;
    filter_send_date_end.value = null;
    filter_due_date_start.value = null;
    filter_due_date_end.value = null;
  }
  selectedBilling.value = null;
  selectedOrigins.value = null;
  selectedCommitment.value = null;
  filter_issue_date_start.value = null;
  filter_issue_date_end.value = null;
  selectedContracts.value = [];
  selectedInvoices.value = [];
  payments.value = [];
  anomalies.value = [];
  sepa_files_preview.value = [];
  total_anomalies.value = 0;
  include_excluded.value = false;
  useRemittanceDate.value = false;
  excludeContractsWithPendingInvoices.value = false;
  paymentsListTab.value = 'included';
  selectedInvoiceStatuses.value = [];
  selectedPaymentStatuses.value = [];
  total_amount.value = 0;
  total_excluded.value = 0;
  total_invoices.value = 0;
  total_sepa_files.value = 0;
  routingWarnings.value = [];
  lastSearchData.value = null;
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }

  if (!props.onlyReturn) {
    paymentsTypeOptions.value = [
      { label: t('invoice'), value: 'invoice' },
      { label: t('claim_block.pay_commitments'), value: 'commitment' },
    ]
  }
  if (!props.onlySEPA) {
    paymentsTypeOptions.value.push({ label: t('common.return'), value: 'return' })
  }

  await getData();
  checkRouteQuery()
  loading.value = false;

  /* NOU: observem l'alçada real del footer per reservar espai equivalent
     sota el contingut, així els desplegables (v-select) mai queden tapats. */
  await nextTick();
  if (footerRef.value && typeof ResizeObserver !== 'undefined') {
    footerResizeObserver = new ResizeObserver(() => {
      // offsetHeight (no contentRect) perquè inclou el padding i la vora del
      // footer; si no, la region quedava més alta que l'espai lliure real.
      footerHeight.value = footerRef.value?.offsetHeight ?? footerHeight.value;
    });
    footerResizeObserver.observe(footerRef.value);
  }
});

onBeforeUnmount(() => {
  if (footerResizeObserver) {
    footerResizeObserver.disconnect();
    footerResizeObserver = null;
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'idvMng') {
    if (route.query.payment_id) {
      loadDataFromPaymentQuery(route.query.payment_id);
    }
  }
}

const getFiles = async () => {
  try {
    const res = await $apiManager.checkTask(taskId.value)
    if (res && res.result?.document_ids.length > 0){
      await downloadSEPADocument(res.result.document_ids);
    }
    if (paymentsType.value == 'return') {
      return navigateTo('/billing/transfer');
    } else {
      return navigateTo('/billing/sepa');
    }
  } catch (error) {
    console.error(error);
  } finally {
    loadingTask.value = false;
    taskId.value = null;
  }
}



watch(paymentsType, () => {
  resetFilters(false);
});

watch(selectedExploitation, () => {
  if (!selectedExploitation.value) {
    selectedOrigins.value = null;
  }
});

watch(
  [total_amount, payments, anomalies, sepa_files_preview, total_excluded, total_anomalies],
  () => {
    triggerFooterHighlight();
  }
);



watch(selectedBilling, async () => {
  if (selectedBilling.value && selectedBilling.value.value) {
    try {
      const val = selectedBilling.value.value;
      const billingDetail = await $BillingApiService.getDetail(val);
      if (billingDetail.send_at) {
        selectedSendDate.value = billingDetail.send_at.split('T')[0];
      } else {
        selectedSendDate.value = new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      }
    } catch (error) {
      console.error('Error fetching billing details:', error);
    }
  }
});

watch(selectedInvoices, () => {
  if (selectedInvoices.value.length > 0) {
    const lastInvoice = selectedInvoices.value[selectedInvoices.value.length - 1];
    if (lastInvoice.send_at) {
      selectedSendDate.value = lastInvoice.send_at.split('T')[0];
    }
  }
}, { deep: true });

watch(selectedContracts, () => {
  if (selectedContracts.value.length > 0) {
    const lastContract = selectedContracts.value[selectedContracts.value.length - 1];
    if (lastContract.send_at) {
      selectedSendDate.value = lastContract.send_at.split('T')[0];
    }
  }
}, { deep: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div
      v-else
      class="mx-auto px-4 py-4 border border-gray-300 rounded-b p-4 bg-white"
      :style="{ paddingBottom: (footerHeight + 40) + 'px' }"
    >

      <!-- Remittance Data & Summary -->
      <div class="grid grid-cols-[1fr,auto] gap-6 mb-5 pb-4 border-b border-gray-200">
        <div class="space-y-3 bg-sky-50 p-1 rounded">
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
            {{ $t('billing_block.remittance_data') }}
          </h3>
          <div class="grid grid-cols-[2fr,2fr,1fr,1fr,1fr] gap-3">
            <div v-if="useManualBankRemittance">
              <label class="block text-xs font-medium text-slate-600 mb-2">
                {{ t('common.select') }} {{ t('common.bank') }}
              </label>
              <v-select class="block w-full custom-select" v-model="selectedBank" :options="company_banks"
                :loading="loadingBanks"
                :class="{ 'invalid': attemptedSave && !selectedBank }" />
            </div>
            <div v-else>
              <label class="block text-xs font-medium text-slate-600 mb-2">
                {{ t('common.select') }} {{ t('service_block.issuing_company') }}
              </label>
              <v-select class="block w-full custom-select" v-model="selectedCompanies" :options="companies"
                :multiple="true" :loading="loadingBanks"
                :class="{ 'invalid': attemptedSave && !selectedCompanies.length }" />
              <p class="mt-1 text-[11px] leading-tight text-slate-500">
                {{ $t('billing_block.info_multiple_banks_remittance') }}
              </p>
              <button v-if="routableCompanies.length" type="button" @click="openRoutingRegion"
                class="mt-1 inline-flex items-center gap-1 text-[11px] text-sky-600 hover:text-sky-800">
                <Icon name="fa6-solid:code-branch" class="text-[10px]" />
                {{ $t('billing_block.review_bank_routing') }}
              </button>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">
                {{ $t('common.select') }} {{ $t('common.send_date_expected').toLowerCase() }}
              </label>
              <AtomsInputDate v-model="selectedSendDate" class="w-full"
              :invalid="attemptedSave && (!selectedSendDate || selectedSendDate == '')" />
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-2">
                {{ $t('billing_block.max_remittance_amount') }}
              </label>
              <div class="flex items-center gap-2 mb-1">
                <input type="number" v-model="maxTotalRemittance" class="input flex-1" />
                <abbr :title="$t('informative_block.info_max_remittance_amount')">
                  <Icon name="fa6-solid:info" class="w-3.5 h-3.5 text-slate-400 hover:text-slate-600" />
                </abbr>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-2 whitespace-nowrap">
                {{ $t('billing_block.include_payment_excluded') }}
              </label>
              <div class="flex justify-between items-center">
                <button type="button" @click="include_excluded = !include_excluded"
                  class="relative inline-flex h-6 w-11 items-center rounded-full  focus:outline-none"
                  :class="include_excluded ? 'bg-sky-500' : 'bg-gray-300'" role="switch" :aria-checked="include_excluded">
                  <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                    :class="include_excluded ? 'translate-x-6' : 'translate-x-1'" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-2 whitespace-nowrap">
                {{ $t('contract_block.use_remittance_date') }}
              </label>
              <div class="flex justify-between items-center">
                <button type="button" @click="useRemittanceDate = !useRemittanceDate"
                  class="relative inline-flex h-6 w-11 items-center rounded-full  focus:outline-none"
                  :class="useRemittanceDate ? 'bg-sky-500' : 'bg-gray-300'" role="switch" :aria-checked="useRemittanceDate">
                  <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                    :class="useRemittanceDate ? 'translate-x-6' : 'translate-x-1'" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Avisos de l'encaminament: informatius, no impedeixen generar -->
      <div v-if="routingWarnings.length"
        class="mb-4 rounded border border-amber-200 bg-amber-50 px-3 py-2">
        <p class="text-xs font-semibold text-amber-900 uppercase tracking-wide mb-1">
          {{ $t('billing_block.routing_warnings') }}
        </p>
        <ul class="text-sm text-amber-900 space-y-0.5">
          <li v-for="warning in routingWarnings" :key="warning.code" class="flex items-start gap-2">
            <Icon name="fa6-solid:triangle-exclamation" class="text-xs mt-1 shrink-0" />
            <span>
              <span class="font-semibold">{{ warning.count }}</span>
              {{ $t('billing_block.routing_warning_' + warning.code) }}
            </span>
          </li>
        </ul>
      </div>

      <!-- Filters Section -->
      <div class="space-y-4">
        <!-- <SelectorType v-model="paymentsType" :options="paymentsTypeOptions" /> -->

        <div class="grid grid-cols-2 gap-6">
          <!-- General Filters -->
          <div class="space-y-3">
            <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 border-b border-gray-100">
              {{ $t('common.general_filters') }}
            </h3>
            <div class="space-y-2.5">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.exploitation') }}
                </label>
                <v-select class="block w-full custom-select" v-model="selectedExploitation" :options="exploitations"
                  :loading="loadingExploitations" :disabled="selectedBilling != null" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.origin') }}
                </label>
                <v-select class="block w-full custom-select" v-model="selectedOrigins" :options="origins"
                  :loading="loadingOrigins"
                  :disabled="paymentsType !== 'invoice' || !!selectedBilling || (!selectedExploitation && selectedContracts.length == 0 && selectedInvoices.length == 0)" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('billing') }}
                </label>
                <v-select
                  class="block w-full custom-select custom-select-billing"
                  v-model="selectedBilling"
                  :options="billings"
                  :loading="loadingBillings"
                  :disabled="paymentsType !== 'invoice' || !!selectedExploitation || !!selectedOrigins"/>
              </div>

              <!-- <div class="flex items-center gap-3">
                <span class="text-xs" :class="{ 'text-slate-400': paymentsType === 'commitment', 'text-slate-800': paymentsType !== 'commitment' }">
                  {{ t('invoices') }}
                </span>
                <button type="button" @click="paymentsType = paymentsType === 'commitment' ? 'invoice' : 'commitment'"
                  class="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-300 focus:outline-none"
                  role="switch" :aria-checked="paymentsType === 'commitment'">
                  <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                    :class="paymentsType === 'commitment' ? 'translate-x-6' : 'translate-x-1'" />
                </button>
                <span class="text-xs" :class="{ 'text-slate-400': paymentsType !== 'commitment', 'text-slate-800': paymentsType === 'commitment' }">
                  {{ t('claim_block.pay_commitments') }}
                </span>
              </div> -->
              <SelectorType v-if="paymentsTypeOptions.length > 1" class="mb-4" v-model="paymentsType" :options="paymentsTypeOptions" />

              <div class="flex items-center justify-between gap-3">
                <label class="text-xs font-medium text-slate-600">
                  {{ $t('billing_block.exclude_contracts_with_pending_invoices') }}
                  <abbr :title="$t('billing_block.info_exclude_contracts_with_pending_invoices')">
                    <Icon name="fa6-solid:info" class="w-3.5 h-3.5 text-slate-400 hover:text-slate-600" />
                  </abbr>
                </label>
                <button type="button" @click="excludeContractsWithPendingInvoices = !excludeContractsWithPendingInvoices"
                  class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full focus:outline-none"
                  :class="excludeContractsWithPendingInvoices ? 'bg-sky-500' : 'bg-gray-300'" role="switch"
                  :aria-checked="excludeContractsWithPendingInvoices">
                  <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                    :class="excludeContractsWithPendingInvoices ? 'translate-x-6' : 'translate-x-1'" />
                </button>
              </div>

            </div>
          </div>

          <!-- Specific Filters -->
          <div class="space-y-3">
            <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 border-b border-gray-100">
              {{ $t('common.specific_filters') }}
            </h3>
            <div class="space-y-2">
              <div>
                <label class="block text-xs font-medium text-slate-600">
                  {{ $t('common.send_date_expected') }} ({{ paymentsType === 'return' ? $t('common.return') : 
                  paymentsType === 'commitment' ? $t('claim_block.commitment_payments') :
                    $t('invoice') }})
                </label>
                <div class="grid grid-cols-2 gap-2">
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.from') }}</label>
                    <AtomsInputDate v-model="filter_send_date_start" class="w-full" />
                  </div>
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.to') }}</label>
                    <AtomsInputDate v-model="filter_send_date_end" class="w-full" />
                  </div>
                </div>
              </div>
              <!-- <div>
                <SearchEntityInput :service="$ContractApiService" @select="onContractSelected"
                  :title="$t('search_block.search_contract')" :result_value="'holder_full_name'" class="w-full" />
              </div> -->
              <div class="grid grid-cols-2 gap-2">
                <ButtonOutline @click="openRegion('AddContracts', null)" :disabled="is_fetching">
                  {{ $t('common.select') }} {{ $t('contracts').toLowerCase() }}
                </ButtonOutline>

                <ButtonOutline @click="openRegion('AddInvoices', null)" :disabled="paymentsType !== 'invoice' || is_fetching">
                  {{ $t('common.select') }} {{ $t('invoices').toLowerCase() }}
                </ButtonOutline>
              </div>

              <div>
                <div v-if="selectedContracts.length == 0 && selectedInvoices.length == 0 && !selectedCommitment">
                  <p class="text-xs text-slate-400">
                    {{ $t('contract_block.no_selected_contracts') }}
                  </p>
                  <p v-if="paymentsType === 'invoice'" class="text-xs text-slate-400">
                    {{ $t('billing_block.no_selected_invoices') }}
                  </p>
                </div>
                <div v-else>
                  <p v-if="selectedCommitment" class="text-xs text-slate-500">
                    {{ t('claim_block.selected_commitment') }}
                  </p>
                  <p v-if="selectedInvoices.length > 0" class="text-xs text-slate-500">
                    {{ t('billing_block.selected_invoices') }} </p>
                  <p v-if="selectedContracts.length > 0" class="text-xs text-slate-500">
                    {{ $t('contract_block.selected_contracts') }}
                  </p>
                  <div class="flex flex-wrap gap-2 mt-1">
                    <div v-if="selectedCommitment"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ selectedCommitment.token }}</span>
                      <button type="button" @click="openRegion('CommitmentDepositRegion', selectedCommitment.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="selectedCommitment = null"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                    <div v-for="invoice in selectedInvoices" :key="invoice.id"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ invoice.serie_final }}</span>
                      <button type="button" @click="openRegion('InvoiceRegion', invoice.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="onInvoiceSelected(invoice)"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                    <div v-for="contract in selectedContracts" :key="contract.id"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ contract.token }}</span>
                      <button type="button" @click="openRegion('ContractRegion', contract.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="onContractSelected(contract)"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        <p class="text-xs text-slate-400 italic pt-1">
          {{ $t('billing_block.minimum_required_filter') }}
        </p>

        <div class="pt-3 border-t border-gray-200">
          
          <button
              type="button"
              class="w-full flex items-center justify-between gap-3 select-none
                    text-left px-2 py-2 rounded
                    hover:bg-slate-50 active:bg-slate-100
                    focus:outline-none focus:ring-2 focus:ring-sky-500/30"
              :aria-expanded="showAdditionalFilters ? 'true' : 'false'"
              :aria-controls="'additional-filters-panel'"
              @click="toggleAdditional"
            >
              <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                {{ $t('common.additional_filters') }}
              </h3>

              <!-- Indicador visual (chevron) que rota -->
              <Icon
                name="fa6-solid:chevron-down"
                class="w-4 h-4 text-slate-500 transition-transform duration-200"
                :class="{ 'rotate-180': showAdditionalFilters }"
                aria-hidden="true"
              />
            </button>
            
            <!-- Panell plegable amb transició -->
            <Transition
              enter-active-class="transition-all duration-200 ease-out"
              enter-from-class="opacity-0 -translate-y-1"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition-all duration-150 ease-in"
              leave-from-class="opacity-100 translate-y-0"
              leave-to-class="opacity-0 -translate-y-1"
            >
              <div
                v-show="showAdditionalFilters"
                :id="'additional-filters-panel'"
                class="mt-2"
              >

              <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.select') }} {{ t('common.statuses').toLowerCase() }} ({{ t('invoice') }})
                </label>
              
                <v-select
                  multiple
                  class="block w-full custom-select custom-select-small"
                  v-model="selectedInvoiceStatuses"
                  :options="invoiceStatuses"
                  :loading="loadingInvoiceStatuses"
                  :disabled="paymentsType !== 'invoice'"
                />
              </div>
            
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.select') }} {{ t('common.statuses').toLowerCase() }} ({{ t('billing_block.payment') }})
                </label>
              
                <v-select
                  multiple
                  class="block w-full custom-select custom-select-small"
                  v-model="selectedPaymentStatuses"
                  :options="paymentStatuses"
                  :loading="loadingPaymentStatuses"
                />
              </div>
            
              <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">
                      {{ $t('billing_block.issue_date') }}
                    </label>
                    <div class="grid grid-cols-2 gap-2">
                      <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.from') }}</label>
                        <AtomsInputDate v-model="filter_issue_date_start" class="w-full" :disabled="paymentsType !== 'invoice'" />
                      </div>
                      <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.to') }}</label>
                        <AtomsInputDate v-model="filter_issue_date_end" class="w-full" :disabled="paymentsType !== 'invoice'" />
                      </div>
                    </div>
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">
                      {{ $t('common.due_date') }}
                    </label>
                    <div class="grid grid-cols-2 gap-2">
                      <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.from') }}</label>
                        <AtomsInputDate v-model="filter_due_date_start" class="w-full" />
                      </div>
                      <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.to') }}</label>
                        <AtomsInputDate v-model="filter_due_date_end" class="w-full" />
                      </div>
                    </div>
                  </div>
                </div>
              
              </div>
            </Transition>
        </div>
      </div>

      <hr />
    </div>

    <!-- NOU: el rectangle inferior és el mateix div de sempre, però ara amb ref
         perquè puguem mesurar-ne l'alçada real (footerHeight) i reservar espai
         sota el contingut. Així els v-select mai queden tapats. -->
    <div
      ref="footerRef"
      :class="{ 'jquery-highlight': highlightFooter }"
      class="fixed right-0 bottom-0 z-[110] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA] flex flex-row justify-between"
      style="width: calc(100% - 250px)"
    >
      <div class="grid auto-cols-max grid-flow-col items-center gap-x-10">

        <!-- TOTAL -->
        <div class="flex flex-col">
          <div class="flex items-center gap-2">
            <div class="text-lg font-bold text-green-800 whitespace-nowrap">
              {{ formatMoneyWithCurrency(total_amount) }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="text-sm font-semibold text-green-800 whitespace-nowrap">
              {{ $t('billing_block.total_amount') }}
            </div>
          </div>
        </div>

        <!-- PAGAMENTS + EXCLOSOS + BOTÓ -->
        <div class="pr-6 mr-4 border-r border-gray-300">
          <div class="grid grid-cols-[auto,30px] items-center gap-x-4">

            <div class="flex flex-col">
              <div class="flex items-center gap-2">
                <span class="text-lg font-bold text-slate-900">{{ total_invoices }}</span>
                <span class="text-sm font-semibold text-slate-700">
                  {{ $t('billing_block.selected_payments') }}
                </span>
              </div>

              <button type="button" class="flex items-center gap-2 text-left hover:underline"
                @click="openRegion('PaymentsList', null, 'excluded')">
                <span class="text-sm font-bold text-red-700">{{ total_excluded }}</span>
                <span class="text-sm font-semibold text-red-600">
                  {{ $t('billing_block.excluded_multiple') }}
                </span>
              </button>
            </div>

            <button
              :disabled="false"
              class="w-7 h-7 bg-sky-500 text-white rounded-full flex items-center justify-center hover:bg-sky-600 transition-colors disabled:opacity-30"
              @click="openRegion('PaymentsList', null)"
            >
              <Icon name="fa6-solid:eye" class="w-3.5 h-3.5" />
            </button>

          </div>
        </div>

        <!-- ANOMALIES + BOTÓ -->
        <div class="grid grid-cols-[auto,30px] items-center gap-x-4">

          <div class="flex items-center gap-2">
            <span class="text-lg font-bold text-slate-900">{{ total_anomalies }}</span>
            <span class="text-sm font-semibold text-slate-700">
              {{ $t('common.anomalies') }}
            </span>
          </div>

          <button
            :disabled="false"
            class="w-7 h-7 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 transition-colors disabled:opacity-30"
            @click="openRegion('AnomalyPaymentsList', null)"
          >
            <Icon name="fa6-solid:exclamation" class="w-3.5 h-3.5" />
          </button>

        </div>

        <!-- SEPA PREVIEWS + BOTÓ -->
        <div class="grid grid-cols-[auto,30px] items-center gap-x-4 pl-6 border-l border-gray-300 ml-4">
          <div class="flex items-center gap-2">
            <span class="text-lg font-bold text-slate-900">{{ total_sepa_files }}</span>
            <span class="text-sm font-semibold text-slate-700">
              {{ $t('billing_block.sepa_files_generated') }}
            </span>
          </div>

          <button
            v-if="total_sepa_files > 0"
            class="w-7 h-7 bg-amber-500 text-white rounded-full flex items-center justify-center hover:bg-amber-600 transition-colors"
            @click="openRegion('SEPADocumentsPreviewList', null)"
          >
            <Icon name="fa6-solid:triangle-exclamation" class="w-3.5 h-3.5" />
          </button>
          <div v-else class="w-7 h-7"></div>
        </div>

      </div>
      <div class="flex gap-3">
        <abbr >
          <button @click="resetFilters()" class="button-default">
            <Icon name="fa6-solid:arrow-rotate-left" />&nbsp; {{ $t('common.clear') }}
          </button>
        </abbr>
        <abbr :title="computedAllowSearch ? $t('informative_block.info_filters_missing') : ''">
          <button @click="search()" :disabled="computedAllowSearch || is_fetching" class="button-default">
            <Icon :name="is_fetching ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
              :class="{ 'animate-spin': is_fetching }" />
            &nbsp; {{ $t('dashboard.search') }}
          </button>
        </abbr>
        <abbr >
          <button v-if="!taskId" @click="clickFinalize" :disabled="!hasRemittanceTarget || !selectedSendDate || total_invoices === 0"
            class="button-secondary">
            <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
          </button>
          <AtomsProcessColorBadge v-else class="h-full items-center justify-center py-2" :value="$t('common.processing')" 
          color="blue" :taskId="taskId" @refresh="getFiles()"></AtomsProcessColorBadge>
        </abbr>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[100]"
      :style="{ height: `calc(100vh - ${footerHeight}px)` }"
      :class="{
        'translate-x-0': showRegionDetailComponent,
        'translate-x-[2000px]': !showRegionDetailComponent,
        'w-[95%]': isSubRegionOpen,
        'w-[50%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegionDetailComponent === 'CompanyBankRouting' ? closeRoutingRegion() : closeSubRegion()"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddInvoices v-if="showRegionDetailComponent == 'AddInvoices'" :multiple="true"
          :height_offset="260 + footerHeight" :selected_items="selectedInvoices" @item-clicked="onInvoiceSelected" />
        <AddContracts v-if="showRegionDetailComponent == 'AddContracts'" :multiple="true"
          :height_offset="260 + footerHeight" :selected_items="selectedContracts" @item-clicked="onContractSelected" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
        <template v-if="showRegionDetailComponent === 'PaymentsList'">
          <div class="flex items-center gap-1 mb-3 border-b border-slate-200">
            <button type="button" @click="paymentsListTab = 'included'"
              class="px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors"
              :class="paymentsListTab === 'included' ? 'border-sky-500 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-700'">
              {{ $t('billing_block.payments_to_remit') }}
              <span class="ml-1 text-xs font-semibold">({{ totalToRemit }})</span>
            </button>
            <button type="button" @click="paymentsListTab = 'excluded'"
              class="px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors"
              :class="paymentsListTab === 'excluded' ? 'border-red-500 text-red-700' : 'border-transparent text-slate-500 hover:text-slate-700'">
              {{ $t('billing_block.excluded_multiple') }}
              <span class="ml-1 text-xs font-semibold">({{ total_excluded }})</span>
            </button>
          </div>
          <SEPAPaymentsList v-if="paymentsListTab === 'included'" :payments="payments"
            :searchData="includedPaymentsSearchData" :banks="assignableBanks"
            v-model:bankAssignments="bankAssignments"
            @exclude_change="onExcludeChange" @change="search(false)" />
          <SEPAPaymentsList v-else :payments="payments" :searchData="excludedPaymentsSearchData" :is_excluded="true"
            @exclude_change="onExcludeChange" @change="search(false)" />
        </template>
        <SEPAAnomalyPaymentsList v-if="showRegionDetailComponent === 'AnomalyPaymentsList'" :payments="anomalies" :searchData="lastSearchData" @exclude_change="onExcludeChange" />
        <SEPADocumentsPreviewList v-if="showRegionDetailComponent === 'SEPADocumentsPreviewList'" :sepa-files="sepa_files_preview" :searchData="lastSearchData" />
        <template v-if="showRegionDetailComponent === 'CompanyBankRouting'">
          <div v-if="routableCompanies.length > 1" class="mb-3 flex items-center gap-2">
            <label class="text-xs font-medium text-slate-600">{{ $t('service_block.issuing_company') }}</label>
            <select v-model="routingCompanyId" class="input py-1 text-sm max-w-[280px]">
              <option v-for="company in routableCompanies" :key="company.value" :value="company.value">
                {{ company.label }}
              </option>
            </select>
          </div>
          <CompanyBankRouting :key="routingCompanyId" :company_id="routingCompanyId" />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped lang="postcss">

/* Els elements seleccionats poden fer scroll */
.custom-select .vs__selected-options {
  max-height: 50px;
  overflow-y: auto;
}

/*
 * Quan el select està obert, queda per sobre
 * dels elements que hi ha al voltant.
 */
:deep(.custom-select.vs--open) {
  position: relative;
  z-index: 90 !important;
}

/*
 * Dropdown compacte amb scroll.
 */
 :deep(.custom-select .vs__dropdown-menu) {
  position: absolute;
  z-index: 90 !important;
  max-height: 180px;
  overflow-y: auto;
}

:deep(.custom-select-small .vs__dropdown-menu) {
  max-height: 100px !important;
}

:deep(.custom-select-billing .vs__dropdown-menu) {
  max-height: 145px !important;
}

#right_page {
  z-index: 100 !important;
}

</style>
