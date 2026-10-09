// plugins/services/contract/bail-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/accounting-pricing/';
    const provideName = 'AccountingPricingApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (
      searchQuery = '', page = 1, sort = null, desc = false,
      groupedList = false,
      category = null, exploitation = null, add_taxes = null, add_subtotals = null,
      pageSize = 50,
    ) => {
      let apiUrl = apiHost + entity + `${groupedList ? 'grouped/' : ''}?search=` + encodeURIComponent(searchQuery) + `&page=${page}&page_size=${pageSize}`;
      
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      if (category) {
        apiUrl += `&category=${category}`;
      }

      if (add_taxes) {
        apiUrl += `&add_taxes=${add_taxes}`;
      }

      if (add_subtotals) {
        apiUrl += `&add_subtotals=${add_subtotals}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation) {
        exploitation_id = exploitation;
      }

      if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`;
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

    const bulkSave = async (data) => {
      let apiUrl = `${apiHost}${entity}bulk-save/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
  
    }

    const findExisting = async (data) => {
      const apiUrl = `${apiHost}${entity}find-existing/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    
    const doDelete = async (data ) => {
      const apiUrl = `${apiHost}${entity}${data.id}/`;
      try {
        await $apiManager.fetch(apiUrl, 'DELETE');
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      getDetail,
      save,
      doDelete,
      bulkSave,
      findExisting,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
