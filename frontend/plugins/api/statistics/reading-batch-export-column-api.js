export default defineNuxtPlugin((nuxtApp) => {
  const entity = '/statistics/reading-batch-export-column/';
  const provideName = 'ReadingBatchExportColumnApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const listUrl = () => `${apiHost}${entity}`;
  const detailUrl = (id) => `${apiHost}${entity}${id}/`;
  const syncUrl = () => `${apiHost}${entity}sync/`;
  const clearUrl = () => `${apiHost}${entity}clear/`;

  /** GET /statistics/reading-batch-export-column/ */
  const getAll = async () => {
    const response = await $apiManager.fetch(listUrl(), 'GET');
    return response;
  };

  /** GET /statistics/reading-batch-export-column/:id/ */
  const getDetail = async (id) => {
    const response = await $apiManager.fetch(detailUrl(id), 'GET');
    return response;
  };

  /** POST /statistics/reading-batch-export-column/ */
  const create = async (data) => {
    const response = await $apiManager.fetch(listUrl(), 'POST', JSON.stringify(data), {
      'Content-Type': 'application/json',
    });
    return response;
  };

  /** PUT /statistics/reading-batch-export-column/:id/ */
  const update = async (data) => {
    const response = await $apiManager.fetch(detailUrl(data.id), 'PUT', JSON.stringify(data), {
      'Content-Type': 'application/json',
    });
    return response;
  };

  /** DELETE /statistics/reading-batch-export-column/:id/ */
  const remove = async (id) => {
    const response = await $apiManager.fetch(detailUrl(id), 'DELETE');
    return response;
  };

  /**
   * POST /statistics/reading-batch-export-column/sync/
   * Replaces all rows. Body: JSON array of { name, value, position }, or { columns: [...] }.
   */
  const sync = async (payload) => {
    const response = await $apiManager.fetch(syncUrl(), 'POST', JSON.stringify(payload), {
      'Content-Type': 'application/json',
    });
    return response;
  };

  /** DELETE /statistics/reading-batch-export-column/clear/ */
  const clear = async () => {
    const response = await $apiManager.fetch(clearUrl(), 'DELETE');
    return response;
  };

  nuxtApp.provide(provideName, {
    getAll,
    getDetail,
    create,
    update,
    remove,
    sync,
    clear,
  });
});
