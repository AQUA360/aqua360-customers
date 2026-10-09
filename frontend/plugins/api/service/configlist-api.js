// plugins/services/service/configlist-api.js
export default defineNuxtPlugin(nuxtApp => {
  
  const provideName = 'ConfiglistApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (entity, page = 1, searchQuery = '') => {
    let apiUrl = apiHost + '/' + entity + '?ordering=position';
    if (page) {
      apiUrl += '&page=' + page;
    }
    if (searchQuery) {
      apiUrl += '&search=' + searchQuery;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }
  
  const getData = async (entity) => {
    let apiUrl = apiHost + '/' + entity;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    getData
  }

  nuxtApp.provide(provideName, apiService);
});
