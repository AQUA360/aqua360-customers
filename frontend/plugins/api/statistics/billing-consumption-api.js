export default defineNuxtPlugin(nuxtApp => {
    const entity = '/statistics/billing-consumption/';
    const provideName = 'BillingConsumptionApiService';

    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (params = {}) => {
        let apiUrl = apiHost + entity;
        const query = new URLSearchParams(params).toString();
        if (query) {
            apiUrl += '?' + query;
        }

        try {
            const response = await $apiManager.fetch(apiUrl, 'GET');
            return response;
        } catch (error) {
            throw error;
        }
    };

    const getByContract = async (contractId) => {
        return getAll({ contract: contractId });
    };

    const getByPeriod = async (year, month) => {
        return getAll({ year, month });
    };

    const apiService = {
        getAll,
        getByContract,
        getByPeriod,
    };

    nuxtApp.provide(provideName, apiService);
});
