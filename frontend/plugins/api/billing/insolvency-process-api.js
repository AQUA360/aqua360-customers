// plugins/api/billing/insolvency-process-api.js
// Processos d'insolvència d'una persona
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/insolvency-process/';
  const provideName = 'InsolvencyProcessApiService';

  const config = useRuntimeConfig();
  const { $apiManager } = useNuxtApp();
  const apiHost = config.public.apiHost;

  const getAll = async (page = 1, filters = {}) => {
    const params = new URLSearchParams({ page: String(page) });
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') params.append(key, value);
    });
    return await $apiManager.fetch(`${apiHost}${entity}?${params.toString()}`, 'GET');
  };

  const getDetail = async (id) => await $apiManager.fetch(`${apiHost}${entity}${id}/`, 'GET');

  const getPermissions = async () => await $apiManager.fetch(`${apiHost}${entity}permissions/`, 'GET');

  const preview = async (personId, startDate) =>
    await $apiManager.fetch(`${apiHost}${entity}preview/`, 'POST', { person_id: personId, start_date: startDate });

  const create = async (data) => await $apiManager.fetch(`${apiHost}${entity}`, 'POST', data);

  // data: { end_date, restore_payment }
  const close = async (id, data = {}) =>
    await $apiManager.fetch(`${apiHost}${entity}${id}/close/`, 'POST', data);

  const uploadDocument = async (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return await $apiManager.fetch(`${apiHost}${entity}${id}/upload-document/`, 'POST', formData);
  };

  nuxtApp.provide(provideName, { getAll, getDetail, getPermissions, preview, create, close, uploadDocument });
});
