// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/notification/calendar-task/';
    const provideName = 'CalendarTaskApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (year = null, month = null, contract_id = null) => {
      let apiUrl = apiHost + entity;

      if (contract_id) {
        apiUrl += '&contract=' + contract_id;
      } else {
        apiUrl += '?year=' + year + '&month=' + month;
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

    const getDayTasks = async(set_date) => {
      let apiUrl = apiHost + entity + '?set_date=' + set_date;

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
  
    /**
     * Tasques entre dues dates (vista setmanal/mensual/llista del calendari).
     * `filters` admet task_done, assigned ('me' | 'all_users'), overdue, search...
     */
    const getRange = async (dateFrom, dateTo, filters = {}) => {
      const params = new URLSearchParams();
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      Object.entries(filters).forEach(([name, value]) => {
        if (value !== null && value !== undefined && value !== '') params.append(name, value);
      });
      params.append('ordering', 'set_date,time');
      return await $apiManager.fetch(`${apiHost}${entity}?${params.toString()}`, 'GET');
    }

    /** Pendents d'avui i endarrerides: `{ today, overdue }`. */
    const getSummary = async (assigned = null) => {
      const query = assigned ? `?assigned=${assigned}` : '';
      return await $apiManager.fetch(`${apiHost}${entity}summary/${query}`, 'GET', null, null, true);
    }

    /** Update a task completion flag without changing its other fields. */
    const setDone = async (id, taskDone) => {
      return await $apiManager.fetch(`${apiHost}${entity}${id}/`, 'PATCH', { task_done: taskDone }, { 'Content-Type': 'application/json' });
    }

    /** Fetch the current user task notification preferences. */
    const getNotificationPreference = async () => {
      return await $apiManager.fetch(`${apiHost}/notification/preference/`, 'GET');
    }

    /** Update the current user task notification preferences. */
    const saveNotificationPreference = async (data) => {
      return await $apiManager.fetch(`${apiHost}/notification/preference/`, 'PUT', data, { 'Content-Type': 'application/json' });
    }

    /** Amb `series`, en una tasca recurrent s'esborren també les ocurrències pendents posteriors. */
    const deleteItem = async (id, series = false) => {
      const apiUrl = `${apiHost}${entity}${id}/${series ? '?series=true' : ''}`;

      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        return true;
  
      } catch (error) {
        throw error;
      }
    };
  
    const apiService = {
      getAll,
      getDetail,
      getDayTasks,
      getRange,
      getSummary,
      setDone,
      getNotificationPreference,
      saveNotificationPreference,
      deleteItem,
      save,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  