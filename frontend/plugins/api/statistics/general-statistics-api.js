export default defineNuxtPlugin((nuxtApp) => {
  const provideName = 'GeneralStatisticsApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const updateDailyConsumption = async () => {
    const apiUrl = `${apiHost}/statistics/update-daily-consumption`;
    return await $apiManager.fetch(apiUrl, 'POST');
  };

  const updateBillingBackfill = async () => {
    const apiUrl = `${apiHost}/statistics/update-billing-backfill`;
    return await $apiManager.fetch(apiUrl, 'POST');
  };

  const getSummaryConsumptionByUse = async (params = {}) => {
    const query = new URLSearchParams(params).toString();
    const apiUrl = `${apiHost}/statistics/summary-consumption-by-use${query ? `?${query}` : ''}`;
    return await $apiManager.fetch(apiUrl, 'GET');
  };

  const getSummaryBillingByUse = async (params = {}) => {
    const query = new URLSearchParams(params).toString();
    const apiUrl = `${apiHost}/statistics/summary-billing-by-use${query ? `?${query}` : ''}`;
    return await $apiManager.fetch(apiUrl, 'GET');
  };

  nuxtApp.provide(provideName, {
    updateDailyConsumption,
    updateBillingBackfill,
    getSummaryConsumptionByUse,
    getSummaryBillingByUse,
  });
});
