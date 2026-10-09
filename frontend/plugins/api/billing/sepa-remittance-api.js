// plugins/services/contract/contract-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/payment-remittance/';
    const provideName = 'SepaRemittanceApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, is_return = null) => {
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

      if (is_return !== null) {
        apiUrl += `&is_return=${is_return}`;
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

    const getPayments = async (id, searchQuery = '', filters = [], page = 1, sort = null, desc = false, pay_type = []) => {
      let apiUrl = `${apiHost}${entity}${id}/payments/?search=${encodeURIComponent(searchQuery)}&page=${page}`;

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

      if (pay_type.length > 0) {
        apiUrl += `&type=${pay_type.join(',')}`;
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

    const exportPaymentsCSV = async (id, searchQuery = '', filters = [], sort = null, desc = false) => {
      let apiUrl = `${apiHost}${entity}${id}/payments/?export=csv&search=${encodeURIComponent(searchQuery)}`;

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

      const authToken = localStorage.getItem('auth_token') || '';
      
      try {
        const response = await $fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Authorization': `Token ${authToken}`
          },
          parseResponse: txt => txt
        });
        
        return response;
      } catch (error) {
        if (error?.response?.status === 401) {
          const message = error?.response?._data?.detail || error?.data?.detail || error?.response?._data?.message || error?.data?.message || error?.message;
          await $apiManager.handleUnauthorized(message);
        }
        throw error;
      }
    }

    const sendRemittance = async (data) => {
      let apiUrl = `${apiHost}${entity}send/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
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

    const deletePaymentRelation = async (paymentRemittanceId, paymentId) => {
      const apiUrl = `${apiHost}${entity}${paymentRemittanceId}/delete-payment-relation/${paymentId}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }

    const regenerateDocument = async (data) => {
      const apiUrl = `${apiHost}/billing/sepa-document-generate/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }

    const regenerateSepaDocument = async (id, data = {}) => {
      const apiUrl = `${apiHost}${entity}${id}/sepa-document-generate/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }

    const validateFile = async (file) => {
      const apiUrl = `${apiHost}/billing/sepa-validate/`;
      const formData = new FormData();
      formData.append('file', file);
      try {
        // 400 with { valid: false, errors, error } is an expected validation result, not a toast error.
        return await $apiManager.fetch(apiUrl, 'POST', formData, null, true);
      } catch (error) {
        const data = error?.response?._data;
        if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'valid')) {
          return data;
        }
        throw error;
      }
    }
  
  
    const apiService = {
      getAll,
      exportData,
      getDetail,
      getPayments,
      exportPaymentsCSV,
      save,
      sendRemittance,
      doDelete,
      deletePaymentRelation,
      regenerateDocument,
      regenerateSepaDocument,
      validateFile
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  