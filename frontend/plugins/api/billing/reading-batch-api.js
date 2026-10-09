// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/reading-batch/';
  const provideName = 'ReadingBatchApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getDetail = async (id) => {
    const apiUrl = apiHost + entity + id + '/';

    try {
      
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  };

  const downloadBatch = async (id, format = null) => {
    let apiUrl = apiHost + entity + id + '/download/';
    if (format) {
      apiUrl += `?format=${encodeURIComponent(format)}`;
    }

    try {
      
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  };
  
  const getReadingRoutes = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + '/billing/reading-route/' + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}&no_batch=true`;

    // Afegir els filtres a la URL
    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      });
    }

    if (filtersValues.length > 0) {
      apiUrl += `&status=${filtersValues.join(',')}`;
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
  };
  
  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    // Afegir els filtres a la URL
    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      });
    }

    if (filtersValues.length > 0) {
      apiUrl += `&status=${filtersValues.join(',')}`;
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
  };

  const getPendingBilling = async (statusToken) => {
    let apiUrl = apiHost + entity;

    apiUrl += `?status=${statusToken}`;

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
  };

  const generateSummary = async (data) => {
    let apiUrl = apiHost + '/billing/reading-batch-summary/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getSummary = async (batchId) => {
    let apiUrl = apiHost + '/billing/reading-batch-summary?batch_id=' + batchId;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET', null, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateForceManual = async (batchId) => {
    let apiUrl = apiHost + '/billing/reading-batch-summary/' + batchId + '/update-force-manual/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', null, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const assignReadings = async (data) => {
    let apiUrl = apiHost + '/billing/reading-batch-summary/' + data.id + '/assign-readings/';
    try {
      
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const generateBatch = async (data) => {
    let apiUrl = apiHost + '/billing/reading-batch/generate';
    try {
      
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const excludeReading = async (data) => {
    let apiUrl = apiHost + '/billing/reading/exclude/';
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

  const update = async (data) => {
    let apiUrl = apiHost + entity + data.id + '/';
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

  const create = async (data) => {
    let apiUrl = apiHost + entity;
    try {
      
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  /**
   * Crea un lot nou només amb els comptadors dels subministraments sense lectura
   * del lot `id`. El backend calcula la llista (mateix criteri que el llistat
   * "Subministraments sense lectura") i fixa el nou lot per comptadors.
   */
  const createMissingBatch = async (id, name) => {
    const apiUrl = apiHost + entity + id + '/create-missing-batch/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { name }, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getSetupReadings = async (id, filter, page = 1, search = '', sort = null, desc = false) => {
    let apiUrl = apiHost + '/billing/reading-batch/setup/' + id + '/?readings=' + filter;
    apiUrl += `&page=${page}`;
    if (search) {
      apiUrl += `&search=${encodeURIComponent(search)}`;
    }
    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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
  const estimateReadings = async (id, data) => {
    let apiUrl = apiHost + '/billing/reading-batch/estimate-readings/' + id + '/';
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

  const revert = async (id) => {
    const apiUrl = apiHost + entity + id + '/revert/';
    // suppressToast: the caller handles 404/409/500 messages explicitly
    return await $apiManager.fetch(apiUrl, 'POST', null, { 'Content-Type': 'application/json' }, true);
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

  const exportCsv = async (batchId) => {
    const apiUrl = `${apiHost}/billing/reading/by-batch/csv-export/?batch=${batchId}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const exportSupplyPointsCsv = async (batchId) => {
    const apiUrl = `${apiHost}/billing/reading/by-batch/supply-points/csv-export/?batch=${batchId}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getNoRouteSupplyPoints = async (batchId, page = 1) => {
    let apiUrl = apiHost + '/billing/reading-batch-summary/no-route-supply-points/?batch_id=' + batchId + '&page=' + page;
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

  // Server-side XLSX export (async). Mirrors getAll's filters/search/sort but
  // POSTs to `{entity}export/`, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns, extraParams: { exploitation: exploitation_id || null } });
  };

  const apiService = {
    getAll,
    getPendingBilling,
    getReadingRoutes,
    getDetail,
    generateSummary,
    getSummary,
    generateBatch,
    assignReadings,
    excludeReading,
    update,
    create,
    getSetupReadings,
    createMissingBatch,
    getNoRouteSupplyPoints,
    estimateReadings,
    revert,
    getPermissions,
    exportCsv,
    exportSupplyPointsCsv,
    downloadBatch,
    updateForceManual,
    exportData
  };

  nuxtApp.provide(provideName, apiService);
});
