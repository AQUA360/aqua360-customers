// plugins/services/service/connection-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/connection/';
  const provideName = 'ConnectionApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (
    searchQuery = '', filters = [], page = 1, sort = null,
    desc = false, exploitation_id = null, type_ids = [],
    use_type_ids = [], material_ids = [], valve_type_ids = [], search_by_address = '') => {
      
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    /* if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`;
    } */

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

    if (type_ids.length > 0) {
      apiUrl += `&type=${type_ids.join(',')}`;
    }

    if (use_type_ids.length > 0) {
      apiUrl += `&use_type=${use_type_ids.join(',')}`;
    }

    if (material_ids.length > 0) {
      apiUrl += `&material=${material_ids.join(',')}`;
    }

    if (valve_type_ids.length > 0) {
      apiUrl += `&valve_type=${valve_type_ids.join(',')}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
    }

    let exploitation_local_id = localStorage.getItem('exploitation');
    if (exploitation_local_id) {
      apiUrl += `&exploitation=${exploitation_local_id}`; 
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
  const exportData = async (
    searchQuery = '', filters = [], sort = null,
    desc = false, exploitation_id = null, type_ids = [],
    use_type_ids = [], material_ids = [], valve_type_ids = [], search_by_address = '',
    columns = []) => {
    const exploitation_local_id = localStorage.getItem('exploitation');
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc,
      columns,
      extraParams: {
        type: type_ids,
        use_type: use_type_ids,
        material: material_ids,
        valve_type: valve_type_ids,
        search_by_address,
        exploitation: exploitation_local_id || null,
      }
    });
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/service/connection-status/';

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
  };

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

  const getClusters = async (connectionId) => {
    const apiUrl = `${apiHost}/service/cluster/?connection=${connectionId}`;

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

  const save = async (data) => {
    const apiUrl = `${apiHost}${entity}`;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    try {
      const response = await $apiManager.fetch(url, method, JSON.stringify(data), { 'Content-Type': 'application/json' });
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const activate = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/activate/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST');
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const remove = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;
    const response = await $apiManager.fetch(apiUrl, 'DELETE');
    return response;
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

  const saveFile = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/save-file/`;
    try {
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('id', data.id);
      formData.append('connection_type', data.connection_type || '');
      const response = await $apiManager.fetch(apiUrl, 'PUT', formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const convertToCluster = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/convert-to-cluster/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', {}, { 'Content-Type': 'application/json' });
      if (response) {
        return response;
      } else {
        throw new Error('Error convertToCluster');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getData,
    exportData,
    getFilterStatus,
    getDetail,
    getClusters,
    save,
    saveFile,
    activate,
    remove,
    getPermissions,
    convertToCluster
  };

  nuxtApp.provide(provideName, apiService);
});
