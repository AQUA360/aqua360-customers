// plugins/services/coredata/street-api.js
export default defineNuxtPlugin(nuxtApp => {
  const service = '/logger/';
  const provideName = 'LoggerChangeApiService';

  const {$apiManager} = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;
  
  const getAll = async (entity, object, obj_id, page = 1, sort = null, desc = false) => {
    // console.log('getAll', entity, obj_id, page, sort, desc);

    let apiUrl = apiHost + service + entity + `/?page=${page}`;
    
    // TODO: Afegir el filtre de rel_id

    if( sort ) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if( obj_id ) {
      apiUrl += `&${object}=${obj_id}`;
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
 
  const apiService = {
    getAll 
  };

  nuxtApp.provide(provideName, apiService);
});
