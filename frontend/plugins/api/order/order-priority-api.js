export default defineNuxtPlugin(nuxtApp => {
  const entity = '/order/order-priority/';
  const provideName = 'OrderPriorityApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async () => {
    let apiUrl = apiHost + entity;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')

      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll
  };

  nuxtApp.provide(provideName, apiService);
});
