
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/order/order/';
    const provideName = 'OrderApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false,
      operatorId = null, type_ids = [], contract_id = null, contract_request_id = null, connection_request_id = null,
      incident_id = null, search_all_address = '', search_by_address = '', related_contract_token = null, creator_ids = [], city_ids = [],
      supply_point_ids = []) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      if (search_all_address) {
        apiUrl += `&search_all_address=${encodeURIComponent(search_all_address)}`;
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
      
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
  
      if (operatorId) {
        apiUrl += `&operators=${operatorId}`;
      }

      if (type_ids?.length > 0) {
        apiUrl += `&type=${type_ids.join(',')}`;
      }

      if (contract_id) {
        apiUrl += `&contract=${contract_id}`;
      }

      if (supply_point_ids?.length > 0) {
        apiUrl += `&supply_point_ids=${supply_point_ids.join(',')}`;
      }

      if (contract_request_id) {
        apiUrl += `&contract_request=${contract_request_id}`;
      }

      if (connection_request_id) {
        apiUrl += `&connection_request=${connection_request_id}`;
      }

      if (incident_id) {
        apiUrl += `&incident=${incident_id}`;
      }

      if (related_contract_token) {
        apiUrl += `&related_contract_token=${encodeURIComponent(related_contract_token)}`;
      }
      
      if (creator_ids?.length > 0) {
        apiUrl += `&created_by=${creator_ids.join(',')}`;
      }

      if (city_ids?.length > 0) {
        apiUrl += `&city=${city_ids.join(',')}`;
      }

      let exploitation_id = localStorage.getItem('exploitation');
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
  
    const getFilterStatus = async () => {
      const apiUrl = apiHost + '/order/order-status/';
  
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

    const getFilterCities = async () => {
      const apiUrl = apiHost + entity + 'filter-cities/';

      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response;
      } catch (error) {
        throw error;
      }
    }

    const getFilterConnection = async(id) =>{
      const apiUrl = apiHost + entity + '?connection=' + id;

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

    const getFilterConnectionRequest = async(id) =>{
      const apiUrl = apiHost + entity + '?connection_request=' + id;

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

    const getFilterContractTermination = async(id) =>{
      const apiUrl = apiHost + entity + '?contract_termination_request=' + id;

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
    
    const getOrderByToken = async (token) => {
      const apiUrl = `${apiHost}${entity}by-token/${token}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response
      }
      catch (error) {
        throw error
      }
    }

    const getReports = async (id) => {
      const apiUrl = `${apiHost}/order/order-report/?order=${id}`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response
      }
      catch (error) {
        throw error
      }
    }

    const getReportDetail = async (id) => {
      const apiUrl = `${apiHost}/order/order-report/${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response
      } 
      catch (error) {
        throw error
      }
    }

    const saveReport = async (data) => {
      let apiUrl = `${apiHost}/order/order-report/`;
      try {
        const method = data.id ? 'PUT' : 'POST';
        if (method == 'PUT') {
          apiUrl += data.id + '/';
        }
        const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
        return response
      }
      catch (error) {
        throw error
      }
    }

    const saveDocument = async (data) => {
      let apiUrl = `${apiHost}/order/order-report-document/`;
      try {
  
        let options;
        const formData = new FormData();
        formData.append('id', data.id);
        formData.append('file', data.file);
  
        options = formData;
        const response = await $apiManager.fetch(apiUrl, 'POST', options)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
  
    }

    const postClaimRequestOrder = async (order_type_token, data) => {
      const apiUrl = `${apiHost}/order/claim-request-order/${order_type_token}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response
      }
      catch (error) {
        throw error
      }
    }
    
    const save = async (data) => {
      let apiUrl = `${apiHost}${entity}`;
      try {
        const method = data.id ? 'PATCH' : 'POST';
        if (method == 'PATCH') {
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
    }

    const invalidateOrder = async (id) => {
      const apiUrl = `${apiHost}/order/invalidate-order/${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', {}, { 'Content-Type': 'application/json' })
        return response
      }
      catch (error) {
        throw error
      }
    }

    const validateChangeMeter = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/validate-change-meter/`;
      try {
          const response = await $apiManager.fetch(apiUrl, 'GET')
          return response
        }
        catch (error) {
          throw error
        }
      }
            const applyChangeMeter = async (id) => {
        const apiUrl = `${apiHost}${entity}${id}/apply-change-meter/`;
        try {
          const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' })
          return response
        }
        catch (error) {
          throw error
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

    const downloadOrder = async (id) => {
      const apiUrl = `${apiHost}/order/download-order/${id}/`;

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

    const previewChangeMeter = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/preview-change-meter/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET')
        return response
      }
      catch (error) {
        throw error
      }
    }
  
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false,
      operatorId = null, type_ids = [], contract_id = null, contract_request_id = null, connection_request_id = null,
      incident_id = null, search_all_address = '', search_by_address = '', related_contract_token = null, creator_ids = [], city_ids = [],
      supply_point_ids = [], columns = []) => {
      const exploitation_id = localStorage.getItem('exploitation');
      return $apiManager.exportTable(entity, {
        searchQuery, filters, sort, desc,
        columns,
        extraParams: {
          search_all_address,
          search_by_address,
          operators: operatorId,
          type: type_ids,
          contract: contract_id,
          supply_point_ids,
          contract_request: contract_request_id,
          connection_request: connection_request_id,
          incident: incident_id,
          related_contract_token,
          created_by: creator_ids,
          city: city_ids,
          exploitation: exploitation_id || null,
        }
      });
    }

    const apiService = {
      getAll,
      exportData,
      getFilterStatus,
      getFilterCities,
      getDetail,
      save,
      deleteItem,
      invalidateOrder,
      validateChangeMeter,
      applyChangeMeter,
      previewChangeMeter,
      getFilterConnection,
      getFilterContractTermination,
      getFilterConnectionRequest,
      getOrderByToken,
      postClaimRequestOrder,
      getReports,
      getReportDetail,
      saveReport,
      saveDocument,
      getPermissions,
      downloadOrder
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  