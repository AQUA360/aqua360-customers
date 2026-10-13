// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/communication/communication/';
    const provideName = 'CommunicationApiService';
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, process_id = null, person_ids = [], is_individual = null, types = [], contract_id = [], date_range = null) => {
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

      if (process_id) {
        apiUrl += `&process=${process_id}`;
      }

      if (person_ids.length > 0) {
        apiUrl += `&person=${person_ids.join(',')}`;
      }

      if (is_individual) {
        apiUrl += `&is_individual=${is_individual}`;
      }

      if (types.length > 0) {
        apiUrl += `&types=${types.join(',')}`;
      }

      if (contract_id) {
        apiUrl += `&contract=${contract_id}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`; 
      }

      if (date_range && date_range.start_date && date_range.end_date) {
        apiUrl += `&start_date=${date_range.start_date}&end_date=${date_range.end_date}`;
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

    const saveDocumentationFile = async (data) => {
      let apiUrl = `${apiHost}/communication/communication-file/`;
      try {
        let options;
        const formData = new FormData();
        formData.append('document', data.document);
        formData.append('communication', data.communication);
  
        options = formData;
        const response = await $apiManager.fetch(apiUrl, 'POST', options)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const saveMessage = async (data) => {
      let apiUrl = `${apiHost}/communication/message/`;
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

    const generateFiles = async (data) => {
      let apiUrl = `${apiHost}/communication/communication-generate-files`;
      try {
        // Si hi ha un fitxer (data.document és un File object), cal usar FormData
        let requestData = data;
        if (data.document && data.document instanceof File) {
          const formData = new FormData();
          formData.append('document', data.document);
          if (data.communication) {
            formData.append('communication', data.communication);
          }
          requestData = formData;
        }
        const response = await $apiManager.fetch(apiUrl, 'POST', requestData)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getClientData = async (data) => {
      let apiUrl = `${apiHost}${entity}get-client-info/`;
      if (data.contract_id) {
        apiUrl += `?contract_id=${data.contract_id}`;
      }
      if (data.person_id) {
        apiUrl += `?person_id=${data.person_id}`;
      }
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

    const checkGenerateFilesProgress = async (taskId) => {
      let apiUrl = `${apiHost}/communication/communication-generate-files/status/${taskId}`;
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

    const sendCommunications = async (data) => {
      let apiUrl = `${apiHost}/communication/send-communications/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const markAsSent = async (data) => {
      let apiUrl = `${apiHost}${entity}mark-as-sent/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getEmailPreview = async (message) => {
      let apiUrl = `${apiHost}${entity}email-preview/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', message)
        if (response) {
          return response;
        }
      }
      catch (error) {
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

    const returnLetter = async (data) => {
      let apiUrl = `${apiHost}${entity}return-letter/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data)
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
    // POSTs to `{entity}export/` so the backend builds the full, filter-aware
    // XLSX as a background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, process_id = null, person_ids = [], is_individual = null, types = [], contract_id = [], date_range = null, columns = []) => {
      let exploitation_id = localStorage.getItem('exploitation');

      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc, columns,
        extraParams: {
          process: process_id,
          person: person_ids,
          is_individual: is_individual ? is_individual : null,
          types,
          contract: contract_id,
          exploitation: exploitation_id || null,
          start_date: date_range && date_range.start_date && date_range.end_date ? date_range.start_date : null,
          end_date: date_range && date_range.start_date && date_range.end_date ? date_range.end_date : null,
        }
      });
    }

    const apiService = {
      getAll,
      getDetail,
      save,
      saveDocumentationFile,
      saveMessage,
      generateFiles,
      checkGenerateFilesProgress,
      sendCommunications,
      markAsSent,
      returnLetter,
      getEmailPreview,
      getClientData,
      deleteItem,
      getPermissions,
      exportData
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  