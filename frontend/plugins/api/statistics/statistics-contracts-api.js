export default defineNuxtPlugin((nuxtApp) => {
  const provideName = 'StatisticsContractsApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  /** POST /statistics/contracts/export/ — retorna { task_id, ... } (202) */
  const exportContracts = async (data) => {
    const apiUrl = `${apiHost}/statistics/contracts/export/`;
    const response = await $apiManager.fetch(apiUrl, 'POST', data);
    return response;
  };

  /** POST /statistics/contracts/invoice-reading-summary/export/ — retorna { task_id, ... } (202) */
  const exportInvoiceReadingSummary = async (data) => {
    const apiUrl = `${apiHost}/statistics/contracts/invoice-reading-summary/export/`;
    const response = await $apiManager.fetch(apiUrl, 'POST', data);
    return response;
  };

  /** POST /statistics/contracts/pricerates/export/ — retorna { task_id, ... } (202) */
  const exportPriceRates = async (data) => {
    const apiUrl = `${apiHost}/statistics/contracts/pricerates/export/`;
    const response = await $apiManager.fetch(apiUrl, 'POST', data);
    return response;
  };

  /** POST /statistics/contracts/termination-reading-invoice/export/ — retorna { task_id, ... } (202) */
  const exportTerminationReadingInvoice = async (data) => {
    const apiUrl = `${apiHost}/statistics/contracts/termination-reading-invoice/export/`;
    const response = await $apiManager.fetch(apiUrl, 'POST', data);
    return response;
  };

  nuxtApp.provide(provideName, {
    exportContracts,
    exportInvoiceReadingSummary,
    exportPriceRates,
    exportTerminationReadingInvoice,
  });
});
