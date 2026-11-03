// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/notification/incident/';
    const provideName = 'IncidentApiService';


    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contract_id=null, invoice_id=null, types=[], commitment_id=null, order_id=null, assigned_to_me=false, overdue=false, out_of_term=false) => {
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

        if (sort) {
            apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
        }

        if (contract_id) {
            apiUrl += `&contract=${contract_id}`;
        }
        if (invoice_id) {
            apiUrl += `&invoice=${invoice_id}`;
        }
        if (commitment_id) {
            apiUrl += `&commitment_deposit=${commitment_id}`;
        }
        if (order_id) {
            apiUrl += `&order=${order_id}`;
        }
        if (types.length > 0) {
            apiUrl += `&incident_type=${types.join(',')}`;
        }
        if (assigned_to_me) {
            apiUrl += `&assigned_to_me=true`;
        }
        if (overdue) {
            apiUrl += `&overdue=true`;
        }
        if (out_of_term) {
            apiUrl += `&closed_out_of_term=true`;
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

    const exportExcel = async (searchQuery = '', filters = [], types = [], assigned_to_me = false, overdue = false, out_of_term = false) => {
        let apiUrl = apiHost + entity + 'export/excel/?search=' + encodeURIComponent(searchQuery);

        let filtersValues = [];
        if (filters.length > 0) {
            filters.map(filter => {
                filtersValues.push(filter);
            })
        }

        if (filtersValues.length > 0) {
            apiUrl += `&status=${filtersValues.join(',')}`;
        }

        if (types.length > 0) {
            apiUrl += `&incident_type=${types.join(',')}`;
        }
        if (assigned_to_me) {
            apiUrl += `&assigned_to_me=true`;
        }
        if (overdue) {
            apiUrl += `&overdue=true`;
        }
        if (out_of_term) {
            apiUrl += `&closed_out_of_term=true`;
        }

        try {
            const response = await $apiManager.fetch(apiUrl, 'GET')
            return response;
        } catch (error) {
            throw error;
        }
    }

    // Esborrat lògic: el backend desa qui l'ha esborrat i quan
    const deleteItem = async (id) => {
        const apiUrl = `${apiHost}${entity}${id}/`;
        await $apiManager.fetch(apiUrl, 'DELETE');
        return true;
    };

    // Cronologia unificada de la incidència
    const getTimeline = async (id) => {
        return await $apiManager.fetch(`${apiHost}${entity}${id}/timeline/`, 'GET');
    };

    // Genera i envia (si hi ha correu) el justificant de registre
    const sendReceipt = async (id) => {
        return await $apiManager.fetch(`${apiHost}${entity}${id}/send-receipt/`, 'POST');
    };

    const apiService = {
        getAll,
        getDetail,
        save,
        getPermissions,
        exportExcel,
        deleteItem,
        getTimeline,
        sendReceipt
    };

    nuxtApp.provide(provideName, apiService);
});
