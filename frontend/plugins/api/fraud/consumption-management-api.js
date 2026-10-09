export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/consumption-management/';
  const provideName = 'ConsumptionManagementApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', type = null, page = 1, sort = null, desc = false, mode = 'current', billingBatch = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (type) {
      apiUrl += `&type=${type}`;
    }

    if (billingBatch) {
      apiUrl += `&billing_batch=${billingBatch}`;
    } else if (mode) {
      apiUrl += `&mode=${mode}`;
    }

    const exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results !== undefined) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  // Server-side XLSX export (async). Mirrors getAll's filters/search/sort but
  // POSTs to `{entity}export/`, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', type = null, sort = null, desc = false, mode = 'current', billingBatch = null, columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');

    return $apiManager.exportTable(entity, {
      searchQuery, sort, desc, columns,
      extraParams: {
        type,
        billing_batch: billingBatch || null,
        mode: billingBatch ? null : mode,
        exploitation: exploitation_id || null,
      }
    });
  };

  const apiService = {
    getAll,
    exportData,
  };

  nuxtApp.provide(provideName, apiService);
});
