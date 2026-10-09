// plugins/services/contract/bonification-documentation-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/person-bank-sepa-documentation/';
  const provideName = 'SepaDocumentationApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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
    const method = data.id ? 'PUT' : 'POST';

    if (method === 'PUT') {
      apiUrl += `${data.id}/`;
    }

    try {
      let options;
      const formData = new FormData();
      formData.append('checked', data.checked);
      formData.append('file', data.file);
      formData.append('person_bank', data.person_bank_id)
      formData.append('service', data.service)

      options = formData;
      const response = await $apiManager.fetch(apiUrl, method, options);

      if (response) {
        return response;
      } else {
        throw new Error('Error: response not found');
      }
    } catch (error) {
      throw error;
    }
  };

  const generateDocument = async (id, body) => {
    const apiUrl = `${apiHost}/coredata/sepa/download/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', body, {'Content-Type': 'application/json'})
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
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
    generateDocument,
  };

  nuxtApp.provide(provideName, apiService);
});
