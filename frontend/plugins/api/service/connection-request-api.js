// plugins/services/service/connection-request-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/connection-request/';
  const entityStatus = '/service/connection-request-status/';
  const provideName = 'ConnectionRequestApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, search_by_address = '') => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    // Afegir els filtres a la URL
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

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`; 
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

  // Server-side export (async). Mirrors getData's filters/search/sort but POSTs
  // to `{entity}export/`, returning `{ task_id }`. Same args as getData (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, search_by_address = '', columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc,
      columns,
      extraParams: { search_by_address, exploitation: exploitation_id || null }
    });
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + entityStatus;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

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


  const get = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      return response;
    } catch (error) {
      throw error;
    }
  };

  const save = async (data) => {
    const apiUrl = `${apiHost}${entity}`;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    // Create a FormData object
    const formData = new FormData();


    // Append all fields from data to formData
    for (const key in data) {
      if (data[key] != "" && data[key] != null) {
        formData.append(key, data[key]);
      }
    }

    try {
      const response = await $apiManager.fetch(url, method, formData);
      
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const closeRequest = async (id) => {

    const apiUrl = `${apiHost}${entity}close/${id}`;

    // Create a FormData object
    const formData = new FormData();

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
    getData,
    getFilterStatus,
    getDetail,
    get,
    save,
    closeRequest,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
