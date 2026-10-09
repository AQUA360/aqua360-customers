import { ref } from 'vue';

/**
 * Resolves the SupplyPoint status token that represents an active supply cut
 * (tall de subministrament), as configured per project.
 */
export function useSupplyPointCutStatusToken() {
  const supplyPointCutStatusToken = ref(null);

  const fetchSupplyPointCutStatusToken = async () => {
    const { $ConfigProjectApiService } = useNuxtApp();
    try {
      supplyPointCutStatusToken.value = await $ConfigProjectApiService.get('supply_point_status_cut_token');
    } catch (err) {
      console.error(err);
      supplyPointCutStatusToken.value = null;
    }
  };

  const isSupplyPointCut = (contract) => {
    if (!supplyPointCutStatusToken.value || !contract) return false;
    const statusToken = contract.supply_point_default?.status_token
      ?? contract.supply_point_default_status_token
      ?? contract.supply_points?.[0]?.status_token;
    return statusToken === supplyPointCutStatusToken.value;
  };

  return { supplyPointCutStatusToken, fetchSupplyPointCutStatusToken, isSupplyPointCut };
}
