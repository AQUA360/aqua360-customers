// plugins/api/dashboard/dashboard-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/dashboard/';
  const provideName = 'DashboardApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  /** Disposició de la pàgina d'inici de l'usuari: `{ layout, is_default }`. */
  const getLayout = async () => {
    return await $apiManager.fetch(`${apiHost}${entity}layout/`, 'GET');
  };

  /** Persist the current user dashboard layout as JSON. */
  const saveLayout = async (layout) => {
    return await $apiManager.fetch(`${apiHost}${entity}layout/`, 'PUT', { layout }, { 'Content-Type': 'application/json' });
  };

  /** Torna a la disposició per defecte. */
  const resetLayout = async () => {
    return await $apiManager.fetch(`${apiHost}${entity}layout/`, 'DELETE');
  };

  /** Catàleg de cards que l'usuari pot afegir (ja filtrat per permisos). */
  const getCards = async () => {
    return await $apiManager.fetch(`${apiHost}${entity}cards/`, 'GET');
  };

  /** Dades d'una card; la configuració va com a paràmetres de la URL. */
  const getCardData = async (key, cardConfig = {}) => {
    const params = new URLSearchParams();
    Object.entries(cardConfig || {}).forEach(([name, value]) => {
      if (value !== null && value !== undefined) params.append(name, value);
    });
    const query = params.toString();
    return await $apiManager.fetch(`${apiHost}${entity}cards/${key}/data/${query ? `?${query}` : ''}`, 'GET', null, null, true);
  };

  nuxtApp.provide(provideName, {
    getLayout,
    saveLayout,
    resetLayout,
    getCards,
    getCardData,
  });
});
