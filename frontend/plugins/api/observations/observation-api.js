// plugins/services/service/cluster-api.js
export default defineNuxtPlugin(nuxtApp => {
    const provideName = 'ObservationApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getObservations = async (searchQuery = '', module = '', entity = '', url_entity = '') => {
      let apiUrl = `${apiHost}/${module}/${url_entity}-observation/?${entity}=${encodeURIComponent(searchQuery)}`;
  
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

    const updateObservation = async (data, module = '', entity = '') => {
      const apiUrl = `${apiHost}/${module}/${entity}-observation/${data.id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'PUT',JSON.stringify(data));
        return response;
      } catch (error) {
        throw error;
      }
    }
  
    const postObservation = async (data, module = '', entity = '') => {
      const apiUrl = `${apiHost}/${module}/${entity}-observation/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'POST',JSON.stringify(data));
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const deleteObservation = async (id, module = '', entity = '') => {
      const apiUrl = `${apiHost}/${module}/${entity}-observation/${id}`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'DELETE');
        return response;
      } catch (error) {
        throw error;
      }
    }

    const apiService = {
      getObservations,
      postObservation,
      updateObservation,
      deleteObservation
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  