// plugins/services/coredata/street-api.js
export default defineNuxtPlugin(nuxtApp => {
  const service = '/logger/';
  const provideName = 'LoggerApiService';

  const {$apiManager} = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;
  
  const getAll = async (entity, obj_id, page = 1, sort = null, desc = false) => {
    // console.log('getAll', entity, obj_id, page, sort, desc);

    let apiUrl = apiHost + service + entity + `/?page=${page}`;
    
    // TODO: Afegir el filtre de rel_id

    if( sort ) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if( obj_id ) {
      apiUrl += `&object=${obj_id}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }
 
  const getReadingChanges = async (params = {}) => {
    let apiUrl = apiHost + service + 'reading-change/?';
    const queryParts = [];
    if (params.contract) {
      queryParts.push(`contract=${params.contract}`);
    }
    if (params.meter) {
      queryParts.push(`meter=${params.meter}`);
    }
    if (params.page) {
      queryParts.push(`page=${params.page}`);
    }
    apiUrl += queryParts.join('&');

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response && response.results) {
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
    getReadingChanges
  };

  nuxtApp.provide(provideName, apiService);
});
