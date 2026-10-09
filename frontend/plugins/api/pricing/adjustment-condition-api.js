// plugins/services/pricing/adjustment-condition-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/adjustment-condition/';
    const provideName = 'AdjustmentConditionApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, adjustment_id = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      if( ! adjustment_id ) {
        console.error('No s\'ha passat l\'id del corrector');
        return [];
      }

      apiUrl += `&adjustment=${adjustment_id}`;
      
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
      
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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
    
    const save = async (data) => {
      let apiUrl = `${apiHost}${entity}`;
      try {
        const method = data.id ? 'PUT' : 'POST';
        if (method == 'PUT') {
          apiUrl += data.id + '/';
        }
        const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const doDelete = async (data ) => {
      const apiUrl = `${apiHost}${entity}${data.id}/`;
      try {
        await $apiManager.fetch(apiUrl, 'DELETE');
      } catch (error) {
        throw error;
      }
    } 
  
    const apiService = {
      getAll,
      save,
      getDetail,
      doDelete
    }
  
    nuxtApp.provide(provideName, apiService);
});
