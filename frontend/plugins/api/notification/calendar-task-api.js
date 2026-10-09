// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/notification/calendar-task/';
    const provideName = 'CalendarTaskApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (year = null, month = null, contract_id = null) => {
      let apiUrl = apiHost + entity;

      if (contract_id) {
        apiUrl += '&contract=' + contract_id;
      } else {
        apiUrl += '?year=' + year + '&month=' + month;
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

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getDayTasks = async(set_date) => {
      let apiUrl = apiHost + entity + '?set_date=' + set_date;

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
  
    const deleteItem = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;

      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        return true;
  
      } catch (error) {
        throw error;
      }
    };
  
    const apiService = {
      getAll,
      getDetail,
      getDayTasks,
      deleteItem,
      save,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  