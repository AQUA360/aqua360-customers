// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/config-project/';
  const provideName = 'ConfigProjectApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (filter_token) => {
    let apiUrl = apiHost + entity;

    if (filter_token) {
      apiUrl += `?token=${filter_token}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (Array.isArray(response)) { // verificar que la resposta sigui un array
        // guardar els valors en el local storage
        response.forEach((value) => {
          const localStorageKey = `config_${value.token}`;
          // console.log('localStorage', localStorageKey, JSON.stringify(value.value));
          localStorage.setItem(localStorageKey, JSON.stringify(value.value));
        });

        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }

    } catch (error) {
      throw error;
    }
  }


  const get = async (key) => {
    // Abans de cridar a la API, comprovar que aquesta key no existeixi en el local storage de config-project
    const localStorageKey = key.startsWith('config') ? key : `config_${key}`;
    const cachedValue = localStorage.getItem(localStorageKey);
    if (cachedValue) {
      // console.log('charged from cache', localStorageKey, cachedValue);
      return JSON.parse(cachedValue);
    }

    const token = localStorageKey.replace(/^config_/, ''); // treure `config_` inicial de la key
    let apiUrl = apiHost + entity + token + `/value/`;

    try {

      const response = await $apiManager.fetch(apiUrl, 'GET')

      if ('value' in response) {
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

  const bulkUpdateValues = async (items) => {
    const apiUrl = apiHost + entity + 'bulk-update-values/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', items, { 'Content-Type': 'application/json' });

      if (Array.isArray(items)) {
        items.forEach((item) => {
          localStorage.setItem(`config_${item.token}`, JSON.stringify(item.value));
        });
      }

      return response;
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getAll,
    get,
    bulkUpdateValues,
  };

  nuxtApp.provide(provideName, apiService);
});
