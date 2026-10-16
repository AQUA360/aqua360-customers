import { ref, watch, onMounted } from 'vue';

/**
 * Dades d'una card del dashboard. Cada card les demana per separat, de manera
 * que una de lenta no bloqueja la resta de la pàgina. Es tornen a demanar quan
 * canvia la configuració o el `refreshKey` (botó de refrescar de la card).
 */
export function useDashboardCardData(key, config, refreshKey) {
  const { $DashboardApiService } = useNuxtApp();
  const data = ref(null);
  const loading = ref(false);
  const error = ref(null);
  let requestId = 0;

  const load = async () => {
    const current = ++requestId;
    loading.value = true;
    error.value = null;
    try {
      const response = await $DashboardApiService.getCardData(key, config.value);
      if (current === requestId) data.value = response.data;
    } catch (err) {
      if (current === requestId) error.value = err;
    } finally {
      if (current === requestId) loading.value = false;
    }
  };

  onMounted(load);
  watch(() => JSON.stringify(config.value || {}), load);
  watch(refreshKey, load);

  return { data, loading, error, load };
}
