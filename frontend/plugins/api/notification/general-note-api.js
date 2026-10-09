// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/notification/general-note/';
    const provideName = 'GeneralNoteApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', page = 1) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
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

    const setAllToRead = async () => {
      let apiUrl = `${apiHost}${entity}read/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
  
    }

    let unseenInFlight = null;
    const checkNewGeneralNotes = async () => {
      if (!unseenInFlight) {
        unseenInFlight = (async () => {
          try {
            const response = await $apiManager.fetch(apiHost + entity + '?is_seen=false', 'GET');
            if (response.results) {
              return response.count;
            } else {
              throw new Error('Error estructura `results` no trobat');
            }
          } finally {
            unseenInFlight = null;
          }
        })();
      }
      return unseenInFlight;
    }

    let unseenResultsInFlight = null;
    const getUnseen = async () => {
      if (!unseenResultsInFlight) {
        unseenResultsInFlight = (async () => {
          try {
            const response = await $apiManager.fetch(apiHost + entity + '?is_seen=false', 'GET');
            if (response.results) {
              return response.results;
            } else {
              throw new Error('Error estructura `results` no trobat');
            }
          } finally {
            unseenResultsInFlight = null;
          }
        })();
      }
      return unseenResultsInFlight;
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
      deleteItem,
      save,
      setAllToRead,
      checkNewGeneralNotes,
      getUnseen,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  