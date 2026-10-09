// plugins/services/service/property-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/property/';
  const provideName = 'PropertyApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', page = 1, sort = null, desc = false, only_unassigned = false, search_by_address = '') => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (only_unassigned) {
      apiUrl += `&only_unassigned=true`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
    }

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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

  // Server-side export (async). Mirrors getAll's search/sort/address filters but
  // POSTs to `{entity}export/` so the backend builds the full, filter-aware XLSX
  // as a background task, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', sort = null, desc = false, only_unassigned = false, search_by_address = '', columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');
    return $apiManager.exportTable(entity, {
      searchQuery, sort, desc, columns,
      extraParams: {
        only_unassigned: only_unassigned ? 'true' : null,
        search_by_address: search_by_address || null,
        exploitation: exploitation_id || null,
      },
    });
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
  };


  const save = async (data) => {
    const apiUrl = `${apiHost}${entity}`;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    try {
      const response = await $apiManager.fetch(url, method, JSON.stringify(data) );
      
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const deleteProperty = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = $apiManager.fetch(apiUrl, 'DELETE');
      
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

  const apiService = {
    getAll,
    exportData,
    getDetail,
    save,
    deleteProperty,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
