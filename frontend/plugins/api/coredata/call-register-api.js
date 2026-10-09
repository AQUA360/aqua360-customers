// plugins/services/coredata/call-register-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/coredata/call-register/';
    const provideName = 'CallRegisterApiService';
  
    const config = useRuntimeConfig();
    const { $apiManager } = useNuxtApp();
  
    const apiHost = config.public.apiHost;
  
    const getAll = async (
      searchQuery = '',
      page = 1,
      contract_id = null,
      person_id = null
    ) => {
      let apiUrl =
        apiHost +
        entity +
        '?search=' +
        encodeURIComponent(searchQuery) +
        `&page=${page}`;
  
      if (contract_id) {
        apiUrl += `&contract=${contract_id}`;
      }
  
      if (person_id) {
        apiUrl += `&person=${person_id}`;
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
  
    const getDetail = async (id) => {
      const apiUrl = apiHost + entity + id + '/';
      try {
        return await $apiManager.fetch(apiUrl, 'GET');
      } catch (error) {
        throw error;
      }
    };

    const save = async (data) => {
      let apiUrl = apiHost + entity;
      const method = data.id ? 'PUT' : 'POST';
      if (method === 'PUT') {
        apiUrl += data.id + '/';
      }
      try {
        const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    };

    const apiService = {
      getAll,
      getDetail,
      save
    };
  
    nuxtApp.provide(provideName, apiService);
  });