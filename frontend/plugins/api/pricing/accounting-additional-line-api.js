export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/accounting-additional-line/';
    const provideName = 'AccountingAdditionalLineApiService';

    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (accountingPricingId = null, isActive = true) => {
      let apiUrl = `${apiHost}${entity}?page_size=200`;
      if (accountingPricingId) {
        apiUrl += `&accounting_pricing=${accountingPricingId}`;
      }
      if (isActive !== null && isActive !== undefined) {
        apiUrl += `&is_active=${isActive ? 'true' : 'false'}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response.results) {
          return response;
        }
        if (Array.isArray(response)) {
          return { results: response };
        }
        throw new Error('Error estructura `results` no trobat');
      } catch (error) {
        throw error;
      }
    }

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response) {
          return response;
        }
        throw new Error('Error estructura `results` no trobat');
      } catch (error) {
        throw error;
      }
    }

    const save = async (data) => {
      let apiUrl = `${apiHost}${entity}`;
      try {
        const method = data.id ? 'PUT' : 'POST';
        if (method === 'PUT') {
          apiUrl += `${data.id}/`;
        }
        const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        }
        throw new Error('Error no trobat');
      } catch (error) {
        throw error;
      }
    }

    const doDelete = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/`;
      try {
        await $apiManager.fetch(apiUrl, 'DELETE');
      } catch (error) {
        throw error;
      }
    }

    const apiService = {
      getAll,
      getDetail,
      save,
      doDelete,
    };

    nuxtApp.provide(provideName, apiService);
  });
