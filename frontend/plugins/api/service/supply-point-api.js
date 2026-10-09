import api from "../api";

// plugins/services/service/supply-point-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/supply-point/';
  const provideName = 'SupplyPointApiService';

  const {$apiManager} = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (searchQuery = '') => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery);
    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`; 
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  const getList = async (searchQuery = '', filters = [], page = 1, 
    sort = null, desc = false, noMeter = false, 
    no_property = false, is_potable = null, cluster_nozzle_type = null,
    type = [], has_fraud= null, supply_type = [], search_by_address = '',
    placement_id = []) => {
    let apiUrl = `${apiHost}${entity}list/?search=${encodeURIComponent(searchQuery)}&page=${page}`;

    if (noMeter) {
      apiUrl += `&no_meters=true`;
    }

    if (no_property) {
      apiUrl += `&no_property=true`;
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`; 
    }
    // Afegir els filtres a la URL
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

    if (is_potable != null) {
      apiUrl += `&is_potable=${is_potable}`;
    }

    if (has_fraud != null) {
      apiUrl += `&has_fraud=${has_fraud}`;
    }

    if (cluster_nozzle_type) {
      apiUrl += `&cluster_nozzle_type=${cluster_nozzle_type}`;
    }

    if (type.length > 0) {
      apiUrl += `&type=${type.join(',')}`;
    }

    if (supply_type.length > 0) {
      apiUrl += `&supply_type=${supply_type.join(',')}`;
    }

    if (placement_id.length > 0) {
      apiUrl += `&placement_id=${placement_id.join(',')}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
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

  // Server-side export (async). Mirrors getList's filters/search/sort but POSTs
  // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
  // background task, returning `{ task_id }`. Same args as getList (no page).
  const exportData = async (
    searchQuery = '', filters = [], sort = null, desc = false,
    noMeter = false, no_property = false, is_potable = null,
    cluster_nozzle_type = null, type = [], has_fraud = null,
    supply_type = [], search_by_address = '', placement_id = [],
    columns = []) => {
    let exploitation_id = localStorage.getItem('exploitation');

    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc,
      columns,
      extraParams: {
        no_meters: noMeter ? 'true' : null,
        no_property: no_property ? 'true' : null,
        exploitation: exploitation_id || null,
        is_potable: is_potable != null ? is_potable : null,
        has_fraud: has_fraud != null ? has_fraud : null,
        cluster_nozzle_type,
        type,
        supply_type,
        placement_id,
        search_by_address: search_by_address || null,
      }
    });
  };

  const getByProperty = async (propertyId) => {
    let apiUrl = `${apiHost}${entity}list/?property=${propertyId}`;
    let allResults = [];
    let nextUrl = apiUrl;

    try {
      while (nextUrl) {
        const response = await $apiManager.fetch(nextUrl, 'GET');
        if (response.results) {
          allResults = allResults.concat(response.results);
          nextUrl = response.next;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      }
      return { results: allResults };
    } catch (error) {
      throw error;
    }
  };

  const getByStreet = async (data) => {
    let apiUrl = `${apiHost}${entity}get-by-street`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data);
      if (response) {
        return response;
      } else {
        throw new Error('Error obtenint dades');
      }
    } catch (error) {
      throw error;
    }
  };
  
  const getByContract = async (contracts_id) => {
    const apiUrl = `${apiHost}${entity}list/?contract=${contracts_id.join(',')}`;

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

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/service/supply-point-status/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
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

  const getSupplyPointsByClusterId = async (clusterId) => {
    const apiUrl = `${apiHost}${entity}?cluster=${clusterId}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  
  const save = async (data) => {
    const apiUrl = apiHost + entity;

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

  const patch = async (id, data) => {
    const url = `${apiHost}${entity}${id}/`;
    try {
      const response = await $apiManager.fetch(url, 'PATCH', JSON.stringify(data), { 'Content-Type': 'application/json' });
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const saveMeterChange = async (data) => {
    const apiUrl = `${apiHost}${entity}save-meter-change/`;
    const method = 'POST';
    const url = apiUrl;
    try {
      const response = await $apiManager.fetch(url, method, data, { 'Content-Type': 'application/json' } );
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const activate = async (id) => {
    const apiUrl = `${apiHost}${entity}`;
    const method = 'PUT';
    const url = `${apiUrl}${id}/activate`;

    // Create a FormData object
    const formData = new FormData();

    try {
      const response = await $apiManager.fetch(url, method, formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error SupplyPointApiService activate');
      }
    } catch (error) {
      throw error;
    }
  }

  const deactivate = async (id, removal_at, removal_reason) => {
    const apiUrl = `${apiHost}${entity}`;
    const method = 'PUT';
    const url = `${apiUrl}${id}/deactivate`;

    // Create a FormData object
    const formData = new FormData();
    if (removal_at) {
      formData.append('removal_at', removal_at);
    }
    if (removal_reason) {
      formData.append('removal_reason', removal_reason);
    }

    try {
      const response = await $apiManager.fetch(url, method, formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error SupplyPointApiService activate');
      }
    } catch (error) {
      throw error;
    }
  }

  const changeAddress = async (id, previous_address, current_address) => {
    const apiUrl = `${apiHost}${entity}${id}/change-address`;

    // Create a FormData object
    const formData = new FormData();
    formData.append('previous_address', previous_address);
    formData.append('current_address', current_address);

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error SupplyPointApiService changeAddress');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateMeter = async (data) => {
    const apiUrl = `${apiHost}${entity}update-meter/`;

    const method = 'POST';
    const url = apiUrl;
    try {
      const response = await $apiManager.fetch(url, method, data, { 'Content-Type': 'application/json' } );

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

  const bulkUpdateProperty = async (data) => {
    const apiUrl = `${apiHost}${entity}bulk-update-property/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(data), { 'Content-Type': 'application/json' } );
      if (response) {
        return response;
      } else {
        throw new Error('Error en bulkUpdateProperty');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getData,
    getList,
    exportData,
    getFilterStatus,
    getByProperty,
    getDetail,
    getSupplyPointsByClusterId,
    save,
    patch,
    activate,
    deactivate,
    changeAddress,
    getByStreet,
    getByContract,
    updateMeter,
    saveMeterChange,
    getPermissions,
    bulkUpdateProperty
  };

  nuxtApp.provide(provideName, apiService);
});
