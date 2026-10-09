export default defineNuxtPlugin((nuxtApp) => {
  const provideName = 'SmartMeteringApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getMeterReading = async ({ meter = null, meter_id = null, date = null, margin = null } = {}) => {
    const params = new URLSearchParams();
    if (meter) params.set('meter', meter);
    if (meter_id) params.set('meter_id', meter_id);
    if (date) params.set('date', date);
    if (margin != null) params.set('margin', String(margin));

    const apiUrl = `${apiHost}/billing/smart-metering/meter-reading/?${params.toString()}`;

    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  };

  /**
   * Starts the smart metering preview Celery task.
   * Returns either:
   * - `{ task_id }` (async — poll via ProcessColorBadge / task-progress)
   * - full preview payload with `readings` (legacy sync backends)
   */
  const previewBatchReadings = async (batchId, data) => {
    const readingDate = encodeURIComponent(data?.reading_date ?? '');
    const apiUrl = `${apiHost}/billing/reading-batch-summary/${batchId}/smart-metering/preview/?reading_date=${readingDate}`;

    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  };

  const assignBatchReadings = async (batchId, data) => {
    const apiUrl = `${apiHost}/billing/reading-batch-summary/${batchId}/smart-metering/assign/`;

    try {
      return await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getMeterReading,
    previewBatchReadings,
    assignBatchReadings,
  };

  nuxtApp.provide(provideName, apiService);
});
