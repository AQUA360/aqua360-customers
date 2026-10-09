import { defineNuxtPlugin } from '#app'
export default defineNuxtPlugin(nuxtApp => {
    console.log('--- OV Logs Plugin Loading ---');
    const service = '/logger/ov_logs/'; // Temporarily assuming endpoint /logger/ov_logs/
    const provideName = 'OvLogsApiService';
    const { $apiManager } = nuxtApp;
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, pageSize = 20, startDate = null, endDate = null) => {
        let apiUrl = apiHost + service + `?page=${page}&page_size=${pageSize}`;
        if (startDate) {
            apiUrl += `&start_date=${startDate}`;
        }
        if (endDate) {
            apiUrl += `&end_date=${endDate}`;
        }
        if (searchQuery) {
            apiUrl += `&search=${encodeURIComponent(searchQuery)}`;
        }
        if (filters && filters.length > 0) {
            const filtersStr = filters.join(',');
            apiUrl += `&status=${filtersStr}`;
        }
        if (sort) {
            apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
        }
        try {
            const response = await $apiManager.fetch(apiUrl, 'GET');
            if (response && response.results) {
                return response;
            } else {
                throw new Error('Error structure `results` not found');
            }
        } catch (error) {
            throw error;
        }
    }
    const getPermissions = async () => {
        // Basic implementation for testing, assumes view allowed
        return { can_view: true, can_add: false, can_change: false, can_delete: false };
    }
    const getDetail = async (id) => {
        const apiUrl = apiHost + service + id + '/';
        try {
            return await $apiManager.fetch(apiUrl, 'GET');
        } catch (error) {
            throw error;
        }
    }
    const apiService = {
        getAll,
        getDetail,
        getPermissions
    };
    nuxtApp.provide(provideName, apiService);
});