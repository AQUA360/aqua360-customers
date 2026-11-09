export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/meter-manufacturer/';
    const provideName = 'MeterManufacturerApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async () => {
        let apiUrl = apiHost + entity
        try {
            const response = await $apiManager.fetch(apiUrl,'GET')
            if (response.results) {
                return response;
            } 
            else {
                throw new Error('Error estructura `results` no trobat');
            }
        } catch (error) {
            throw error;
        } 
    }

    // `search` fa coincidència parcial: es filtra per nom exacte (sense distingir majúscules)
    const getByName = async (name) => {
        const apiUrl = apiHost + entity + '?search=' + encodeURIComponent(name)
        const response = await $apiManager.fetch(apiUrl, 'GET')
        const target = (name || '').trim().toLowerCase()
        return (response.results || []).filter(m => (m.name || '').trim().toLowerCase() === target)
    }

    const getOrCreate = async (name) => {
        const apiUrl = apiHost + entity + 'get-or-create/';
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify({ name }), {
            'Content-Type': 'application/json'
        });
    }

    // CRUD del diccionari (Configuració > Comptadors)
    const list = async (params = {}) => {
        const query = new URLSearchParams(params).toString();
        const response = await $apiManager.fetch(apiHost + entity + (query ? '?' + query : ''), 'GET');
        return response.results || [];
    };

    const create = async (data) => {
        return await $apiManager.fetch(apiHost + entity, 'POST', JSON.stringify(data), { 'Content-Type': 'application/json' });
    };

    const update = async (id, data) => {
        return await $apiManager.fetch(apiHost + entity + id + '/', 'PATCH', JSON.stringify(data), { 'Content-Type': 'application/json' });
    };

    const remove = async (id) => {
        return await $apiManager.fetch(apiHost + entity + id + '/', 'DELETE');
    };

    const apiService = {
        getAll, getByName, getOrCreate, list, create, update, remove
    };
    
    nuxtApp.provide(provideName, apiService);
})