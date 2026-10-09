// plugins/services/contract/contract-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/bail/';
  const provideName = 'BailApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contractStatusFilters = []) => {
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

    if (contractStatusFilters?.length > 0) {
      apiUrl += `&contract_status=${contractStatusFilters.join(',')}`;
    }

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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

  // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
  // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
  // background task, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = [], contractStatusFilters = []) => {
    let exploitation_id = localStorage.getItem('exploitation');

    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: {
        exploitation: exploitation_id || null,
        contract_status: contractStatusFilters,
      }
    });
  }

  const doReturn = async (id) => {
    const apiUrl = `${apiHost}${entity}return/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT')
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
    const apiUrl = apiHost + '/contract/bail-status/';

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

  const getFilterContractStatus = async () => {
    const apiUrl = apiHost + '/contract/contract-status/';

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

  const liquidate = async (data) => {
    const apiUrl = `${apiHost}${entity}liquidate/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data)
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const cancel = async (data) => {
    const apiUrl = `${apiHost}${entity}cancel/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data)
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
    doDelete,
    getFilterStatus,
    getFilterContractStatus,
    doReturn,
    liquidate,
    cancel,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
