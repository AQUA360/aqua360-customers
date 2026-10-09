import apiManager from "../api-manager";

// plugins/services/service/cluster-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/cluster/';
    const provideName = 'ClusterApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    
    const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, connection_id = null, search_by_address = '') => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      if (connection_id) {
        apiUrl += `&connection=${connection_id}`;
      }

      if (search_by_address) {
        apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
      }

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

      let exploitation_id = localStorage.getItem('exploitation');
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
  
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, connection_id = null, search_by_address = '', columns = []) => {
      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc, columns,
        extraParams: { connection: connection_id, search_by_address }
      });
    }

    const getFilterStatus = async () => {
      const apiUrl = apiHost + '/service/cluster-status/';
  
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
  
    const getNozzles = async (cluster_id, page = 1) => {
      const apiUrl = `${apiHost}/service/cluster-nozzle/?cluster=${cluster_id}&page=${page}`;
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
    }
    
    const save = async ( data ) => {
      const apiUrl = `${apiHost}${entity}`;

      const is_created = data.id ? false : true;
      const method = is_created ? 'POST' : 'PUT';
      const id = data.id ? data.id : '';
      const url = is_created ? apiUrl : `${apiUrl}${id}/`;

      // Create a FormData object
      const formData = new FormData();


      // Append all fields from data to formData
      for (const key in data) {
        if (data[key] != "" && data[key] != null) {
          formData.append(key, data[key]);
        }
      }

      try {
        const response = await $apiManager.fetch(url, method, formData);
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const deleteCluster = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'DELETE');
        return response;
      } catch (error) {
        throw error;
      }
    }

    const saveFile = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/save-file/`;
      try {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('id', data.id);
        formData.append('cluster_type', data.cluster_type || '');
        const response = await $apiManager.fetch(apiUrl, 'PUT', formData);
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
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
      exportData,
      getFilterStatus,
      getDetail,
      getNozzles,
      save,
      saveFile,
      deleteCluster,
      getPermissions
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  