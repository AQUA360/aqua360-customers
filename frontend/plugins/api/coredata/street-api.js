// plugins/services/coredata/street-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/coredata/street/';
    const provideName = 'StreetApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
    
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, city_id = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      // Afegir els filtres a la URL
      let filtersValues = [];
      if (filters.length > 0 ) {
        filters.map( filter => {
          filtersValues.push(filter);
        })
      }

      if( filtersValues.length > 0 ) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }

      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      if( city_id ) {
        apiUrl += `&city=${city_id}`;
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

    // Server-side export (async). Mirrors getAll's search/filters/sort/city but
    // POSTs to `{entity}export/` so the backend builds the full, filter-aware
    // XLSX as a background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, city_id = null, columns = []) => {
      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc, columns,
        extraParams: { city: city_id }
      });
    }

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}`;
  
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

    const getStreetTypes = async () => {
      let apiUrl = apiHost + '/coredata/street-type/'; // + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`

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
    
    const getStreetNumber = async (id, page = 1) => {
      let apiUrl = apiHost + '/coredata/street-number/?street='+id+'&page='+page;

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    };
    
    const patch = async (id, data) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PATCH', data);
        return response;
      } catch (error) {
        throw error;
      }
    }

    const create = async (data) => {
      const apiUrl = `${apiHost}${entity}`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(data));
        return response;
      } catch (error) {
        throw error;
      }
    }

    const getPermissions = async () => {
      const apiUrl = `${apiHost}${entity}permissions/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response;
      } catch (error) {
        throw error;
      }
    }

    const apiService = {
      getAll,
      exportData,
      getStreetTypes,
      getStreetNumber,
      getDetail,
      create,
      patch,
      getPermissions,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  