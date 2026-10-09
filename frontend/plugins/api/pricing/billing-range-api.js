// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/billing-range/';
    const provideName = 'BillingRangeApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, price_rate = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      if (price_rate) {
        apiUrl += `&price_rate=${price_rate}`;
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
    
    // Server-side export (async). Mirrors getAll's search/filter/sort but POSTs
    // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
    // background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, price_rate = null, columns = []) => {
      return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns, extraParams: { price_rate } });
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
      exportData,
      save,
      getDetail
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  