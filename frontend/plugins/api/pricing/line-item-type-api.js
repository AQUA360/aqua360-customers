// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/line-item-type/';
    const provideName = 'LineItemTypeApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, br_id = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
  
      if( br_id ) {
        apiUrl += `&billing_range=${br_id}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
    // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
    // background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, br_id = null) => {
      return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, extraParams: { billing_range: br_id } });
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

    const getByBillingRange = async (billingRangeId) => {
      let apiUrl = apiHost + entity + '?billing_range=' + billingRangeId;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const getAllByProduct = async (productId) => {
      let apiUrl = apiHost + entity + 'by-product/?product=' + productId;
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const getStretches = async (id) => {
      let apiUrl = apiHost + entity + id + '/stretches';
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const saveArticle = async (data) => {
      let apiUrl = `${apiHost}/pricing/article-code/save-article/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        if (response) {
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
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const doDelete = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
      try {
        await $apiManager.fetch(apiUrl, 'DELETE');
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      exportData,
      save,
      getDetail,
      getByBillingRange,
      getAllByProduct,
      getStretches,
      saveArticle,
      doDelete
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  