// plugins/services/service/supply-cut-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/supply-cut/';
    const provideName = 'SupplyCutApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, exploitation_id = null, supply_point_id = null, search_by_address = '') => {
      let apiUrl = apiHost + entity + 'list/?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      /* if (exploitation_id) {
        apiUrl += `&exploitation=${exploitation_id}`;
      } */

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

      if( supply_point_id ) {
        apiUrl += `&supply_point=${supply_point_id}`;
      }

      if (search_by_address) {
        apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
      }

      let exploitation_local_id = localStorage.getItem('exploitation');
      if (exploitation_local_id) {
        apiUrl += `&exploitation=${exploitation_local_id}`; 
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
      const apiUrl = apiHost + '/service/supply-cut-status/';
  
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

    const removeSupplyPoint = async (id, supply_point_id, observation = null) => {
      const apiUrl = `${apiHost}${entity}${id}/remove-supply-point/`;
      const payload = { supply_point: supply_point_id };
      if (observation) payload.observation = observation;

      try {
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(payload), { 'Content-Type': 'application/json' });
      } catch (error) {
        throw error;
      }
    }

    const startCut = async (id, observation = null) => {
      const apiUrl = `${apiHost}${entity}${id}/start-cut/`;
      const payload = {};
      if (observation) payload.observation = observation;
      try {
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(payload), { 'Content-Type': 'application/json' });
      } catch (error) {
        throw error;
      }
    }

    const finishCut = async (id, observation = null) => {
      const apiUrl = `${apiHost}${entity}${id}/finish-cut/`;
      const payload = {};
      if (observation) payload.observation = observation;
      try {
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(payload), { 'Content-Type': 'application/json' });
      } catch (error) {
        throw error;
      }
    }

    const resolveReview = async (id, status, observation = null, extra = {}) => {
      const apiUrl = `${apiHost}${entity}${id}/resolve-review/`;
      const payload = { status, ...extra };
      if (observation) payload.observation = observation;
      try {
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(payload), { 'Content-Type': 'application/json' });
      } catch (error) {
        throw error;
      }
    }

    const getCauses = async () => {
      const apiUrl = `${apiHost}/service/supply-cut-cause/`;

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
      getData,
      getFilterStatus,
      getDetail,
      save,
      removeSupplyPoint,
      getCauses,
      getPermissions,
      startCut,
      finishCut,
      resolveReview
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  