export default defineNuxtPlugin(nuxtApp => {
  const entity = '/statistics/billing/';
  const provideName = 'ReportsApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + '/statistics/general-report/' + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

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

  const getBillingActiveProducts = async (id) => {
    let apiUrl = apiHost + entity + id + '/active-products';
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
    const apiUrl = `${apiHost}/statistics/general-report/permissions/`;
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

  const getActiveReports = async () => {
    const apiUrl = `${apiHost}/statistics/available-reports/active-list/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const triggerReport = async (reportId, data) => {
    const apiUrl = `${apiHost}/statistics/available-reports/${reportId}/trigger/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data);
      if (response) {
        return response;
      } else {
        throw new Error('Error triggering report');
      }
    } catch (error) {
      throw error;
    }
  }

  const getIndividualReport = async (reportDir, data) => {
    const apiUrl = `${apiHost}${entity}${reportDir}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data);
      if (response) {
        return response;
      } else {
        throw new Error('Error getting individual report');
      }
    } catch (error) {
      throw error;
    }
  }

  const getReportsQueue = async () => {
    let apiUrl = `${apiHost}/statistics/report-queue/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getReportsQueueItem = async (queueItemId) => {
    const apiUrl = `${apiHost}/statistics/report-queue/${queueItemId}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  /** action: 'kill' | 'skip' | 'restart' */
  const sendReportsQueueAction = async (queueItemId, action) => {
    const apiUrl = `${apiHost}/statistics/report-queue/${queueItemId}/action/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { action }, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    getBillingActiveProducts,
    getPermissions,
    getActiveReports,
    getIndividualReport,
    triggerReport,
    getReportsQueue,
    getReportsQueueItem,
    sendReportsQueueAction
  };

  nuxtApp.provide(provideName, apiService);
});
