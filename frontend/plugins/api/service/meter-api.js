// plugins/services/service/meter-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/meter/';
  const provideName = 'MeterApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (
    searchQuery = '', filters = [], page = 1, sort = null,
    desc = false, noSupplyPoint = false, exclude = null,
    is_property = null, is_compound = null, is_general = null, 
    search_by_address = '', remote_reading_type = null, remote_reading_history = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (noSupplyPoint) {
      apiUrl += `&no_supply_points=true`;
    }

    if (exclude) {
      apiUrl += `&exclude=${exclude}`;
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

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (is_property) {
      apiUrl += `&is_property=${is_property}`;
    }

    if (is_compound) {
      apiUrl += `&is_compound=${is_compound}`;
    }

    if (is_general) {
      apiUrl += `&is_general=${is_general}`;
    }

    if (remote_reading_type) {
      apiUrl += `&remote_reading_type=${remote_reading_type}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
    }

    if (remote_reading_history !== null && remote_reading_history !== undefined) {
      apiUrl += `&remote_reading_history=${remote_reading_history}`;
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

  // Server-side export (async). Mirrors getData's filters/search/sort but POSTs
  // to `{entity}export/`, returning `{ task_id }`. Same args as getData (no page).
  const exportData = async (
    searchQuery = '', filters = [], sort = null,
    desc = false, noSupplyPoint = false, exclude = null,
    is_property = null, is_compound = null, is_general = null,
    search_by_address = '', remote_reading_type = null, remote_reading_history = null, columns = []) => {
    let exploitation_id = localStorage.getItem('exploitation');

    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: {
        no_supply_points: noSupplyPoint ? 'true' : null,
        exclude,
        is_property: is_property ? is_property : null,
        is_compound: is_compound ? is_compound : null,
        is_general: is_general ? is_general : null,
        remote_reading_type,
        search_by_address: search_by_address || null,
        remote_reading_history: (remote_reading_history !== null && remote_reading_history !== undefined) ? remote_reading_history : null,
        exploitation: exploitation_id || null,
      }
    });
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/service/meter-status/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  const updateStatus = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/status/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      return response;
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
  };

  const getByReadingDocument = async (data) => {
    const apiUrl = `${apiHost}${entity}reading-document/`;

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
  };

  const createMeter = async (data) => {
    const apiUrl = `${apiHost}${entity}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      console.log('response', response)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      console.log('error', error)
      throw error;
    }

  }

  const updateMeter = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })

      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const deleteMeter = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE')
      return true;

    } catch (error) {
      throw error;
    }
  };
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

  const checkCode = async (code, excludeId = null) => {
    let apiUrl = `${apiHost}${entity}check-code/?code=${encodeURIComponent(code)}`;
    if (excludeId) apiUrl += `&exclude_id=${excludeId}`;
    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  }

  const exportCsv = async (
    searchQuery = '', filters = [], sort = null,
    desc = false, is_property = null, is_compound = null, is_general = null) => {
    let apiUrl = apiHost + entity + 'export/csv/';
    let queryParams = [];

    if (searchQuery) {
      queryParams.push('search=' + encodeURIComponent(searchQuery));
    }

    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      })
    }

    if (filtersValues.length > 0) {
      queryParams.push(`status=${filtersValues.join(',')}`);
    }

    if (sort) {
      queryParams.push(`ordering=${desc ? '-' : ''}${sort}`);
    }

    if (is_property !== null) {
      queryParams.push(`is_property=${is_property}`);
    }

    if (is_compound !== null) {
      queryParams.push(`is_compound=${is_compound}`);
    }

    if (is_general !== null) {
      queryParams.push(`is_general=${is_general}`);
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      queryParams.push(`exploitation=${exploitation_id}`);
    }

    if (queryParams.length > 0) {
      apiUrl += '?' + queryParams.join('&');
    }

    const authToken = localStorage.getItem('auth_token') || '';
    
    try {
      const response = await $fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Token ${authToken}`
        }
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

  const lookupByCodes = async (codes = []) => {
    const apiUrl = `${apiHost}${entity}lookup-by-codes/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { codes }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const lookupByCodesCsv = async (codes = []) => {
    const apiUrl = `${apiHost}${entity}lookup-by-codes/csv/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { codes }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const bulkUpdatePreview = async (file) => {
    const apiUrl = `${apiHost}${entity}bulk-update/preview/`;
    const formData = new FormData();
    formData.append('file', file);
    try {
      return await $apiManager.fetch(apiUrl, 'POST', formData);
    } catch (error) {
      throw error;
    }
  }

  const bulkUpdateConfirm = async (file) => {
    const apiUrl = `${apiHost}${entity}bulk-update/confirm/`;
    const formData = new FormData();
    formData.append('file', file);
    try {
      return await $apiManager.fetch(apiUrl, 'POST', formData);
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getData,
    exportData,
    getFilterStatus,
    getDetail,
    createMeter,
    updateMeter,
    deleteMeter,
    getLogs,
    updateStatus,
    getByReadingDocument,
    getPermissions,
    exportCsv,
    lookupByCodes,
    lookupByCodesCsv,
    bulkUpdatePreview,
    bulkUpdateConfirm,
    checkCode
  };

  nuxtApp.provide(provideName, apiService);
});
