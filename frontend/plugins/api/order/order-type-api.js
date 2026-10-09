// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/order/order-type/';
  const provideName = 'OrderTypeApiService';

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

  const createOrderType = async (data) => {
    const apiUrl = `${apiHost}${entity}`;
    const formData = new FormData();
    for (const key in data) {
      if (data[key] != "" && data[key] != null) {
        formData.append(key, data[key]);
      }
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const deleteOrderType = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}`;
    try {
      const response = await $apiManager.fetch(apiUrl,'DELETE');
      return response;
    } 
    catch (error) {
      throw error;
    }
  }

  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = data.id ? 'PUT' : 'POST';
      if(method == 'PUT') {
        apiUrl += data.id + '/';
      }
      console.log(apiUrl, method, data  );
      const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
      if (response) {
        console.log(response)
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } 
    catch (error) {
      throw error;
    }
  }

  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns });
  }

  const apiService = {
    getAll,
    exportData,
    getDetail,
    createOrderType,
    deleteOrderType,
    save
  };

  nuxtApp.provide(provideName, apiService);
});
