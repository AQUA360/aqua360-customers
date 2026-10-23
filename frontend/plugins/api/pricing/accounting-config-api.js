// plugins/api/pricing/accounting-config-api.js
export default defineNuxtPlugin((nuxtApp) => {
  const entity = '/pricing/accounting-config/';
  const provideName = 'AccountingConfigApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getCurrent = async () => {
    const apiUrl = `${apiHost}${entity}current/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error estructura no trobat');
    } catch (error) {
      throw error;
    }
  };

  const saveCurrent = async (data) => {
    const apiUrl = `${apiHost}${entity}current/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, {
        'Content-Type': 'application/json',
      });
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getCurrent,
    saveCurrent,
  };

  nuxtApp.provide(provideName, apiService);
});
