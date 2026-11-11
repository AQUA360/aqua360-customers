import { ref, reactive } from 'vue';

// Contract invoices grouped by the year of the billed period (or the issue date when
// the invoice has no period). Only the selected year is loaded.
export const NO_PERIOD_YEAR = 'none';

export function useContractInvoicesByPeriod(getContractId) {
  const { $InvoiceApiService } = useNuxtApp();

  const years = ref([]); // [{ year, count }], newest first, NO_PERIOD_YEAR last
  const activeYear = ref(null);
  const invoices = ref([]);
  const loading = ref(false);
  const error = ref(false);
  // 'invoice' → is_invoice=true; 'budget' → is_invoice=false
  const listMode = ref('invoice');

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

  // Reloads the years and keeps the selected one if it still has invoices.
  const load = async () => {
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

  const setListMode = async (mode) => {
    if (listMode.value === mode) return;
    listMode.value = mode;
    // Budgets and invoices rarely share the same years; start from the newest.
    activeYear.value = null;
    await load();
  };

  const reset = () => {
    requestId++;
    years.value = [];
    activeYear.value = null;
    invoices.value = [];
    loading.value = false;
    error.value = false;
    listMode.value = 'invoice';
  };

  // Keeps the "send" button in sync after a PDF is generated, without reloading.
  const updateInvoiceFile = ({ id, invoice_file }) => {
    const item = invoices.value.find((inv) => inv.id === parseInt(id));
    if (item) item.invoice_file = invoice_file;
  };

  return reactive({
    years, activeYear, invoices, loading, error, listMode,
    load, loadYear, setListMode, reset, updateInvoiceFile,
  });
}
