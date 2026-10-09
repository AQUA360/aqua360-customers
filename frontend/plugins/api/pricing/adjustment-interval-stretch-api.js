// plugins/services/pricing/adjustment-interval-stretch-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/adjustment-interval-stretch/';
    const provideName = 'AdjustmentIntervalStretchApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, adjustment_id = null,interval_stretch_id = null, price_variable_stretch_id = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      apiUrl += adjustment_id ? `&adjustment=${adjustment_id}` : '&adjustment=-1';
      if (interval_stretch_id) {
        apiUrl += `&price_interval_stretch=${interval_stretch_id}`;
      }
      if (price_variable_stretch_id) {
        apiUrl += `&price_variable_stretch=${price_variable_stretch_id}`;
      }
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
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
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      save,
      getDetail,
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  