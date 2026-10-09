export function usePermissions() {
    const config = useRuntimeConfig();
    const permissions = ref(null);
    const loading = ref(true);

    const fetchPermissions = async () => {
        try {
            const { $apiManager } = useNuxtApp();
            const response = await $apiManager.fetch(config.public.apiHost + '/auth/permission/my-permissions/', 'GET');
            permissions.value = response;
            loading.value = false;
        } catch (error) {
            loading.value = false;
        }
    };

    onMounted(async () => {
        await fetchPermissions();
    });

    return { permissions, loading };
}

export const checkPermission = async (service) => {
    try {
        const data = await service.getPermissions();
        // Be flexible with the naming conventions from the backend
        return {
            can_change: data.can_change || data.can_edit || data.change || data.edit || false, 
            can_view: data.can_view || data.view || false
        };
    } catch (error) {
        console.log(error);
        return {can_change: false, can_view: false};
    }
}