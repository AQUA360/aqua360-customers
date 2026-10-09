// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/notification/notification/';
    const provideName = 'NotificationApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, is_seen = null, is_archived = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      if (is_seen != null) {
        apiUrl += `&is_seen=${is_seen}`;
      }
      if (is_archived != null) {
        apiUrl += `&is_archived=${is_archived}`;
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

    const checkNewNotifications = async () => {
      let apiUrl = apiHost + entity + '?is_seen=false&is_active=true';
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response.results) {
          return response.count;
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
  
    const deleteItem = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;

      /* TODO: INSTEAD OF DELETING, SET IT TO EITHE ACTIVATE FALSE OR ADD ARCHIVE */ 
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        return true;
  
      } catch (error) {
        throw error;
      }
    };
  
    const apiService = {
      getAll,
      checkNewNotifications,
      deleteItem,
      save,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  