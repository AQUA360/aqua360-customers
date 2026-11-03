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

    const getByName = async (name) => {
        let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(name)
        try {
            const response = await $apiManager.fetch(apiUrl,'GET')
            return response.results
        }
        catch (error) {
            throw error;
        }
    }

    const getOrCreate = async (name) => {
        const apiUrl = apiHost + entity + 'get-or-create/';
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify({ name }), {
            'Content-Type': 'application/json'
        });
    }

    const apiService = {
        getAll, getByName, getOrCreate
    };
    
    nuxtApp.provide(provideName, apiService);
})