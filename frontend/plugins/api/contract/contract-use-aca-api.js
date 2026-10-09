// plugins/services/contract/contract-use-aca-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract-use-aca/';
  const provideName = 'ContractUseAcaApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getStats = async () => {
    const apiUrl = apiHost + entity;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const fill = async (data = {}) => {
    const apiUrl = apiHost + entity;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
      return response ?? {};
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getStats,
    fill,
  };

  nuxtApp.provide(provideName, apiService);
});
