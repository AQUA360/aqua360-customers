// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/pricing/product/';
    const provideName = 'ProductApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, price_rate_id = null, exclude_origin_tokens = [], unpaginated = false, exploitation = null, full_serializer = false) => {
      let apiUrl = apiHost + entity + (unpaginated ? 'all/' : '') + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
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

      if( price_rate_id ) {
        apiUrl += `&price_rates=${price_rate_id}`;
      }

      if( exclude_origin_tokens && exclude_origin_tokens.length > 0) {
        apiUrl += `&exclude_origin_token=${exclude_origin_tokens.join(',')}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation) exploitation_id = exploitation;
      if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`; 
      }

      if (full_serializer) {
        apiUrl += `&full_serializer=true`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (unpaginated ? response : response.results) {
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
    
    const getList = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
      let apiUrl = `${apiHost}${entity}list/?search=${encodeURIComponent(searchQuery)}&page=${page}`;
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
      if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`; 
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
  
    // Server-side export (async). Mirrors getList's search/filters/sort but POSTs
    // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
    // background task, returning `{ task_id }`. Same args as getList (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
      let exploitation_id = localStorage.getItem('exploitation');

      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc, columns,
        extraParams: { exploitation: exploitation_id || null }
      });
    };

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

    const getProductsPriority = async (exploitation_id = null) => {
      let apiUrl = `${apiHost}${entity}priority/`;
      if (exploitation_id) {
        apiUrl += `?exploitation=${exploitation_id}`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
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

    const getOrigins = async () => {
      const apiUrl = `${apiHost}/pricing/product-origin/`;

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
      } catch (error) {
        throw error;
      }
    };

    const getPermissions = async () => {
      const apiUrl = `${apiHost}${entity}permissions/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'GET')
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
      save,
      getDetail,
      getList,
      exportData,
      deleteItem,
      getOrigins,
      getProductsPriority,
      getPermissions
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  