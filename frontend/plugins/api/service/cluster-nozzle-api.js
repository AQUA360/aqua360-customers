// plugins/services/service/cluster-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/cluster-nozzle/';
    const provideName = 'ClusterNozzleApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    
    const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
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
    
    const getFilterStatus = async () => {
      const apiUrl = apiHost + '/service/cluster-nozzle-status/';
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response.results) {
          return response.results;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    };
    
    const getNozzleType = async () => {
      const apiUrl = apiHost + '/service/cluster-nozzle-type/';
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response.results) {
          return response.results;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    };
  
    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
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
    
    const save = async ( data ) => {
      const apiUrl = `${apiHost}${entity}`;

      const is_created = data.id ? false : true;
      const method = is_created ? 'POST' : 'PUT';
      const id = data.id ? data.id : '';
      const url = is_created ? apiUrl : `${apiUrl}${id}/`;
      
      try {
        const response = await $apiManager.fetch(url, method, JSON.stringify(data), { 'Content-Type': 'application/json' } );
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const doDelete = async (data ) => {
      const apiUrl = `${apiHost}${entity}${data.id}/`;
      return await $apiManager.fetch(apiUrl, 'DELETE');
    }

    const apiService = {
      getData,
      getFilterStatus,
      getDetail,
      save,
      doDelete,
      getNozzleType
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  