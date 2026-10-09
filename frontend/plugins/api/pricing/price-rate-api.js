// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/pricing/price-rate/';
  const provideName = 'PriceRateApiService';

  const {$apiManager} = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, product_id = null, origin = null, unpaginated = false, exploitation_search_id = null) => {
    let apiUrl = apiHost + entity + (unpaginated? 'all/' : '') + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      })
    }

    if (filtersValues.length > 0) {
      apiUrl += `&product=${filtersValues.join(',')}`;
    }

    if( sort ) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if(product_id) {
      apiUrl += `&product=${product_id}`;
    }

    if(origin) {
      apiUrl += `&origin=${origin.join(',')}`;
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_search_id) {
      exploitation_id = exploitation_search_id;
    }
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`; 
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
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, product_id = null, origin = null, exploitation_search_id = null, columns = []) => {
    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_search_id) {
      exploitation_id = exploitation_search_id;
    }

    return $apiManager.exportTable(entity, {
      searchQuery, sort, desc,
      columns,
      extraParams: {
        product: product_id || filters,
        origin,
        exploitation: exploitation_id || null,
      }
    });
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

  const getFilterProducts = async () => {
    const apiUrl = apiHost + '/pricing/product/';

    try {
      const response = await $apiManager.fetch(apiUrl,'GET')
      if (response.results) {
        return response.results;
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
    exportData,
    save,
    getDetail,
    getFilterProducts,
    getPermissions
  }

  nuxtApp.provide(provideName, apiService);
});
