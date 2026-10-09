// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/cnae/';
  const provideName = 'CnaeApiService';

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


  const get = async (localStorageKey) => {
    // Abans de cridar a la API, comprovar que aquesta key no existeixi en el local storage de config-project
    const cachedValue = localStorage.getItem(localStorageKey);
    if (cachedValue) {
      return JSON.parse(cachedValue);
    }

    const token = localStorageKey.replace(/^config_/, ''); // treure `config_` inicial de la key
    let apiUrl = apiHost + entity + token + `/value`;

    try {

      const response = await $apiManager.fetch(apiUrl, 'GET')

      if (response.value) {
        // Guardar el valor en el local storage
        localStorage.setItem(localStorageKey, JSON.stringify(response.value));
        return response.value;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    get
  };

  nuxtApp.provide(provideName, apiService);
});
