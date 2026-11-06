export default defineNuxtPlugin(nuxtApp => {
  const entity = '/send-batch/batch/';
  const provideName = 'SendBatchApiService';

  const { $apiManager } = useNuxtApp();
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAllBatches = async (
    searchQuery = '', page = 1,
    sort = null, desc = false,
  ) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response;
      }
      throw new Error('Error estructura `results` no trobat');
    } catch (error) {
      throw error;
    }
  };

  const getBatchDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error estructura no trobada');
    } catch (error) {
      throw error;
    }
  };

  const getBatchItems = async (id, searchQuery = '', page = 1) => {
    let apiUrl = `${apiHost}${entity}${id}/items/?page=${page}`;
    if (searchQuery) {
      apiUrl += `&search=${encodeURIComponent(searchQuery)}`;
    }
    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  };

  const getBatchErrors = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/errors/`;
    try {
      return await $apiManager.fetch(apiUrl, 'GET');
    } catch (error) {
      throw error;
    }
  };

  const resendErrors = async (id, aquaIds, send = true) => {
    const apiUrl = `${apiHost}${entity}${id}/resend-errors/`;
    try {
      return await $apiManager.fetch(
        apiUrl,
        'POST',
        JSON.stringify({ aqua_ids: aquaIds, send }),
        { 'Content-Type': 'application/json' },
      );
    } catch (error) {
      throw error;
    }
  };

  const previewPayload = async (id, aquaIds) => {
    const apiUrl = `${apiHost}${entity}${id}/preview-payload/`;
    try {
      return await $apiManager.fetch(
        apiUrl,
        'POST',
        JSON.stringify({ aqua_ids: aquaIds }),
        { 'Content-Type': 'application/json' },
      );
    } catch (error) {
      throw error;
    }
  };

  const retrySend = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/retry-send/`;
    try {
      return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify({}), {
        'Content-Type': 'application/json',
      });
    } catch (error) {
      throw error;
    }
  };

  const checkStatus = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/check-status/`;
    try {
      return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify({}), {
        'Content-Type': 'application/json',
      });
    } catch (error) {
      throw error;
    }
  };

  const getPermissions = async () => {
    const apiUrl = `${apiHost}${entity}permissions/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const settingsBase = `${apiHost}/send-batch/`;

  const getSettings = async () => {
    return $apiManager.fetch(`${settingsBase}settings/`, 'GET');
  };

  const ensureDefaults = async () => {
    return $apiManager.fetch(`${settingsBase}settings/`, 'POST', JSON.stringify({}), {
      'Content-Type': 'application/json',
    });
  };

  const listProviders = async () => {
    return $apiManager.fetch(`${settingsBase}provider/`, 'GET');
  };

  const createProvider = async (payload) => {
    return $apiManager.fetch(
      `${settingsBase}provider/`,
      'POST',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  const updateProvider = async (id, payload) => {
    return $apiManager.fetch(
      `${settingsBase}provider/${id}/`,
      'PATCH',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  const listTypes = async () => {
    return $apiManager.fetch(`${settingsBase}type/`, 'GET');
  };

  const createType = async (payload) => {
    return $apiManager.fetch(
      `${settingsBase}type/`,
      'POST',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  const updateType = async (id, payload) => {
    return $apiManager.fetch(
      `${settingsBase}type/${id}/`,
      'PATCH',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  const listStatuses = async () => {
    return $apiManager.fetch(`${settingsBase}status/`, 'GET');
  };

  const createStatus = async (payload) => {
    return $apiManager.fetch(
      `${settingsBase}status/`,
      'POST',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  const updateStatus = async (id, payload) => {
    return $apiManager.fetch(
      `${settingsBase}status/${id}/`,
      'PATCH',
      JSON.stringify(payload),
      { 'Content-Type': 'application/json' },
    );
  };

  nuxtApp.provide(provideName, {
    getAllBatches,
    getBatchDetail,
    getBatchItems,
    getBatchErrors,
    resendErrors,
    previewPayload,
    retrySend,
    checkStatus,
    getPermissions,
    getSettings,
    ensureDefaults,
    listProviders,
    createProvider,
    updateProvider,
    listTypes,
    createType,
    updateType,
    listStatuses,
    createStatus,
    updateStatus,
  });
});
