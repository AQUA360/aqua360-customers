<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import H1Region from '../atoms/H1Region.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import CompanyBankSelect from '~/components/molecules/CompanyBankSelect.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import BudgetEdit from '../organisms/BudgetEdit.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import ChangeStatus from './ChangeStatus.vue';
import PersonSearch from '../organisms/PersonSearch.vue';
import AddContracts from './AddContracts.vue';
import { checkPermission } from '~/middleware/permission';
import { CustomInvoiceTypeChoices } from '~/utils/billing';
import IndividualInvoiceForm from './IndividualInvoiceForm.vue';
import RedoOptions from './RedoOptions.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';
import SelectInvoiceCategory from '~/components/molecules/SelectInvoiceCategory.vue';

const { t } = useI18n();
const { $ConfiglistApiService, $ConfigProjectApiService, $InvoiceApiService, $ReadingApiService, $ContractApiService, $PersonApiService, $ExploitationApiService } = useNuxtApp();
const emit = defineEmits(['change', 'show-subregion', 'close']);
const toast = useToast();

const props = defineProps({
  object_id: Number,
  service: Object,
  entity: String,
  persons: Array,
  company: Object,
  use_default: {
    type: Boolean,
    default: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  is_connection: {
    type: Boolean,
    default: false
  },
  in_invoice: Object,
  reset: {
    type: Boolean,
    default: false
  },
  individual: {
    type: Boolean,
    default: false
  },
  isSubSubRegion: {
    type: Boolean,
    default: false
  },
  bill_termination_requester: {
    type: Boolean,
    default: false
  },
  bill_termination_requester: {
    type: Boolean,
    default: false
  },
  selectedCustom: Object
});

const loading = ref(true);
const loadingReadings = ref(false);

const period_types = ref([
  { code: 0, label: t('common.punctual') },
  { code: 30, label: t('date.monthly') },
  { code: 60, label: t('date.bimonthly') },
  { code: 180, label: t('date.semestral') },
  { code: 90, label: t('date.trimestral') },
  { code: 120, label: t('date.quadrimestral') },
  { code: 360, label: t('date.annual') },
]);

const data = ref(null);
const localPersons = ref((props.persons || []).filter(Boolean));
const originalPersons = ref((props.persons || []).filter(Boolean));

const personIdFrom = (value) => {
  if (value == null || value === '') return null
  if (typeof value === 'object') return value.id || null
  return value
}

const collectRolePersonIds = (source) => {
  if (!source) return []
  return [
    personIdFrom(source.holder ?? source.holder_id),
    personIdFrom(source.tenant ?? source.tenant_id),
    personIdFrom(source.owner ?? source.owner_id),
  ].filter(Boolean)
}

const hydratePersonsByIds = async (ids) => {
  const uniqueIds = [...new Set(ids.filter(Boolean))]
  const loaded = []
  for (const id of uniqueIds) {
    try {
      loaded.push(await $PersonApiService.getFullDetail(id))
    } catch (error) {
      console.error(error)
    }
  }
  return loaded
}

const loadInvoicePersons = async () => {
  const invoice = props.in_invoice
  if (!invoice) return

  console.log('in_invoice', invoice)

  let ids = []
  const invoicePersonId = personIdFrom(invoice.person ?? invoice.person_id)
  if (invoicePersonId) {
    ids = [invoicePersonId]
  } else {
    ids = [
      ...collectRolePersonIds(invoice.contract),
      ...collectRolePersonIds(invoice.contract_request),
    ]
    if (!ids.length) {
      ids = collectRolePersonIds(data.value)
    }
  }

  const loaded = await hydratePersonsByIds(ids)
  originalPersons.value = loaded
  if (selectedHolder.value?.id && !loaded.some(person => person.id === selectedHolder.value.id)) {
    localPersons.value = [...loaded, selectedHolder.value]
  } else {
    localPersons.value = loaded
  }
}
const selectedPaymentType = ref(null);
const selectedBankDebit = ref(null);
const selectedCompanyBankDebit = ref(null);
const electronicInvoiceData = ref({})
const due_date = ref(new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);
const issue_date = ref(new Date(Date.now()).toISOString().split('T')[0]);
const send_at = ref(null);
const period_year = ref(new Date().getFullYear());
const period_month = ref(new Date().getMonth() + 1);
const period_days = ref(90)
const invoices = ref([])
const companyBanks = ref([])
const companies = ref([])
const selectedCompanyId = ref(null)
const selectedCategoryId = ref(null)
const hasInvoiceCategories = ref(true)
const useMultipleCompanies = ref(false)

const onCategoriesLoaded = ({ options }) => {
  hasInvoiceCategories.value = !!options?.length;
};

const localCompany = ref(null)

const resolvedCompany = computed(() => {
  if (props.company) return props.company;
  if (localCompany.value) {
    return {
      ...localCompany.value,
      company_banks: companyBanks.value?.length ? companyBanks.value : localCompany.value.company_banks
    }
  }
  const d = data.value?.results ? data.value.results[0] : data.value;
  const c = d?.company || d?.contract?.company || d?.exploitation?.company || d?.contract?.exploitation?.company ||
            selectedCustom.value?.company || selectedCustom.value?.contract?.company || selectedCustom.value?.exploitation?.company || selectedCustom.value?.contract?.exploitation?.company;
  if (c && typeof c === 'object') {
    return {
      ...c,
      company_banks: companyBanks.value?.length ? companyBanks.value : c.company_banks
    }
  }
  if (companyBanks.value?.length) {
    return {
      name: t('company'),
      company_banks: companyBanks.value
    }
  }
  return null;
});

const entity = ref(props.entity)
const object_id = ref(props.object_id)

const paymentTypeOptionsById = ref([]);

const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
};

const paymentData = ref({})

const is_electronic_invoice = ref(false);
const accounting_office = ref(null)
const managing_body = ref(null)
const processing_unit = ref(null)
const command = ref(null)
const record = ref(null)

const showRegionComponent = ref('');
const regionDetailId = ref('');
const showRegion = ref(false);
const SubRegion = computed(() => showRegion.value);

const finalInvoice = ref(null)
const finalInvoiceId = ref(null)
const { invoiceTypeToken, cancelStatusToken, droppedStatusToken, paidStatusToken, fetchFinalInvoiceTokens, isInvoice, isVoidedInvoice, findFinalInvoice } = useFinalInvoiceTokens();
const redoBudget = ref(false)

const showWarning = ref(false)
const showRedoOptions = ref(false)
const showCustomInvoice = ref(false)
const redoOption = ref(null)
const redoReason = ref('other')
const redoLeakConsum = ref({})

const selectedContract = ref(null)
const selectedPerson = ref(null)
const selectedHolder = ref(null)
const selectedCustom = ref(null)
const readingHasInvoice = ref(false)
const personSearchContext = ref('custom')

const getOriginalPersons = () => {
  if (originalPersons.value.length) return originalPersons.value
  return (props.persons || []).filter(Boolean)
}

const applyRedoMeta = (option = redoOption.value) => {
  if (!option) return option
  const payload = { ...option }
  if (props.in_invoice) {
    payload.title = props.in_invoice.title_final
    payload.invoice_token = props.in_invoice.token
  }
  if (payload.reason === 'holder' && selectedHolder.value?.id) {
    payload.new_holder = selectedHolder.value.id
  } else {
    delete payload.new_holder
  }
  return payload
}

const resetHolderSelection = () => {
  selectedHolder.value = null
  localPersons.value = getOriginalPersons()
}

// helpers for child components
const openSelectContract = () => { showDetail('AddContracts', null) }
const openSelectPerson = () => {
  personSearchContext.value = 'custom'
  showDetail('PersonSearch', null)
}
const openSelectHolder = () => {
  personSearchContext.value = 'holder'
  showDetail('PersonSearch', null)
}
const clearSelected = () => { selectedContract.value = null; selectedPerson.value = null; selectedCustom.value = null }
const onUpdateSelectedCustom = (val) => { selectedCustom.value = val }
const onUpdateReadingHasInvoice = (val) => { readingHasInvoice.value = !!val }
const setRedoOption = (val) => {
  if (val?.reason !== 'holder' && selectedHolder.value) {
    resetHolderSelection()
  }
  redoOption.value = applyRedoMeta(val)
}

const billCutReading = ref(false);

// helpers for child components

const customInvoiceTypes = ref([])
const selectedCustomInvoiceType = ref(null)
const readings = ref([])
const selectedReading = ref(null)
const title = ref('')

const objectPermissions = ref(null);

const selectedExploitation = ref(null)

const clickedInvoice = computed(() => {
  return invoices.value.find(inv => inv.id === regionDetailId.value);
});

const getData = async (load = true) => {
  if (load) loading.value = true;
  try {
    if (props.object_id) {

      const response = await props.service.getDetail(props.object_id);
      data.value = response;
      billCutReading.value = data.value.bill_cut_reading || false;
      if (props.selectedCustom) {
        if (!selectedCustom.value) {
          selectedCustom.value = { ...props.selectedCustom };
        } else {
          selectedCustom.value = { ...props.selectedCustom, ...selectedCustom.value };
        }
        let currentExploitation = localStorage.getItem('exploitation');
        selectedCustom.value.exploitation = currentExploitation;
        if (selectedCustom.value.period_days) period_days.value = selectedCustom.value.period_days;
      }
      if (props.entity === 'connection_request') {
        const responseInvoices = await $InvoiceApiService.getConnectionRequestInvoice(props.object_id);
        invoices.value = responseInvoices.results || [];
      } else if (props.entity === 'contract_request') {
        const responseInvoices = await $InvoiceApiService.getContractInvoice(props.object_id);
        invoices.value = responseInvoices.results || [];
      } else if (props.entity === 'contract') {
        const responseInvoices = await $InvoiceApiService.getInvoicesFromContract(props.object_id);
        invoices.value = responseInvoices.results || [];
      } else if (data.value.invoices && data.value.invoices.length > 0) {
        invoices.value = data.value.invoices.filter(inv => inv.entity === props.entity && inv.object_id === props.object_id);
      } else {
        invoices.value = [];
      }

      let invoice_statuses = { results: [] };
      try {
        invoice_statuses = await $ConfiglistApiService.getAll('billing/invoice-status');
      } catch (e) {
        console.error('Error fetching invoice statuses:', e);
      }

      invoices.value = invoices.value.map(inv => {
        const statusObj = invoice_statuses.results?.find(s => String(s.id) === String(inv.status));
        const statusToken = statusObj?.token || inv.status_token || inv.status?.token || inv.status_final || (typeof inv.status === 'string' ? inv.status : null);
        return {
          ...inv,
          type_token: inv.type_token || inv.type?.token || inv.type_final || (typeof inv.type === 'string' ? inv.type : null),
          status_token: statusToken,
          status_name: inv.status_name || statusObj?.name || null,
          status_color: inv.status_color || statusObj?.color || null,
        };
      });
      
      // removed getCustomInvoiceType call, handled by child when individual flow
      if (props.reset) {
        if (props.in_invoice) {
          invoices.value = invoices.value.filter(invoice => invoice.refactored_token == props.in_invoice.token);
          
          props.in_invoice.readings.forEach(reading => {
            redoLeakConsum.value[reading.id] = reading.calculated_value;
          });
        } else {
          invoices.value = invoices.value.filter(invoice => !invoice.has_invoice);
        }
      }

      // Baixa: el pagament és al contracte (la sol·licitud no en té). Alta: a la sol·licitud.
      const paymentSource = props.entity === 'contract_termination_request'
        ? (data.value.contract?.payment || data.value.payment)
        : data.value.payment;

      if (paymentSource && !selectedPaymentType.value) {
        selectedPaymentType.value = paymentSource.type?.id;
        selectedBankDebit.value = paymentSource.IBAN ? paymentSource.IBAN : null;
        selectedCompanyBankDebit.value = paymentSource.company_iban ? paymentSource.company_iban : null;
        accounting_office.value = paymentSource.accounting_office ? paymentSource.accounting_office : null;
        managing_body.value = paymentSource.managing_body ? paymentSource.managing_body : null;
        processing_unit.value = paymentSource.processing_unit ? paymentSource.processing_unit : null;
        command.value = paymentSource.command ? paymentSource.command : null;
        record.value = paymentSource.record ? paymentSource.record : null;
        selectedExploitation.value = data.value.exploitation?.id || data.value.contract?.exploitation?.id;
        if (accounting_office.value || managing_body.value || processing_unit.value) {
          is_electronic_invoice.value = true;
        }
        electronicInvoiceData.value = {
          accounting_office: paymentSource?.accounting_office,
          managing_body: paymentSource?.managing_body,
          processing_unit: paymentSource?.processing_unit,
          command: paymentSource?.command,
          record: paymentSource?.record
        }

        paymentData.value = {
          type_id: selectedPaymentType.value,
          IBAN: selectedBankDebit.value?.id || null,
          electronic_data: electronicInvoiceData.value.accounting_office ? electronicInvoiceData.value : null,
          due_date: due_date.value,
          issue_date: issue_date.value,
          send_at: send_at.value,
          selected_exploitation: selectedExploitation.value,
          period_days: period_days.value,
          period_year: period_year.value,
          period_month: period_month.value
        }

        if (props.use_default) {
          electronicInvoiceData.value = {
            accounting_office: paymentSource?.accounting_office,
            managing_body: paymentSource?.managing_body,
            processing_unit: paymentSource?.processing_unit,
            command: paymentSource?.command,
            record: paymentSource?.record
          }
          paymentData.value = {
            type_id: paymentSource.type?.id,
            IBAN: paymentSource.IBAN?.id || null,
            company_iban: paymentSource.company_iban?.id || null,
            electronic_data: electronicInvoiceData.value.accounting_office ? electronicInvoiceData.value : null,
            due_date: due_date.value,
            issue_date: issue_date.value,
            send_at: send_at.value,
            selected_exploitation: selectedExploitation.value,
            period_days: period_days.value,
            period_year: period_year.value,
            period_month: period_month.value
          }
        }

        showWarning.value = false

      }

      finalInvoice.value = findFinalInvoice(invoices.value)
    }

    if (props.in_invoice) {
      await loadInvoicePersons()
    }

    await loadCompanyBanks();
    await loadCompanies();

  } catch (error) {
    console.log(error);
  } finally {
    loading.value = false;
  }
};

const loadCompanies = async () => {
  const explId = selectedExploitation.value || data.value?.exploitation?.id;
  if (!explId) {
    companies.value = [];
    return;
  }
  try {
    const explResp = await $ExploitationApiService.getDetail(explId);
    companies.value = explResp?.companies || [];
  } catch (err) {
    console.error(err);
    companies.value = [];
  }
};

const showCompanySelector = computed(() => useMultipleCompanies.value && companies.value?.length > 1);

const loadCompanyBanks = async () => {
  const d = data.value?.results ? data.value.results[0] : data.value;
  const c = d?.company || d?.contract?.company || d?.exploitation?.company || d?.contract?.exploitation?.company ||
            selectedCustom.value?.company || selectedCustom.value?.contract?.company || selectedCustom.value?.exploitation?.company || selectedCustom.value?.contract?.exploitation?.company;
  let compId = selectedCompanyId.value || props.company?.id || (c && typeof c === 'object' ? c.id : c);

  if (!compId && selectedExploitation.value) {
    try {
      const explResp = await $ExploitationApiService.getDetail(selectedExploitation.value);
      const ec = explResp?.company;
      compId = ec && typeof ec === 'object' ? ec.id : ec;
    } catch(err) {
      console.error(err);
    }
  }

  if (compId) {
    try {
      if (!props.company) {
        try {
          const compResp = await $ExploitationApiService.getCompany(compId);
          if (compResp) {
            localCompany.value = compResp;
          }
        } catch(err) {
          console.error(err);
        }
      }
      const banksResp = await $ExploitationApiService.getCompanyBanks(compId);
      if (banksResp?.results) {
        companyBanks.value = banksResp.results;
      } else if (Array.isArray(banksResp)) {
        companyBanks.value = banksResp;
      }
    } catch(e) {
      console.error(e);
    }
  } else if (props.company?.company_banks) {
    companyBanks.value = props.company.company_banks;
  }
  if (companyBanks.value?.length === 1 && paymentTypeOptionsById?.value[selectedPaymentType?.value]?.token == 'BANK_TRANSFER' && !selectedCompanyBankDebit.value) {
    selectedCompanyBankDebit.value = companyBanks.value[0];
  }
};

watch([selectedExploitation, () => selectedCustom.value?.id, () => selectedCustom.value?.company, selectedCompanyId], () => {
  loadCompanyBanks();
  loadCompanies();
});

const getCustomInvoiceType = () => {
  customInvoiceTypes.value = []
  customInvoiceTypes.value.push({
    value: 'custom',
    label: t("common.custom")
  })
  if (selectedCustom.value?.entity == 'contract') {
    customInvoiceTypes.value.push({
      value: 'reading',
      label: t("reading")
    })
  }
}

const selectExploitation = (event) => {
  selectedExploitation.value = event;
}

const getReadings = async () => {
  loadingReadings.value = true;
  try {
    const response = await $ReadingApiService.getAll(
      '', [], 1, 'id', false,
      selectedCustom.value?.entity == 'contract' ? [selectedCustom.value.id] : [],
      null, null, false
    );

    const groupedReadings = response.results.reduce((acc, reading) => {
      const date = reading.reading_date;
      if (!acc[date]) {
        acc[date] = { has_invoice: reading.invoice != null, ids: [reading.id] };
      } else {
        acc[date].ids.push(reading.id);
      }
      return acc;
    }, {});
    readings.value = Object.entries(groupedReadings).map(([date, total]) => ({
      value: date,
      label: `${date}`,
      has_invoice: total.has_invoice,
      ids: total.ids
    }));

  } catch (error) {
    console.log(error);
  } finally {
    loadingReadings.value = false;
  }
}


const onSelectPaymentMethod = () => {
  selectedBankDebit.value = null;
  selectedCompanyBankDebit.value = null;
  if (paymentTypeOptionsById.value[selectedPaymentType.value]?.token == 'BANK_TRANSFER') {
    if (companyBanks.value?.length === 1) {
      selectedCompanyBankDebit.value = companyBanks.value[0];
    } else if (companyBanks.value?.length > 1) {
      openCompanyBankSelect();
    }
  }
};

const onPersonBankSelected = (bank) => {
  selectedBankDebit.value = bank;
  closeAllRegions();
};

const onCompanyBankSelected = (bank) => {
  selectedCompanyBankDebit.value = bank;
  closeAllRegions();
};


const openPersonBankSelect = () => {
  closeAllRegions();
  showRegionComponent.value = paymentTypeOptionsById.value[selectedPaymentType.value].token == 'DIRECT_DEBIT' ? 'PersonBankSelect' : 'CompanyBankSelect';
  toggleRegion(true);
  emit('show-subregion', true);
};

const openCompanyBankSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'CompanyBankSelect';
  toggleRegion(true);
  emit('show-subregion', true);
};

const ensureRedoHolderSelected = () => {
  if (redoOption.value?.reason == 'holder' && !selectedHolder.value?.id) {
    toast.warning(t("billing_block.select_new_holder"))
    return false
  }
  return true
}

const generateInvoice = async () => {
  if (!confirm(t("confirmation_text_block.confirm_budget_invoice"))) return
  if (!ensureRedoHolderSelected()) return

  let budget = invoices.value.find(invoice => !isInvoice(invoice))
  
  loading.value = true;
  try {
    const invoice_generation = {
      entity: budget ? 'invoice' : props.entity,
      object_id: budget ? budget.id : data.value?.id,
      is_budget: false,
      bill_cut_reading: props.entity === 'contract_request' ? billCutReading.value : false,
      payment_data: paymentData.value,
      redo_option: applyRedoMeta(),
      selected_custom: selectedCustom.value,
      bill_termination_requester: props.bill_termination_requester
    };

    const response = await $InvoiceApiService.generateInvoiceBudget(invoice_generation);
    
    if (response) {
      toast.success(t('informative_block.info_invoice_correct_gen'));
      await refresh(false, response.invoice);
      if (budget) {
        entity.value = 'invoice'
        object_id.value = budget.id
      } else {
        entity.value = props.entity
        object_id.value = props.object_id
      }
      showDetail('InvoiceEdit', response.invoice?.id);
    }
  } catch (error) {
    console.error(error);
    toast.error(error.message || t('common.error_save'));
  } finally {
    loading.value = false;
  }
}

const regenBudget = async () => {
  entity.value = props.entity
  object_id.value = props.object_id
  if (props.in_invoice) {
    if (redoOption.value?.reason == 'leak' && (!redoOption.value?.leak_consum || Object.keys(redoOption.value.leak_consum).length === 0)) {
      toast.warning(t("billing_block.select_real_consumption"))
      return
    }
    if (!ensureRedoHolderSelected()) return
    redoOption.value = applyRedoMeta()
  }
  if (selectedPaymentType.value == null) {
    toast.warning(t("common.select_payment_method"))
    return
  }
  showRegionComponent.value = null;
  regionDetailId.value = null;
  redoBudget.value = true
  let budget = invoices.value.find(invoice => !isInvoice(invoice))
  if (budget) {
    showDetail('BudgetEdit', budget.id)
  } else {
    generateBudget();
  }
}

const showDetail = (component, id) => {
  showRegionComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true);
  emit('show-subregion', true);
}

// Estats que s'ofereixen al panell d'anul·lar factura. El primer és el preseleccionat.
const cancelAllowedTokens = ref([]);

const toNumber = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(String(value).replace(',', '.'));
  return Number.isNaN(parsed) ? null : parsed;
};

/**
 * Anul·lar (-7) només té sentit mentre la factura no hagi cobrat res; si en té,
 * l'únic camí correcte és abonar-la (-6). És el mateix criteri que el backend
 * aplica a /billing/invoice/{id}/return/ (pagaments amb moviments), aproximat
 * aquí amb el que el detall de la factura ja ens dona.
 */
const openCancelInvoice = async (invoice) => {
  let hasCollected = String(invoice.status_token) === String(paidStatusToken.value);
  try {
    const detail = await $InvoiceApiService.getDetail(invoice.id);
    const left = toNumber(detail?.left_to_pay);
    const total = toNumber(detail?.total_final);
    if (left !== null && total !== null && total > 0 && left < total) hasCollected = true;
  } catch (error) {
    console.error('Error fetching invoice detail:', error);
  }

  cancelAllowedTokens.value = hasCollected
    ? [cancelStatusToken.value]
    : [droppedStatusToken.value, cancelStatusToken.value];

  showDetail('ChangeStatus', invoice.id);
}

const onChangeElectronicInvoice = () => {
  if (accounting_office.value && managing_body.value && processing_unit.value) {
    electronicInvoiceData.value = {
      accounting_office: accounting_office.value,
      managing_body: managing_body.value,
      processing_unit: processing_unit.value,
      command: command.value,
      record: record.value
    }
  }
}


onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  await fetchFinalInvoiceTokens();
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
  await getData()
  if (props.in_invoice) {
    showRedoOptions.value = true
  }
  if (props.individual) {
    showCustomInvoice.value = true
  }
});

const closeAllRegions = () => {
  showRegionComponent.value = null;
  regionDetailId.value = null;
  toggleRegion(false);
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    showRegionComponent.value = null;
    regionDetailId.value = null;
    emit('show-subregion', false);
    entity.value = props.entity
    object_id.value = props.object_id
  }
}

const refresh = async (close = false, invoice = null) => {
  if (close) {
    toggleRegion(false)
  }
  await getData(false)
  if (invoice) {
    const isFinal = (invoice?.type?.token == invoiceTypeToken.value || invoice?.type_token == invoiceTypeToken.value);
    const existingIndex = invoices.value.findIndex(i => i.id === invoice.id);
    
    if (existingIndex !== -1) {
      invoices.value[existingIndex] = invoice;
    } else {
      invoices.value.push(invoice);
    }

    if (isFinal) {
      finalInvoice.value = invoice;
    }

    if (!close && isFinal && regionDetailId.value && regionDetailId.value !== invoice.id) {
      entity.value = 'invoice';
      object_id.value = invoice.id;
      showDetail('InvoiceEdit', invoice.id);
    }
  }
  redoBudget.value = false
  emit('change', close)
}

const deleteBudget = async (id) => {
  if (!confirm(t("confirmation_text_block.confirm_delete_budget"))) return
  try {
    await $InvoiceApiService.deleteInvoiceBudget(id)
    toast.success(t('common.deleted_correctly'))
    await refresh()
  } catch (error) {
    console.error(error)
    toast.error(error.message || t('common.error_delete'))
  }
}

const onContractSelected = async (item) => {
  if (selectedContract.value?.id == item.id) {
    selectedContract.value = null;
    selectedCustom.value = null;
    localPersons.value = props.persons;
  } else {
    selectedContract.value = item;
    selectedCustom.value = {
      id: item.id,
      title: '',
      label: item.holder_token ? `${item.token} - ${item.holder_name} (${item.holder_token})` : `${item.token} - ${item.holder_name}`,
      general_invoice: false,
      period_days: item?.billing_period_days || 0,
      entity: 'contract',
    }
    await getCustomInvoiceType();
  }
  if (selectedContract.value) {
    getContractPersons();
  }
  closeAllRegions();
}

const getContractPersons = async () => {
  try {
    let response = await $ContractApiService.getDetail(selectedContract.value.id);
    if (response.holder) {
      const hydratedHolder = await $PersonApiService.getFullDetail(response.holder.id);
      localPersons.value = [hydratedHolder];
    }
  } catch (error) {
    console.error(error);
  }
}

const updateTitle = () => {
  selectedCustom.value.title = title.value;
}

const onHolderPersonSaved = async (item) => {
  selectedHolder.value = item
  try {
    const loadedPerson = await $PersonApiService.getFullDetail(item.id)
    selectedHolder.value = loadedPerson
  } catch (error) {
    console.error(error)
  }
  const originals = getOriginalPersons()
  const newPerson = selectedHolder.value
  if (newPerson?.id && originals.some(person => person.id === newPerson.id)) {
    localPersons.value = originals
  } else if (newPerson) {
    localPersons.value = [...originals, newPerson]
  } else {
    localPersons.value = originals
  }
  redoOption.value = applyRedoMeta()
  closeAllRegions()
}

const onPersonSaved = async (item) => {
  if (personSearchContext.value === 'holder') {
    await onHolderPersonSaved(item)
    return
  }
  selectedPerson.value = item;
  selectedCustom.value = {
    id: item.id,
    title: '',
    label: `${item.full_name} (${item.token})`,
    general_invoice: false,
    period_days: 0,
    entity: 'person',
  }
  try {
    const loadedPerson = await $PersonApiService.getFullDetail(item.id);
    localPersons.value = [loadedPerson];
  } catch (error) {
    console.error(error);
  }
  getCustomInvoiceType();
  closeAllRegions();
}

const updateSelect = async (event, field) => {
  switch (field) {
    case 'custom_invoice_type':
      selectedCustomInvoiceType.value = event;
      selectedCustom.value.type = event.value;
      selectedReading.value = null;
      if (event.value == 'reading') {
        await getReadings();
      }
      break;
    case 'reading':
      selectedReading.value = event;
      selectedCustom.value.readings = event.ids;
      break;
  }

}

const disableRedo = async (invoice) => {
  redoBudget.value = false
  await getData(false)
  if (invoice) {
    const oldId = regionDetailId.value;
    const existingIndex = invoices.value.findIndex(i => i.id === oldId || i.id === invoice.id);
    if (existingIndex !== -1) {
      invoices.value[existingIndex] = invoice;
    } else {
      invoices.value.push(invoice);
    }
    regionDetailId.value = invoice.id;
  }
}

const generateBudget = async () => {
  if (selectedPaymentType.value == null) {
    toast.warning(t("common.select_payment_method"))
    return
  }
  if (!ensureRedoHolderSelected()) return

  loading.value = true;
  try {
    const invoice_generation = {
      entity: props.entity,
      object_id: data.value?.id,
      is_budget: true,
      bill_cut_reading: props.entity === 'contract_request' ? billCutReading.value : false, 
      payment_data: paymentData.value,
      redo_option: applyRedoMeta(),
      selected_custom: selectedCustom.value,
      bill_termination_requester: props.bill_termination_requester
    };

    const response = await $InvoiceApiService.generateInvoiceBudget(invoice_generation);
    
    if (props.entity === 'contract_request' && billCutReading.value && data.value.contract_termination_requests?.length > 0) {
      for (const term of data.value.contract_termination_requests) {
        const invoice_generation_cons = {
          entity: 'contract_termination_request',
          object_id: term.id,
          is_budget: true,
          payment_data: paymentData.value,
          company_id: selectedCompanyId.value,
          category_id: selectedCategoryId.value
        };
        await $InvoiceApiService.generateInvoiceBudget(invoice_generation_cons);
      }
    }

    if (response) {
      toast.success(t('informative_block.info_budget_correct_gen'));
      await refresh(false, response.invoice);
      showDetail('BudgetEdit', response.invoice?.id);
    }
  } catch (error) {
    console.error(error);
    toast.error(error.message || t('common.error_save'));
  } finally {
    loading.value = false;
  }
}

watch([selectedPaymentType, selectedBankDebit, selectedCompanyBankDebit, electronicInvoiceData, due_date, issue_date, send_at, selectedExploitation, period_days, period_year, period_month, paymentTypeOptionsById, selectedCompanyId, selectedCategoryId], () => {
  paymentData.value = {
    type_id: selectedPaymentType.value,
    IBAN: paymentTypeOptionsById?.value[selectedPaymentType?.value]?.token == 'DIRECT_DEBIT' && selectedBankDebit.value ? selectedBankDebit.value?.id : null,
    company_iban: (paymentTypeOptionsById?.value[selectedPaymentType?.value]?.token == 'DIRECT_DEBIT' || paymentTypeOptionsById?.value[selectedPaymentType?.value]?.token == 'BANK_TRANSFER') && selectedCompanyBankDebit.value ? selectedCompanyBankDebit.value?.id : null,
    electronic_data: electronicInvoiceData.value,
    due_date: due_date.value,
    issue_date: issue_date.value,
    send_at: send_at.value,
    selected_exploitation: selectedExploitation.value,
    period_days: period_days.value,
    period_year: period_year.value,
    period_month: period_month.value,
    company_id: selectedCompanyId.value,
    category_id: selectedCategoryId.value
  }
  showWarning.value = true
}, { deep: true, immediate: true })

watch(selectedPaymentType, (newVal) => {
  if (paymentTypeOptionsById?.value[newVal]?.token == 'BANK_TRANSFER') {
    if (companyBanks.value?.length === 1 && !selectedCompanyBankDebit.value) {
      selectedCompanyBankDebit.value = companyBanks.value[0];
    }
  }
})

watch(selectedCustom, () => {
  if (selectedCustom.value?.type == 'custom') {
    period_days.value = 0;
  }
}, { deep: true })

watch([issue_date, period_days], () => {
  if (period_days.value == 0 || issue_date.value && (new Date(issue_date.value).getFullYear() != period_year.value || new Date(issue_date.value).getMonth() + 1 != period_month.value)) {
    period_year.value = new Date(issue_date.value).getFullYear();
    period_month.value = new Date(issue_date.value).getMonth() + 1;
  }
}, { deep: true })

watch(is_electronic_invoice, (newVal) => {
  if (!newVal) {
    accounting_office.value = null;
    managing_body.value = null;
    processing_unit.value = null;
    command.value = null;
    record.value = null;
    electronicInvoiceData.value = null;
  }
}, { deep: true });

watch(redoReason, () => {
  if (props.in_invoice) {
    props.in_invoice.readings.forEach(reading => {
      redoLeakConsum.value[reading.id] = reading.calculated_value;
    });
  }
});
watch(() => props.object_id, () => {
  getData();
});

</script>

<template>
  <div v-if="!loading" class="region__content h-full">
    <div class="pr-2 relative pb-24 h-full overflow-y-auto transition-all duration-500 ease"
      :class="{ 'mr-[48vw]': SubRegion }">

      <div class="w-full mb-6">
        <H1Region>{{ $t('billing_block.budget_invoice_generate') }}</H1Region>
      </div>

      <RedoOptions v-if="showRedoOptions" :in_invoice="in_invoice" :selected-holder="selectedHolder"
      @update:redoOption="setRedoOption" @close-region="emit('change', true)"
      @open-person-search="openSelectHolder" />

      <IndividualInvoiceForm v-if="props.individual" :object_id="props.object_id" :service="props.service"
        :persons="localPersons" :selectedCustom="selectedCustom" :companies="companies"
        @update:selectedCustom="onUpdateSelectedCustom"
        @select-contract="openSelectContract" @select-person="openSelectPerson" @clear-selected="clearSelected"
        @select-exploitation="selectExploitation"
        @update:readingHasInvoice="onUpdateReadingHasInvoice" />

      <fieldset v-if="!use_default" class="mb-4 mx-5 border border-gray-300 rounded-lg p-6">
        <legend class="font-medium text-gray-700 px-3 py-1">{{ $t('common.payment_method') }}</legend>
        <div v-if="showCompanySelector" class="max-w-xl mb-3">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('company') }}</label>
          <select v-model.number="selectedCompanyId" class="input w-full">
            <option :value="null">-- {{ $t('common.select') }} --</option>
            <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>

        <div v-if="!props.individual && hasInvoiceCategories" class="max-w-xl mb-3">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.category') }}</label>
          <SelectInvoiceCategory v-model="selectedCategoryId" :model-as-number="true"
            select-class="w-full text-base border border-gray-300 rounded p-2" @loaded="onCategoriesLoaded" />
        </div>
        <div class="max-w-xl">
          <SelectPaymentType v-model="selectedPaymentType" :model-as-number="true"
            select-class="w-full text-base border border-gray-300 rounded p-2"
            @change="onSelectPaymentMethod" @loaded="onPaymentTypesLoaded" />
        </div>

        <div class="select_bank mt-3 max-w-xl"
          v-if="paymentTypeOptionsById[selectedPaymentType] && paymentTypeOptionsById[selectedPaymentType].token == 'DIRECT_DEBIT'">
          <div v-if="selectedBankDebit || selectedCompanyBankDebit" class="bg-green-100 p-4 rounded relative group">
            <div>
              <BankDetail :item="selectedBankDebit ? selectedBankDebit : selectedCompanyBankDebit" />
            </div>
            <button @click="openPersonBankSelect"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>

          <ButtonSeleccio v-else @click="openPersonBankSelect()" class="py-3">
            <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
            {{ $t('common.select') }} {{ $t('common.iban') }}
          </ButtonSeleccio>

        </div>

        <div class="select_bank mt-3 max-w-xl"
          v-if="paymentTypeOptionsById[selectedPaymentType] && paymentTypeOptionsById[selectedPaymentType].token == 'BANK_TRANSFER' && companyBanks.length > 1">
          <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{{ $t('common.bank_data') }} ({{ $t('company') }})</label>
          <div v-if="selectedCompanyBankDebit" class="bg-sky-50 border border-sky-100 p-4 rounded relative group">
            <div>
              <BankDetail :item="selectedCompanyBankDebit" />
            </div>
            <button @click="openCompanyBankSelect"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>

          <ButtonSeleccio v-else @click="openCompanyBankSelect()" class="py-3">
            <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
            {{ $t('common.select') }} {{ $t('common.iban') }}
          </ButtonSeleccio>
        </div>

        <div>
          <div class="flex items-center mt-9 ml-2 text-slate-500">
            <input v-model="is_electronic_invoice" type="checkbox" id="is_electronic_invoice"
              name="is_electronic_invoice" class="checkbox" />
            <label for="is_electronic_invoice" class="ml-2"> {{ t('common.electronic_invoice') }}</label>
          </div>

          <details class="select_bank bg-green-50 mt-3 max-w-xl p-1 border rounded" v-if="is_electronic_invoice">
            <summary class="text-slate-500">
              {{ $t('common.electronic_invoice_data') }}
            </summary>
            <div class="bg-green-50  rounded-lg p-4 relative group my-2">
              <div class="grid grid-cols-2 gap-3">
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.accounting_office') }}
                  </label>
                  <input type="text" v-model="accounting_office"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi oficina" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.managing_body') }}
                  </label>
                  <input type="text" v-model="managing_body"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi òrgan" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.processing_unit') }}
                  </label>
                  <input type="text" v-model="processing_unit"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi unitat" />
                </div>
                <!-- <div class="space-y-1">
                <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                  {{ $t('billing_block.command') }}
                </label>
                <input type="text" v-model="command" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                  @change="onChangeElectronicInvoice" placeholder="Codi comanda" />
              </div>
              <div class="space-y-1 col-span-2">
                <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                  {{ $t('billing_block.record') }}
                </label>
                <input type="text" v-model="record" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                  @change="onChangeElectronicInvoice" placeholder="Codi expedient" />
              </div> -->
              </div>
            </div>
          </details>
        </div>


      </fieldset>
      <fieldset v-else class="mb-4 border border-sky-500 rounded-lg p-6">
        <FieldDetail :label="$t('common.payment_method')" :value="data.payment?.type?.name"></FieldDetail>
        <BankDetail v-if="data?.payment?.IBAN || data?.payment?.company_iban" :item="data?.payment?.IBAN
          ? data.payment.IBAN : data?.payment?.company_iban
            ? data.payment.company_iban : null" />
        <div v-if="electronicInvoiceData && electronicInvoiceData.accounting_office"
          class="bg-green-50 border border-slate-200 rounded-lg p-4 relative group mb-2">
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1">
              <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                {{ $t('billing_block.accounting_office') }}
              </label>
              <input type="text" v-model="accounting_office"
                class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" @change="onChangeElectronicInvoice"
                placeholder="Codi oficina" />
            </div>
            <div class="space-y-1">
              <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                {{ $t('billing_block.managing_body') }}
              </label>
              <input type="text" v-model="managing_body"
                class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" @change="onChangeElectronicInvoice"
                placeholder="Codi òrgan" />
            </div>
            <div class="space-y-1">
              <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                {{ $t('billing_block.processing_unit') }}
              </label>
              <input type="text" v-model="processing_unit"
                class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" @change="onChangeElectronicInvoice"
                placeholder="Codi unitat" />
            </div>
            <!-- <div class="space-y-1">
              <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                {{ $t('billing_block.command') }}
              </label>
              <input type="text" v-model="command" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                @change="onChangeElectronicInvoice" placeholder="Codi comanda" />
            </div>
            <div class="space-y-1 col-span-2">
              <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                {{ $t('billing_block.record') }}
              </label>
              <input type="text" v-model="record" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                @change="onChangeElectronicInvoice" placeholder="Codi expedient" />
            </div> -->
          </div>
        </div>
      </fieldset>
      
      <fieldset class="mb-4 mx-5 border border-gray-300 rounded-lg p-6">
        <div class="flex items-center grid grid-cols-3 gap-x-3">
          <div>
            <AtomsInputDate v-model="issue_date" :label="t('billing_block.sel_issue_date')" />
          </div>
          <div>
            <AtomsInputDate v-model="due_date" :label="t('common.due_date')" />
          </div>
          <div v-if="(paymentTypeOptionsById[selectedPaymentType] && paymentTypeOptionsById[selectedPaymentType].token == 'DIRECT_DEBIT') || 
           ( use_default && (data?.payment?.IBAN != null || data?.payment?.company_iban != null))">
            <AtomsInputDate v-model="send_at" :label="t('common.send_date')" />
          </div>
          <div v-else></div>
          <div class="input-group">
            <label for="period_days_select" class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.billing_period') }} </label>
            <select id="period_days_select" v-model.number="period_days" class="input" :disabled="selectedCustom?.type == 'custom'">
              <option v-for="period_type in period_types" :value="period_type.code" :key="period_type.code">
                {{ period_type.label }}
              </option>
            </select>
          </div>
          <div v-if="period_days != 0">
            <label for="period_days_select" class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.period_year') }}</label>
            <input type="number" v-model="period_year" class="input" :placeholder="t('billing_block.period_year')" />
          </div>
          <div v-if="period_days != 0">
            <label for="period_days_select" class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.period_month') }}</label>
            <input type="number" v-model="period_month" class="input" :placeholder="t('billing_block.period_month')" />
          </div>
        </div>
      </fieldset>


      <div v-if="showWarning && invoices && invoices.length > 0 && !finalInvoice"
        class="flex justify-between items-center w-[90%] mb-5 h-auto p-2 mx-auto bg-orange-100 rounded-md">
        <span class="text-orange-600 px-5">
          {{ $t("warning_block.budget_warning") }}
        </span>
        <button @click="showWarning = false"
          class="text-orange-600 hover:text-orange-700 transition-all duration-200 ease-in-out">
          <Icon name="fa6-solid:xmark" class="text-orange-600 m-auto" />
        </button>

      </div>

      <!-- <fieldset id="invoice_budget__box" v-if="data && typeof data === 'object'" -->
      <fieldset id="invoice_budget__box" class="w-[95%] mb-4 border border-gray-300 rounded-lg p-4 mx-5">
        <legend v-if="invoices &&invoices.length === 0" class="font-medium text-gray-700 px-3">
          {{ $t('billing_block.budget_generate') }}</legend>
        <legend v-else-if="invoices &&invoices.length > 0 && !finalInvoice" class="font-medium text-gray-700 px-3">{{
          $t('billing_block.invoice_generate') }}</legend>
        <legend v-else class="font-medium text-gray-700 px-3">{{ $t('billing_block.budget_invoice') }}</legend>
        <div class="px-3" v-if="invoices">
          <div v-for="invoice in invoices" :key="invoice.id"
            class="grid grid-cols-[1fr,1fr,auto,auto,20px,20px] items-center gap-x-4 py-4 border-b border-gray-200 last:border-b-0 animate-fadeIn"
            :class="{ 'opacity-60': isVoidedInvoice(invoice) }">
            <span class="text-slate-700 font-semibold text-sm md:text-base flex items-center">
              {{ isInvoice(invoice) ? t('invoice') : t('common.budget_detail') }}:
              <span class="text-gray-600 ml-1 font-normal">{{ invoice.serie_final }}</span>
            </span>
            <span class="text-gray-600 text-sm md:text-base truncate" :title="invoice.title_final">
              {{ invoice.title_final }}
            </span>
            <span class="text-gray-800 font-bold text-sm md:text-base">
              {{ formatMoneyWithCurrency(invoice.total_final) }}
            </span>
            <span>
              <AtomsColorBadge v-if="invoice.status_name" :value="invoice.status_name" :color="invoice.status_color" />
            </span>
            <abbr
              :title="isInvoice(invoice) ? `${t('common.check')} ${t('invoice')}` : `${t('common.check')} ${t('common.budget_detail')}`"
              class="flex items-center my-auto justify-center w-9 h-9">
              <!-- <button @click="showDetail(finalInvoice ? 'InvoiceEdit' : 'BudgetEdit', invoice.id)" -->
              <button @click="showDetail(isInvoice(invoice) && !isVoidedInvoice(invoice)
                ? 'BudgetEdit' : finalInvoice ? 'InvoiceEdit' : 'BudgetEdit', invoice.id)"
                class="rounded-full w-6 h-6 border border-orange-500 bg-white m-auto p-auto hover:bg-orange-100 flex items-center">
                <Icon class="text-orange-500 m-auto" :name="!finalInvoice && !isInvoice(invoice) && !isVoidedInvoice(invoice) ?
                  'fa6-solid:pencil' : finalInvoice ? 'fa6-solid:eye' : 'fa6-solid:pencil'" />
              </button>
            </abbr>
            <abbr
              v-if="!isInvoice(invoice) && !isVoidedInvoice(invoice)"
              :title="t('common.delete')" class="flex items-center my-auto justify-center w-9 h-9">
              <button @click="deleteBudget(invoice.id)"
                class="rounded-full w-6 h-6 border border-red-500 bg-white m-auto p-auto hover:bg-red-100 flex items-center">
                <Icon name="fa6-solid:trash" class="text-red-500 m-auto" />
              </button>
            </abbr>
            <abbr
              v-if="isInvoice(invoice) && !isVoidedInvoice(invoice)"
              :title="t('billing_block.cancel_invoice')" class="flex items-center my-auto justify-center w-9 h-9">
              <!-- <button @click="showDetail(finalInvoice ? 'InvoiceEdit' : 'BudgetEdit', invoice.id)" -->
              <button @click="openCancelInvoice(invoice)"
                class="rounded-full w-6 h-6 border border-orange-500 bg-white m-auto p-auto hover:bg-orange-100 flex items-center">
                <Icon name="fa6-solid:trash" class="text-orange-500 m-auto" />
              </button>
            </abbr>
          </div>

        </div>

        <div>
          <ButtonOutline v-if="invoices && invoices.length === 0"
            :disabled="(props.individual && !selectedCustom?.type)" class="my-2"
            @click="generateBudget">
            {{ $t('billing_block.budget_generate') }}
          </ButtonOutline>
          <div v-if="invoices && invoices.length > 0 && !finalInvoice" class="gap-5">
            <ButtonOutline class="my-2 flex items-center gap-3" @click="regenBudget">
              <!-- <Icon name="fa6-solid:arrows-rotate" class="m-auto text-blue-600" /> -->
              {{ $t('billing_block.budget_generate_again') }}
            </ButtonOutline>
            <ButtonOutline class="my-2" @click="generateInvoice">
              {{ $t('billing_block.invoice_generate') }}
            </ButtonOutline>
            <!-- <abbr v-if="data.invoices.length > 0 && !finalInvoice" :title="t('Torna a generar el pressupost')">
              <button
                class="h-9 w-9 rounded bg-white border border-blue-500 flex items-center justify-center hover:bg-slate-50"
                @click="regenBudget">
                <Icon name="fa6-solid:arrows-rotate" class="m-auto text-blue-600" />
              </button>
            </abbr> -->
          </div>
        </div>
      </fieldset>
    </div>

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden shadow-2xl fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div v-if="showRegion" id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
          :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="localPersons"
          @selected-item="onPersonBankSelected" />
        <CompanyBankSelect v-if="showRegionComponent === 'CompanyBankSelect'"
          :title="`${$t('common.select')} ${$t('common.iban')}`" :company="resolvedCompany"
          @selected-item="onCompanyBankSelected" />
        <BudgetEdit v-if="showRegionComponent === 'BudgetEdit' || showRegionComponent === 'InvoiceEdit'"
          :key="showRegionComponent"
          @disable-redo="disableRedo" @changed="refresh" :id="data?.id ? data.id : null" :object_id="object_id"
          :invoice_id="regionDetailId" :redo_budget="redoBudget" :payment_data="paymentData"
          :is_budget="showRegionComponent === 'BudgetEdit'" :is_connection="is_connection" :service="props.service"
          :entity="entity" :redo_option="redoOption" :selected_custom="selectedCustom" :isSubRegion="true" />
        <ChangeStatus v-if="showRegionComponent === 'ChangeStatus'" entity="invoice" parent_entity="invoice"
          :id="regionDetailId" :status="clickedInvoice?.status_id || clickedInvoice?.status?.id"
          @changed="refresh(true)" :module="'billing'" :has_observation="false"
          :allowedTokens="cancelAllowedTokens"
          :reasonToken="[cancelStatusToken, droppedStatusToken]" reasonLabel="billing_block.reason_cancellation"
          reasonPlaceholder="billing_block.write_reason_cancellation" :reasonRequired="true" />
        <AddContracts v-if="showRegionComponent == 'AddContracts'" :multiple="false"
          :selected_items="[selectedContract]" @item-clicked="onContractSelected" />
        <PersonSearch v-if="showRegionComponent == 'PersonSearch'" :key="personSearchContext"
          :personLabel="personSearchContext === 'holder' ? 'contract_block.new_holder' : 'common.requester'"
          :allowCreate="personSearchContext === 'holder'" @saved="onPersonSaved" />
      </div>
    </div>
  </div>
  <div v-else>
    <p>{{ $t('common.loading') }}...</p>
  </div>
</template>

<style scoped>
/* Custom styles */
body {
  background-color: #f7fafc;
}
</style>
