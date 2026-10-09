import api from "../api";

export default defineNuxtPlugin(nuxtApp => {
  const entity = '/search/';
  const provideName = 'SearchApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getSearch = async (searchQuery = '', entityFilter = '', page = 1) => {
    let apiUrl = apiHost + entity + 'results/?q=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (entityFilter !== '') {
      apiUrl += `&entity=${entityFilter}`;
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

  const getData = async (search_app, search_entity, search_id) => {
    let apiUrl = apiHost + '/' + search_app + '/' + search_entity + '/' + search_id
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

  const saveSearchHistory = async (searchQuery) => {
    let apiUrl = apiHost + '/search/history/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', searchQuery);
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getSearchHistory = async (searchQuery = '', filters = [], page = 1) => {
    let apiUrl = apiHost + entity + 'history/?q=' + encodeURIComponent(searchQuery) + `&page=${page}`;

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

  const apiService = {
    getSearch,
    getData,
    saveSearchHistory,
    getSearchHistory
  };

  nuxtApp.provide(provideName, apiService);
});
