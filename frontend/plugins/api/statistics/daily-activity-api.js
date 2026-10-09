export default defineNuxtPlugin((nuxtApp) => {
  const provideName = 'DailyActivityApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  /**
   * Resum d'activitat d'un usuari (o de diversos) entre dues dates.
   *
   * Sense `userIds`, el backend retorna l'activitat de l'usuari de la sessió; amb
   * `'all'` o amb ids d'altres usuaris, cal permís de veure usuaris (si no, 403).
   * Sense dates, el dia d'avui. `includeDetails: false` estalvia la cronologia i és
   * el que fa servir el widget del dashboard, que només pinta els comptadors.
   */
  const getSummary = async ({ dateFrom = null, dateTo = null, userIds = null, includeDetails = true, timelineLimit = null } = {}) => {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (userIds !== null && userIds !== undefined && userIds !== '') {
      params.append('user_ids', Array.isArray(userIds) ? userIds.join(',') : userIds);
    }
    if (!includeDetails) params.append('include_details', 'false');
    if (timelineLimit) params.append('timeline_limit', timelineLimit);

    const query = params.toString();
    const apiUrl = `${apiHost}/statistics/daily-activity-summary${query ? `?${query}` : ''}`;
    return await $apiManager.fetch(apiUrl, 'GET');
  };

  /** Encola l'Excel del resum i retorna `{ task_id }`, com la resta d'informes. */
  const generateReport = async (payload) => {
    const apiUrl = `${apiHost}/statistics/billing/daily-activity-summary`;
    return await $apiManager.fetch(apiUrl, 'POST', payload, { 'Content-Type': 'application/json' });
  };

  nuxtApp.provide(provideName, {
    getSummary,
    generateReport,
  });
});
