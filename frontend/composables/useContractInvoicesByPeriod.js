import { ref, reactive } from 'vue';

// Contract invoices grouped by the year of the billed period (or the issue date when
// the invoice has no period). Only the selected year is loaded.
export const NO_PERIOD_YEAR = 'none';

// 'periods': year tabs and billed cycles; 'list': every invoice, paginated (classic view).
export const VIEW_PERIODS = 'periods';
export const VIEW_LIST = 'list';
const VIEW_STORAGE_KEY = 'contract_invoices_view';
const LIST_PAGE_SIZE = 50;

const readStoredView = () => {
  try {
    return localStorage.getItem(VIEW_STORAGE_KEY) === VIEW_LIST ? VIEW_LIST : VIEW_PERIODS;
  } catch {
    return VIEW_PERIODS;
  }
};

export function useContractInvoicesByPeriod(getContractId) {
  const { $InvoiceApiService } = useNuxtApp();

  const years = ref([]); // [{ year, count }], newest first, NO_PERIOD_YEAR last
  const activeYear = ref(null);
  const invoices = ref([]);
  const loading = ref(false);
  const error = ref(false);
  // 'invoice' → is_invoice=true; 'budget' → is_invoice=false
  const listMode = ref('invoice');
  const viewMode = ref(readStoredView());
  const listInvoices = ref([]);
  const listPagination = ref({ page: 1, perPage: LIST_PAGE_SIZE, total: 0, totalPages: 0, isFiltered: true });

  // Answers of older requests are dropped (fast year switching, contract change).
  let requestId = 0;

  const isInvoice = () => listMode.value === 'invoice';

  const loadYear = async (year) => {
    const current = ++requestId;
    activeYear.value = year;
    invoices.value = [];
    error.value = false;
    if (year === null) {
      loading.value = false;
      return;
    }
    loading.value = true;
    try {
      const results = await $InvoiceApiService.getContractInvoicesByPeriodYear(
        getContractId(),
        year,
        isInvoice(),
      );
      if (current === requestId) invoices.value = results;
    } catch (err) {
      console.error(err);
      if (current === requestId) error.value = true;
    } finally {
      if (current === requestId) loading.value = false;
    }
  };

  const loadListPage = async (page = 1) => {
    const current = ++requestId;
    loading.value = true;
    error.value = false;
    try {
      const response = await $InvoiceApiService.getContractInvoicesPage(getContractId(), page, isInvoice());
      if (current !== requestId) return;
      listInvoices.value = response.results;
      const total = response.count || 0;
      listPagination.value = {
        ...listPagination.value,
        page,
        total,
        totalPages: Math.ceil(total / LIST_PAGE_SIZE),
      };
    } catch (err) {
      console.error(err);
      if (current === requestId) error.value = true;
    } finally {
      if (current === requestId) loading.value = false;
    }
  };

  // Reloads the years and keeps the selected one if it still has invoices.
  const loadPeriods = async () => {
    const current = ++requestId;
    loading.value = true;
    error.value = false;
    try {
      const result = await $InvoiceApiService.getContractInvoicePeriodYears(
        getContractId(),
        isInvoice(),
      );
      if (current !== requestId) return;
      years.value = result;
      const keep = result.some((row) => row.year === activeYear.value);
      await loadYear(keep ? activeYear.value : (result[0]?.year ?? null));
    } catch (err) {
      console.error(err);
      if (current === requestId) {
        error.value = true;
        loading.value = false;
      }
    }
  };

  const load = () => (viewMode.value === VIEW_LIST
    ? loadListPage(listPagination.value.page || 1)
    : loadPeriods());

  const setListMode = async (mode) => {
    if (listMode.value === mode) return;
    listMode.value = mode;
    // Budgets and invoices rarely share the same years; start from the newest.
    activeYear.value = null;
    listPagination.value = { ...listPagination.value, page: 1 };
    await load();
  };

  // The user's choice is kept for the next contracts (per browser).
  const setViewMode = (mode) => {
    if (mode === viewMode.value) return;
    viewMode.value = mode;
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, mode);
    } catch {
      // Storage unavailable: the choice lasts for this page only.
    }
    load();
  };

  const reset = () => {
    requestId++;
    years.value = [];
    activeYear.value = null;
    invoices.value = [];
    listInvoices.value = [];
    listPagination.value = { ...listPagination.value, page: 1, total: 0, totalPages: 0 };
    loading.value = false;
    error.value = false;
    listMode.value = 'invoice';
  };

  // Keeps the "send" button in sync after a PDF is generated, without reloading.
  const updateInvoiceFile = ({ id, invoice_file }) => {
    for (const list of [invoices.value, listInvoices.value]) {
      const item = list.find((inv) => inv.id === parseInt(id));
      if (item) item.invoice_file = invoice_file;
    }
  };

  return reactive({
    years, activeYear, invoices, loading, error, listMode,
    viewMode, listInvoices, listPagination,
    load, loadYear, loadListPage, setListMode, setViewMode, reset, updateInvoiceFile,
  });
}
