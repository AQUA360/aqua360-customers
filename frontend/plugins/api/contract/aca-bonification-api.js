// plugins/api/contract/aca-bonification-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/aca-bonification-request/';
  const provideName = 'ACABonificationApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getPending = async () => {
    const apiUrl = `${apiHost}${entity}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const update = async (id, data) => {
    const apiUrl = `${apiHost}${entity}${id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PATCH', data)
      return response;
    } catch (error) {
      throw error;
    }
  }

  const previewExport = async (ids) => {
    const apiUrl = `${apiHost}${entity}preview-export/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { ids })
      return response;
    } catch (error) {
      throw error;
    }
  }

  const generateExport = async (ids) => {
    const apiUrl = `${apiHost}${entity}generate-export/`;
    const authToken = localStorage.getItem('auth_token') || '';
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ ids })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Error generant el fitxer');
    }

    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename=([^;]+)/);
    const filename = match ? match[1].trim() : 'ampliacio_trams.txt';

    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(blobUrl), 250);
  }

  const apiService = {
    getPending,
    update,
    previewExport,
    generateExport
  };

  nuxtApp.provide(provideName, apiService);
});
