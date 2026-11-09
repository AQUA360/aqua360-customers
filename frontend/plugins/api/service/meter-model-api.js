export default defineNuxtPlugin(nuxtApp => {
    const entity = '/service/meter-model/';
    const provideName = 'MeterModelApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getModelsByManufacturer = async (manufacturerId) => {
        if (manufacturerId && manufacturerId > 0) {
            let apiUrl = apiHost + entity + 'by_manufacturer/?manufacturer_id=' + manufacturerId
            try {
                const response = await $apiManager.fetch(apiUrl,'GET')
                return response
            } 
            catch (error) {
                throw error;
            } 
        }
        else {
            throw new Error('Manufacturer ID must be provided!');
        }
    }

    const getByName = async (manufacturerId, modelName) =>  {
        let modelsByManufacturer = await getModelsByManufacturer(manufacturerId)
        const target = (modelName || '').trim().toLowerCase()
        return modelsByManufacturer.filter(model => (model.name || '').trim().toLowerCase() === target)
    }

    const getOrCreate = async (manufacturerId, name) => {
        const apiUrl = apiHost + entity + 'get-or-create/';
        return await $apiManager.fetch(apiUrl, 'POST', JSON.stringify({
            manufacturer_id: manufacturerId,
            name
        }), {
            'Content-Type': 'application/json'
        });
    }

    const getByName_DEPRECATED = async (name) => {
        let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(name)
        try {
            const response = await $apiManager.fetch(apiUrl,'GET')
            return response.results
        }
        catch (error) {
            throw error;
        }
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
        getModelsByManufacturer, getByName, getOrCreate, list, create, update, remove
    };
    
    nuxtApp.provide(provideName, apiService);
})