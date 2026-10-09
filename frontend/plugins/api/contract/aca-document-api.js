// plugins/services/contract/clause-template-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/aca-document/';
  const provideName = 'ACADocumentApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = {}, page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    for(var f in filters ) {
      apiUrl += `&${f}=${filters[f]}`;
    }

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
    try {
      const method = data.id ? 'PUT' : 'POST';
      if( method == 'PUT' ){
        apiUrl += data.id + '/';
      }

      const formData = new FormData();

      // Append all fields from data to formData
      for (const key in data) {
        if (data[key] != "" && data[key] != null) {
          formData.append(key, data[key]);
        }
      }

      const response = await $apiManager.fetch(apiUrl, method, formData)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const validateChange = async (id, validate) => {
    let apiUrl = `${apiHost}/contract/aca-document-change/${id}/`;
    try {
      const data = {
        id: id,
        accepted: validate
      }

      const response = await $apiManager.fetch(apiUrl, 'PUT', data)
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

  const getPermissions = async () => {
    const apiUrl = `${apiHost}${entity}permissions/`;
    try {
      const response = await $apiManager.fetch(apiUrl,'GET')
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    getDetail,
    save,
    doDelete,
    validateChange,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
