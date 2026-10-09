// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/config-aca/';
    const provideName = 'ConfigAcaApiService';
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getDetail = async (id) => {
      const apiUrl = apiHost + entity + id + '/';
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
      } catch (error) {
        throw error;
      }
    };
    
    const getAll = async (exploitation = null, page = 1) => {
      let apiUrl = apiHost + entity + `?page=${page}`;

      if (exploitation) {
        apiUrl += `&exploitation=${exploitation}`;
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
    };

    const getAllUnpaginated = async (exploitation = null) => {
      let apiUrl = apiHost + entity + 'all/';

      if (exploitation) {
        apiUrl += `?exploitation=${exploitation}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
      } catch (error) {
        throw error;
      }
    };

    const updateConfigs = async (data) => {
      let apiUrl = apiHost + entity + 'update-configs/';

      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        return response;
      } catch (error) {
        throw error;
      }
    };

    const reRunUpdateConfig = async () => {
      // THIS PETITION IS USED TO UPDATE CONFIG TO DEFAULT
      let apiUrl = apiHost + entity + 'update/';
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST');
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
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
  
    const apiService = {
      getAll,
      getAllUnpaginated,
      getDetail,
      updateConfigs,
      reRunUpdateConfig,
      save,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  