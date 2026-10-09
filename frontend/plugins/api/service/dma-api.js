// plugins/services/service/dma-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/dma/';
    const provideName = 'DMAApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', page = 1, sort = null, desc = false) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    };
  
    const apiService = {
      getAll,
      getDetail
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  