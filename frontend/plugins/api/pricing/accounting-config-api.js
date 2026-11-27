// plugins/api/pricing/accounting-config-api.js
export default defineNuxtPlugin((nuxtApp) => {
  const entity = '/pricing/accounting-config/';
  const provideName = 'AccountingConfigApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const resolveExploitationId = (exploitation = null) => {
    if (exploitation !== null && exploitation !== undefined && exploitation !== '') {
      return exploitation;
    }
    try {
      return localStorage.getItem('exploitation') || null;
    } catch (error) {
      return null;
    }
  };

  const withExploitationQuery = (url, exploitation = null) => {
    const exploitationId = resolveExploitationId(exploitation);
    if (!exploitationId) return url;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}exploitation=${encodeURIComponent(exploitationId)}`;
  };

  const getCurrent = async (exploitation = null) => {
    const apiUrl = withExploitationQuery(`${apiHost}${entity}current/`, exploitation);
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error estructura no trobat');
    } catch (error) {
      throw error;
    }
  };

  const saveCurrent = async (data, exploitation = null) => {
    const exploitationId = resolveExploitationId(
      exploitation ?? data?.exploitation_id ?? data?.exploitation,
    );
    const payload = { ...data };
    if (exploitationId && payload.exploitation_id == null) {
      payload.exploitation_id = exploitationId;
    }
    const apiUrl = withExploitationQuery(`${apiHost}${entity}current/`, exploitationId);
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', payload, {
        'Content-Type': 'application/json',
      });
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getCurrent,
    saveCurrent,
  };

  nuxtApp.provide(provideName, apiService);
});
