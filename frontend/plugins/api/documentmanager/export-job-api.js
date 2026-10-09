// plugins/api/documentmanager/export-job-api.js
// General downloads queue of the logged-in user (backend `ExportJob`). Each
// server-side export creates a job; its file stays reachable from here even if
// the user leaves the page that launched it.
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/documentmanager/export-job/';
  const provideName = 'ExportJobApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async ({ active = false, pageSize = 20 } = {}) => {
    let apiUrl = `${apiHost}${entity}?page_size=${pageSize}`;
    if (active) apiUrl += '&active=true';
    return await $apiManager.fetch(apiUrl, 'GET', null, null, true);
  };

  const getDetail = async (id) => {
    return await $apiManager.fetch(`${apiHost}${entity}${id}/`, 'GET', null, null, true);
  };

  const dismiss = async (id) => {
    return await $apiManager.fetch(`${apiHost}${entity}${id}/`, 'DELETE');
  };

  const cancel = async (id) => {
    return await $apiManager.fetch(`${apiHost}${entity}${id}/cancel/`, 'POST');
  };

  const clearFinished = async () => {
    return await $apiManager.fetch(`${apiHost}${entity}clear-finished/`, 'POST');
  };

  nuxtApp.provide(provideName, { getAll, getDetail, dismiss, cancel, clearFinished });
});
