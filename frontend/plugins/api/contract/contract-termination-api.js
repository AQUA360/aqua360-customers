// plugins/contract/contract-termination-request-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract-termination-request/';
  const provideName = 'ContractTerminationApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, type_ids = [], has_invoice = null, search_by_address = '') => {
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

    if (type_ids.length > 0) {
      apiUrl += `&type=${type_ids.join(',')}`;
    }

    if (has_invoice!=null) {
      apiUrl += `&no_invoice=${has_invoice}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
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

  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, type_ids = [], has_invoice = null, search_by_address = '', columns = []) => {
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: {
        type: type_ids,
        no_invoice: has_invoice,
        search_by_address,
      }
    });
  }

  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = data.id ? 'PUT' : 'POST';
      if( method == 'PUT' ){
        apiUrl += data.id + '/';
      }
      let response
      if (data.file){
        let options;
        const formData = new FormData();
        formData.append('termination_file', data.file);
        formData.append('id', data.id);
        options = formData;
        response = await $apiManager.fetch(apiUrl, method, options);
      } else {
        response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
      }
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }

  }

  const cancelTermination = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/cancel/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT');
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const close = async (id, data = null) => {

    const apiUrl = `${apiHost}${entity}close/${id}`;

    // Create a FormData object
    const formData = new FormData();
    if (data) {
      formData.append('status', data.status);
      formData.append('status_name', data.status_name);
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', formData);

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/contract/contract-termination-request-status/';

    try {
      const response = await $apiManager.fetch(apiUrl,'GET')
      if (response.results) {
        return response.results;
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

  const getDocument = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/download`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET', null, { 'Content-Type': 'application/pdf' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
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

  const apiService = {
    getAll,
    exportData,
    getDetail,
    save,
    close,
    doDelete,
    cancelTermination,
    getFilterStatus,
    getDocument,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
