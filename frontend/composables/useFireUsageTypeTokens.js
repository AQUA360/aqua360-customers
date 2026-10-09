import { ref } from 'vue';

/**
 * Resolves the ContractUseType token(s) considered fire hydrant usage.
 * The ConfigProject value can hold several tokens separated by commas
 * (e.g. 'AV BIE D,AV BIE I') to support clients with more than one
 * fire-related use type.
 */
export function useFireUsageTypeTokens() {
  const fireUsageTypeTokens = ref([]);

  const fetchFireUsageTypeTokens = async () => {
    const { $ConfigProjectApiService } = useNuxtApp();
    let rawValue = null;
    try {
      rawValue = await $ConfigProjectApiService.get('fire_usage_type_token');
      if (!rawValue) {
        rawValue = await $ConfigProjectApiService.get('fire_usage_type_id');
      }
      if (!rawValue) {
        rawValue = 'inc';
      }
    } catch (err) {
      console.error(err);
      rawValue = 'inc';
    }
    fireUsageTypeTokens.value = String(rawValue).split(',').map((token) => token.trim()).filter(Boolean);
  };

  const isFireContract = (contract) => {
    if (!contract) return false;
    return contract.is_fire
      || fireUsageTypeTokens.value.includes(contract.use_type_token)
      || fireUsageTypeTokens.value.includes(contract.use_type?.token);
  };

  return { fireUsageTypeTokens, fetchFireUsageTypeTokens, isFireContract };
}
