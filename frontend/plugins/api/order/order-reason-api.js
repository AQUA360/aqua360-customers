export default defineNuxtPlugin(nuxtApp => {
    const entity = '/order/order-reason/';
    const provideName = 'OrderReasonApiService';

    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
        let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
        if (sort) {
          apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
        }
    
        try {
          const response = await $apiManager.fetch(apiUrl, 'GET')
          if (response.results) {
            return response;
          } 
          else {
            throw new Error('Error estructura `results` no trobat');
          }
        } 
        catch (error) {
          throw error;
        }
    }

    const apiService = {
        getAll
    };
    
    nuxtApp.provide(provideName, apiService);
});