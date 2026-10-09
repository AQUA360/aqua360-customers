// plugins/services/service/supply-point-request-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/supply-point-request/';
  const entityStatus = '/service/supply-point-request-status/';
  const provideName = 'SupplyPointRequestApiService';

  const {$apiManager} = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
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
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns });
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

  const saveDocument = async (data) => {
    const apiUrl = `${apiHost}/service/supply-point-request-document/`;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

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
        throw new Error('Error no hi ha resposta');
      }
    } catch (error) {
      throw error;
    }
  };

  const deleteDocument = async (id) => {
    const apiUrl = `${apiHost}/service/supply-point-request-document/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return response;
    }
    catch (error) {
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

  const deleteRequest = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return response;
    }
    catch (error) {
      throw error;
    }
  };

  const apiService = {
    getData,
    exportData,
    getFilterStatus,
    getDetail,
    get,
    save,
    closeRequest,
    deleteRequest,
    saveDocument,
    deleteDocument
  };

  nuxtApp.provide(provideName, apiService);
});
