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

    nuxtApp.provide('MeterCommTechnologyApiService', { getAll, getOrCreate });
});
