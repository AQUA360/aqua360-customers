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
        let result = []
        modelsByManufacturer.filter(model => model.name == modelName).forEach(model => {
            result.push(model)
        });
        return result
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

    const apiService = {
        getModelsByManufacturer, getByName
    };
    
    nuxtApp.provide(provideName, apiService);
})