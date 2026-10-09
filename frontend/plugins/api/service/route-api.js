// plugins/services/service/route-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/service/route/';
  const provideName = 'RouteApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;


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

  const createRoute = async (data) => {
    let apiUrl = `${apiHost}${entity}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateRoute = async (data) => {
    let apiUrl = `${apiHost}${entity}${data.id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const deleteRoute = async (id) => {
    let apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE')
      return response;

    } catch (error) {
      throw error;
    }
  }

  const getDetail = async (id) => {
    let apiUrl = `${apiHost}${entity}${id}/`;

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

  const getRoutePositions = async (routeId) => {
    const apiUrl = `${apiHost}/service/route-position/?route=${routeId}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getAllRoutePositions = async (searchQuery = '', page = 1, sort = null, desc = false, routeId = null) => {
    let apiUrl = `${apiHost}/service/route-position/?search=${encodeURIComponent(searchQuery)}&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (routeId) {
      apiUrl += `&route=${routeId}`;
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

  const checkPositionOccupied = async (routeId, position) => {
    const apiUrl = `${apiHost}/service/route-position/check_position/?route=${routeId}&position=${position}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return !!response?.occupied;
    } catch (error) {
      console.error('Error checking position occupancy:', error);
      return false;
    }
  }

  const getOccupiedPositions = async (routeId) => {
    const apiUrl = `${apiHost}/service/route-position/?route=${routeId}&page_size=5000&fields=position`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    } catch (error) {
      console.error('Error fetching occupied positions:', error);
      return { last_position: 0, available_positions: [], results: [] };
    }
  }

  const getRoutePosition = async (id) => {
    let apiUrl = `${apiHost}/service/route-position/${id}/`;

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

  const createRoutePosition = async (data) => {
    let apiUrl = `${apiHost}/service/route-position/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateRoutePosition = async (data) => {
    let apiUrl = `${apiHost}/service/route-position/${data.id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const moveRoutePosition = async (id, newPosition, routeId) => {
    let apiUrl = `${apiHost}/service/route-position/${id}/move/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { new_position: newPosition, route_id: routeId }, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error movent la posició de ruta');
      }
    } catch (error) {
      throw error;
    }
  }

  const deleteRoutePosition = async (id) => {
    let apiUrl = `${apiHost}/service/route-position/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE')
      return response;

    } catch (error) {
      throw error;
    }
  }

  const getZone = async (id) => {
    let apiUrl = `${apiHost}/service/route-zone/${id}/`;

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

  const getRouteZones = async (exploitation_id = null) => {
    let apiUrl = `${apiHost}/service/route-zone/`;
    /* if (exploitation_id) {
      apiUrl += `?exploitation=${exploitation_id}`
    } */

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const createZone = async (data) => {
    let apiUrl = `${apiHost}/service/route-zone/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(data));
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateZone = async (data) => {
    let apiUrl = `${apiHost}/service/route-zone/${data.id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', JSON.stringify(data));
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const exportRoutePositions = async (routeId) => {
    const apiUrl = `${apiHost}${entity}${routeId}/export-positions/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', { async: true }, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const exportRouteSupplyPoints = async (routeId) => {
    const apiUrl = `${apiHost}${entity}${routeId}/export-supply-points/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getRouteSupplyPoints = async (
    routeId,
    page = 1,
    pageSize = 20,
    statusIds = [],
    contractStatusIds = [],
    ordering = null
  ) => {
    let apiUrl = `${apiHost}${entity}${routeId}/supply-points/?page=${page}&page_size=${pageSize}`;

    if (statusIds?.length > 0) {
      apiUrl += `&status=${statusIds.join(',')}`;
    }
    if (contractStatusIds?.length > 0) {
      apiUrl += `&contract_status=${contractStatusIds.join(',')}`;
    }
    if (ordering) {
      apiUrl += `&ordering=${encodeURIComponent(ordering)}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response?.results) {
        return response;
      }
      throw new Error('Error estructura `results` no trobat');
    } catch (error) {
      throw error;
    }
  }

  const getPermissions = async () => {
    const apiUrl = `${apiHost}${entity}permissions/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
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
    getDetail,
    createRoute,
    updateRoute,
    deleteRoute,
    getZone,
    getRoutePositions,
    getAllRoutePositions,
    exportRoutePositions,
    exportRouteSupplyPoints,
    getRouteSupplyPoints,
    getOccupiedPositions,
    checkPositionOccupied,
    getRoutePosition,
    createRoutePosition,
    updateRoutePosition,
    moveRoutePosition,
    deleteRoutePosition,
    getRouteZones,
    createZone,
    updateZone,
    getPermissions
  }

  nuxtApp.provide(provideName, apiService);
});
