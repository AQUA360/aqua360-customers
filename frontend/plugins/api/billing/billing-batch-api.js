// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/billing-batch/';
  const provideName = 'BillingBatchApiService';

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

  const generateSummary = async (data) => {
    let apiUrl = apiHost + '/billing/billing-batch/summary';
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
  const generateDocuments = async (id, data) => {
    let apiUrl = apiHost + '/billing/billing-batch/documents/' + id + '/';
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

  const getInvoices = async (batchId) => {
    let apiUrl = apiHost + '/billing/billing-batch/summary?batch_id=' + batchId;
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

  const apiService = {
    getAll,
    getDetail,
    getInvoices,
    generateSummary,
    generateDocuments,
    update
  };

  nuxtApp.provide(provideName, apiService);
});
