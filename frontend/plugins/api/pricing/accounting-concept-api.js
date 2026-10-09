// plugins/services/pricing/accounting-concept-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/accounting-concept/';
    const provideName = 'AccountingConceptApiService';

    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (searchQuery = '', page = 1, sort = null, desc = false, category = null, exploitation = null, add_taxes = null, add_subtotals = null) => {

      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      if (category) {
        apiUrl += `&category=${category}`;
      }
      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation) exploitation_id = exploitation;
      if (exploitation_id) apiUrl += `&exploitation=${exploitation_id}`;

      if (add_taxes) {
        apiUrl += `&add_taxes=${add_taxes}`;
      }

      if (add_subtotals) {
        apiUrl += `&add_subtotals=${add_subtotals}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')

        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
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
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const save = async (data) => {
      let apiUrl = `${apiHost}${entity}`;
      try {
        const method = data.id ? 'PUT' : 'POST';
        if (method == 'PUT') {
          apiUrl += data.id + '/';
        }
        const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }

    }


    const doDelete = async (data ) => {
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
