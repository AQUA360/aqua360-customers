export default defineNuxtPlugin((nuxtApp) => {
  const entity = '/statistics/reading-batch-import-template/';
  const provideName = 'ReadingBatchImportTemplateApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const listUrl = () => `${apiHost}${entity}`;
  const detailUrl = (id) => `${apiHost}${entity}${id}/`;

  /** GET /statistics/reading-batch-import-template/ */
  const getAll = async () => {
    const response = await $apiManager.fetch(listUrl(), 'GET');
    return response;
  };

  /** GET /statistics/reading-batch-import-template/:id/ */
  const getDetail = async (id) => {
    const response = await $apiManager.fetch(detailUrl(id), 'GET');
    return response;
  };

  /** POST /statistics/reading-batch-import-template/ */
  const create = async (data) => {
    const response = await $apiManager.fetch(listUrl(), 'POST', JSON.stringify(data), {
      'Content-Type': 'application/json',
    });
    return response;
  };

  /** PUT /statistics/reading-batch-import-template/:id/ */
  const update = async (data) => {
    const response = await $apiManager.fetch(detailUrl(data.id), 'PUT', JSON.stringify(data), {
      'Content-Type': 'application/json',
    });
    return response;
  };

  /** DELETE /statistics/reading-batch-import-template/:id/ */
  const remove = async (id) => {
    const response = await $apiManager.fetch(detailUrl(id), 'DELETE');
    return response;
  };

  nuxtApp.provide(provideName, {
    getAll,
    getDetail,
    create,
    update,
    remove,
  });
});
