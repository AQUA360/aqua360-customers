// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/verifactu/invoice/';
    const provideName = 'VerifactuApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (
      searchQuery = '', page = 1, 
      sort = null, desc = false, batch_id = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      if (batch_id) {
        apiUrl += `&batch_id=${batch_id}`; 
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
  
    const getAllBatches = async (
      searchQuery = '', page = 1, 
      sort = null, desc = false, 
    ) => {
      let apiUrl = apiHost + '/verifactu/batch/' + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
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
    
    // Server-side export (async). Mirrors getAllBatches' search/sort but POSTs to
    // `/verifactu/batch/export/` so the backend builds the full, filter-aware XLSX
    // as a background task, returning `{ task_id }`. Same args as getAllBatches (no page).
    const exportData = async (
      searchQuery = '', sort = null, desc = false,
    ) => {
      let query = 'search=' + encodeURIComponent(searchQuery);
      if (sort) query += `&ordering=${desc ? '-' : ''}${sort}`;
      const apiUrl = `${apiHost}/verifactu/batch/export/?${query}`;
      try {
        return await $apiManager.fetch(apiUrl, 'POST', { async: true }, { 'Content-Type': 'application/json' });
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

    const notifyVerifactuInvoice = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/notify-verifactu/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT');
        return response;
      } catch (error) {
        throw error;
      }
    }
    
    const getPermissions = async () => {
      const apiUrl = `${apiHost}${entity}permissions/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'GET')
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getBatchDetail = async (id) => {
      const apiUrl = `${apiHost}/verifactu/batch/${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura no trobada');
        }
      } catch (error) {
        throw error;
      }
    }

    const getLogs = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/logs/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      save,
      getDetail,
      notifyVerifactuInvoice,
      getPermissions,
      getAllBatches,
      exportData,
      getBatchDetail,
      getLogs
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  