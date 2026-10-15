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
   * Starts the smart metering preview Celery task (Introduir lectures).
   * Returns `{ task_id }`; 409 if a load already exists for that date
   * (`existing_document.replaceable` tells whether it can be replaced).
   */
  const previewReadings = async ({ reading_date, replace = false } = {}) => {
    const params = new URLSearchParams();
    params.set('reading_date', reading_date ?? '');
    if (replace) params.set('replace', 'true');
    const apiUrl = `${apiHost}/billing/reading-document/smart-metering/preview/?${params.toString()}`;

    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  };

  /** Saves the previewed readings into a new (or replaced) reading document. */
  const importReadings = async (data) => {
    const apiUrl = `${apiHost}/billing/reading-document/smart-metering/import/`;

    try {
      return await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getMeterReading,
    previewReadings,
    importReadings,
  };

  nuxtApp.provide(provideName, apiService);
});
