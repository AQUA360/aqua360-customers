// plugins/services/contract/contract-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/payment-remittance-return/';
    const provideName = 'SepaRemittanceReturnApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
  
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

    // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
    // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
    // background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
      return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns });
    }

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response) {
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
        if( method == 'PUT' ){
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

    
    const doDelete = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'DELETE');
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }
  
  
    const apiService = {
      getAll,
      exportData,
      getDetail,
      save,
      doDelete,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  