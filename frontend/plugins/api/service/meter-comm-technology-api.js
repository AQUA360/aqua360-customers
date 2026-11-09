export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/meter-comm-technology/';
    const { $apiManager } = useNuxtApp();
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async () => {
        const response = await $apiManager.fetch(apiHost + entity, 'GET');
        if (!response.results) {
            throw new Error('Error estructura `results` no trobat');
        }
        return response;
    };

    const getOrCreate = async (name) => {
        return await $apiManager.fetch(
            apiHost + entity + 'get-or-create/',
            'POST',
            JSON.stringify({ name }),
            { 'Content-Type': 'application/json' }
        );
    };

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

    nuxtApp.provide('MeterCommTechnologyApiService', { getAll, getOrCreate, list, create, update, remove });
});
