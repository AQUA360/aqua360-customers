// plugins/services/contract/bail-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/statistics/daily-document/';
    const provideName = 'DailyDocumentApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }

      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`;
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

    const checkNewDailyDocuments = async () => {
      const apiUrl = `${apiHost}${entity}pending/`;
      try {
        return await $apiManager.fetch(apiUrl, 'GET');
      } catch (error) {
        throw error;
      }
    }

    const regenerate = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/regenerate/`;
      try {
        return await $apiManager.fetch(apiUrl, 'GET');
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      getDetail,
      save,
      doDelete,
      checkNewDailyDocuments,
      regenerate,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  