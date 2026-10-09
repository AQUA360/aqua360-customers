// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/communication/communication-process/';
    const provideName = 'CommunicationProcessApiService';
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, types = [], supplyCut = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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
  
      if (types.length > 0) {
        apiUrl += `&types=${types.join(',')}`;
      }

      if (supplyCut) {
        apiUrl += `&supply_cut=${supplyCut}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`; 
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

    // Preflight for the supply cut guard. Returns the tier the server computed
    // ('none' | 'warn' | 'block') plus the processes that caused it, so the UI
    // can ask for confirmation before the user commits to the wizard.
    const getSupplyCutStatus = async (supplyCutId) => {
      const apiUrl = `${apiHost}${entity}supply-cut-status/?supply_cut=${supplyCutId}`;

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
  
    const getCommunicationProcessData = async (data) => {
      const apiUrl = `${apiHost}${entity}get-data`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
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

    const downloadEInvoices = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/e-invoices/`;
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

    const sendMessages = async (id, only_returned = false) => {
      let apiUrl = `${apiHost}${entity}${id}/send-messages/`;
      try {

        if (only_returned) {
          apiUrl += '?only_returned=true';
        }

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
  
    const deleteItem = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        return true;
  
      } catch (error) {
        throw error;
      }
    };

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
  
    // Server-side XLSX export (async). Mirrors getAll's filters/search/sort but
    // POSTs to `{entity}export/`, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, types = []) => {
      let exploitation_id = localStorage.getItem('exploitation');

      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc,
        extraParams: { types, exploitation: exploitation_id || null }
      });
    }

    const apiService = {
      getAll,
      getDetail,
      getSupplyCutStatus,
      getCommunicationProcessData,
      save,
      sendMessages,
      downloadEInvoices,
      deleteItem,
      getPermissions,
      exportData
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  