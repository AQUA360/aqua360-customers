// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/reading/';
    const provideName = 'ReadingApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false, contracts = [], supply_point = null, meter=null, is_control = null) => {
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

      if (contracts.length > 0) {
        apiUrl += `&contract=${contracts.join(',')}`;
      }
      
      if (supply_point) {
        apiUrl += `&supply_point=${supply_point}`;
      }

      if (meter) {
        apiUrl += `&meter=${meter}`;
      }

      if (is_control != null) {
        apiUrl += `&is_control=${is_control}`;
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
    
    const checkAllowSave = async (data) => {
      let apiUrl = `${apiHost}${entity}check-allow-period/`;
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

    const saveRequestReading = async (data) => {   // DIFF SAVE TO AVOID PROBLEMS WITH NORMAL SAVE
      let apiUrl = `${apiHost}${entity}request-reading/`;
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
  
    // "Facturar període complert": darrera lectura no facturada del contracte anterior
    const getRequestTransferableReading = async (contract_request_id, supply_point_id, meter_id) => {
      const params = new URLSearchParams({ contract_request_id, supply_point_id, meter_id });
      let apiUrl = `${apiHost}${entity}request-transferable-reading/?${params.toString()}`;
      try {
        return await $apiManager.fetch(apiUrl, 'GET');
      } catch (error) {
        throw error;
      }
    }

    const transferRequestReading = async (data) => {
      let apiUrl = `${apiHost}${entity}request-transfer-reading/`;
      try {
        return await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      } catch (error) {
        throw error;
      }
    }

    const saveModifiedReadings = async (data) => {
      let apiUrl = `${apiHost}${entity}modified-readings/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
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
  
    const getModificationData = async (data) => {
      const apiUrl = `${apiHost}${entity}get-modification-data/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'POST', data, { 'Content-Type': 'application/json' });
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const getReadingDetail = async (id, page = 1) => {
      const apiUrl = `${apiHost}/billing/reading-detail/${id}/?page=${page}`;

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
    
    const addReadingToCommunicationProcess = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/add-to-communication-process/`;
  
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

    const getReadingsByBatch = async (batch_id, page) => {

      let apiUrl = `${apiHost}${entity}by-batch/`
      if (batch_id) {
        apiUrl += `?batch=${batch_id}`;
      }
      apiUrl += `&page=${page}`;
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

    const getReadingsByBatchMinimal = async (batch_id, page, filter = null, previous_leak = false, leak = false, sort = null, desc = false, search = null) => {

      let apiUrl = `${apiHost}${entity}by-batch-minimal/`
      if (batch_id) {
        apiUrl += `?batch=${batch_id}`;
      }
      if (filter) {
        apiUrl += `&${filter}`;
      }
      if (previous_leak) {
        apiUrl += `&previous_leak=true`;
      }
      if (leak) {
        apiUrl += `&leak=true`;
      }
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
      if (search && search != '') {
        apiUrl += `&search=${search}`;
      }
      apiUrl += `&page=${page}`;
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

    const filterExportReadings = async (data) => {
      let apiUrl = `${apiHost}${entity}filter-export/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }

    const exportReadings = async (data) => {
      let apiUrl = `${apiHost}${entity}export-readings/`;
      // Name for the downloads queue (set by useServerExport).
      if ($apiManager.pendingExportName) apiUrl += `?export_name=${encodeURIComponent($apiManager.pendingExportName)}`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }

    const recalculateEstimatedReadings = async (reading_ids) => {
      let apiUrl = `${apiHost}${entity}recalculate-estimated/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', { reading_ids }, { 'Content-Type': 'application/json' });
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const estimateReading = async (data) => {
      let apiUrl = `${apiHost}${entity}estimate/`;
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

    const doDelete = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'DELETE');
        if (response) {
          return response;
        }
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      save,
      saveModifiedReadings,
      saveRequestReading,
      getRequestTransferableReading,
      transferRequestReading,
      checkAllowSave,
      getDetail,
      getReadingDetail,
      getReadingsByBatch,
      getReadingsByBatchMinimal,
      getModificationData,
      recalculateEstimatedReadings,
      estimateReading,
      filterExportReadings,
      exportReadings,
      addReadingToCommunicationProcess,
      getPermissions,
      doDelete
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  