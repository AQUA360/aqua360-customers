// plugins/api/coredata/db-sync-api.js
// Sincronització nocturna de dades prod → test: activar/desactivar (test/staging/local, admins).
// Els errors no mostren toast: el component els tradueix a partir del `code`.
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/db-sync/';
  const provideName = 'DbSyncApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getStatus = async () => $apiManager.fetch(apiHost + entity, 'GET', null, null, true);

  const setNightlyEnabled = async (enabled) =>
    $apiManager.fetch(apiHost + entity, 'PATCH', { nightly_enabled: enabled }, null, true);

  nuxtApp.provide(provideName, {
    getStatus,
    setNightlyEnabled,
  });
});
