// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/billing/';
  const provideName = 'BillingApiService';

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

  // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
  // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
  // background task, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns });
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

  const patch = async (id, data) => {
    let apiUrl = `${apiHost}${entity}${id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PATCH', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const remove = async (id) => {
    let apiUrl = `${apiHost}${entity}${id}/`;

    try {

      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return response;

    } catch (error) {
      throw error;
    }
  }

  const checkMissingContracts = async (id, type, is_csv = false) => {
    let apiUrl = `${apiHost}${entity}${id}/check-missing`;
    if (type) {
      apiUrl += `?type=${type}`;
    }
    
    if (is_csv) {
      apiUrl += `${apiUrl.includes('?') ? '&' : '?'}is_csv=true`;
    }
    try {

      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;

    } catch (error) {
      throw error;
    }
  }

  const generateMissingBatch = async (data) => {
    let apiUrl = `${apiHost}${entity}missing-contracts/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      return response;
    } catch (error) {
      throw error;
    }
  }



  const exclude = async (data) => {
    let apiUrl = apiHost + '/billing/exclude/';
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

  const summary = async () => {
    let apiUrl = apiHost + '/billing/summary';
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

  const getRoutes = async (id) => {
    let apiUrl = apiHost + '/billing/billing-routes?id=' + id;
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

  const getBadges = async () => {
    let apiUrl = apiHost + '/billing/badges';
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

  const assignReadings = async (id, data) => {
    let apiUrl = apiHost + '/billing/billing/pre-invoices/' + id + '/assign-readings';
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
  const getSummary = async (id) => {
    let apiUrl = apiHost + '/billing/billing/pre-invoices/' + id + '/summary';
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
  const downloadSummary = async (id) => {
    let apiUrl = apiHost + '/billing/billing/pre-invoices/' + id + '/summary/xls';
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
  const recalculate = async (id) => {
    let apiUrl = apiHost + '/billing/billing/' + id + '/recalculate';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }
  const regeneratePdfs = async (id) => {
    let apiUrl = apiHost + '/billing/billing/' + id + '/regenerate-pdfs';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' });
      if (response) { return response; } else { throw new Error('Error no trobat'); }
    } catch (error) { throw error; }
  }

  const checkRegeneratePdfsTask = async (taskId) => {
    let apiUrl = apiHost + '/billing/billing/regenerate-pdfs/status/' + taskId + '/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) { return response; } else { throw new Error('Error no trobat'); }
    } catch (error) { throw error; }
  }

  const getBatchPdf = async (id) => {
    let apiUrl = apiHost + '/billing/batch/' + id + '/pdf';
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

  const getReadings = async (id, query = '', page = 1, filter = null) => {
    let apiUrl = `${apiHost}/billing/billing/${id}/readings`;
    apiUrl += `?search=${encodeURIComponent(query)}&page=${page}`;
    if (filter) {
      apiUrl += `&${filter}`;
    }
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

  const generateInvoiceBudget = async (billingId, data) => {
    let apiUrl = apiHost + '/billing/billing/' + billingId + '/generate-invoice-budget/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const moveBudgetToPreInvoice = async (billingId, data) => {
    let apiUrl = apiHost + '/billing/billing/' + billingId + '/update-pre-invoices/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const moveInvoiceToBilling = async (billingId, data) => {
    let apiUrl = apiHost + '/billing/billing/' + billingId + '/move-invoice-to-billing/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const start = async (billerId = null, token = null, name = null) => {
    let apiUrl = apiHost + '/billing/start';
    const params = [];
  
    if (billerId) params.push(`biller_id=${billerId}`);
    if (token) params.push(`token=${encodeURIComponent(token)}`);
    if (name) params.push(`name=${encodeURIComponent(name)}`);
  
    apiUrl += params.length > 0 ? `?${params.join('&')}` : '/';
  
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

  const cancel = async (id) => {
    let apiUrl = apiHost + entity + id + '/cancel/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', {}, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const addEstimatedReading = async (billingId, contractId) => {
    let apiUrl = `${apiHost}/billing/billing/${billingId}/add-estimated-reading/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { contract_id: contractId }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const addToBatch = async (billingId, contractId) => {
    let apiUrl = `${apiHost}/billing/billing/${billingId}/add-to-batch/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { contract_id: contractId }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const processContract = async (billingId, contractId) => {
    let apiUrl = `${apiHost}/billing/billing/${billingId}/process-contract/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { contract_id: contractId }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const processSelectedContracts = async (billingId, contractIds) => {
    let apiUrl = `${apiHost}/billing/billing/${billingId}/process-selected/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { contract_ids: contractIds }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getBillingQueue = async (billingId = null) => {
    let apiUrl = `${apiHost}/billing/billing-queue/`;
    if (billingId) {
      apiUrl += `?billing_id=${billingId}`;
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  /** action: 'kill' | 'skip' | 'restart' */
  const sendBillingQueueAction = async (queueItemId, action) => {
    let apiUrl = `${apiHost}/billing/billing-queue/${queueItemId}/action/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { action }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    exportData,
    getDetail,
    save,
    remove,
    exclude,
    summary,
    getRoutes,
    getBadges,
    getSummary,
    downloadSummary,
    recalculate,
    regeneratePdfs,
    checkRegeneratePdfsTask,
    moveInvoiceToBilling,
    getBillingQueue,
    sendBillingQueueAction,
    getBatchPdf,
    start,
    checkMissingContracts,
    getReadings,
    generateMissingBatch,
    assignReadings,
    getPermissions,
    patch,
    cancel,
    addEstimatedReading,
    moveBudgetToPreInvoice,
    generateInvoiceBudget,
    addToBatch,
    processContract,
    processSelectedContracts,
  };

  nuxtApp.provide(provideName, apiService);
});
