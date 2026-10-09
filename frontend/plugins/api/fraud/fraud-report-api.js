// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/fraud/fraud-report/';
  const provideName = 'FraudReportApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      })
    }

    if (filtersValues.length > 0) {
      apiUrl += `&status=${filtersValues.join(',')}`;
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

  const getFraudReports = async (fraud_id) => {
    const apiUrl = `${apiHost}${entity}?fraud=${fraud_id}`;

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

  const saveDocument = async (data) => {
    let apiUrl = `${apiHost}/fraud/fraud-documentation/`;
    try {

      let options;
      const formData = new FormData();
      formData.append('id', data.id);
      formData.append('file', data.file);

      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'POST', options)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }

  }
  
  const saveImage = async (data) => {
    let apiUrl = `${apiHost}/fraud/fraud-image/`;
    try {

      let options;
      const formData = new FormData();
      formData.append('id', data.id);
      formData.append('file', data.file);

      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'POST', options)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }

  }

  const deleteItem = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return true;

    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getAll,
    getFraudReports,
    getDetail,
    save,
    saveDocument,
    saveImage,
    deleteItem,
  };

  nuxtApp.provide(provideName, apiService);
});
