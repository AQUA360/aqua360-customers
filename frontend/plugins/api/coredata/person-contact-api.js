// plugins/services/coredata/person-address-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/person-contact/';
  const provideName = 'PersonContactApiService';

  const config = useRuntimeConfig();
  const {$apiManager} = useNuxtApp()

  const apiHost = config.public.apiHost;
 
  const save = async (data) => {
    const apiUrl = apiHost + entity;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    try {
      const response = await $apiManager.fetch(url, method, JSON.stringify(data));
      return response;
    } catch (error) {
      throw error;
    }
  };
   

  const getAll = async (personId) => {
    const apiUrl = `${apiHost}${entity}?person=${personId}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const remove = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const apiService = { 
    save,
    getAll,
    remove
  };

  nuxtApp.provide(provideName, apiService);
});