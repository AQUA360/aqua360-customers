import { ref } from 'vue';

export function useOrderReasonId(configToken) {
  const reasonId = ref(null);
  const resolved = ref(false);

  const getReasonId = async () => {
    if (resolved.value) return reasonId.value;

    const { $ConfigProjectApiService, $ConfiglistApiService } = useNuxtApp();

    let reason_token = null;
    try {
      reason_token = await $ConfigProjectApiService.get(configToken);
    } catch (error) {
      console.warn(`ConfigProject '${configToken}' not found; order will be created without reason`, error);
      resolved.value = true;
      return null;
    }
    if (!reason_token) {
      resolved.value = true;
      return null;
    }

    try {
      let page = 1;
      let resp = null;
      let reason = null;
      do {
        resp = await $ConfiglistApiService.getAll('order/order-reason', page);
        reason = resp.results?.find(item => item.token == reason_token)
          || (/^\d+$/.test(String(reason_token)) ? resp.results?.find(item => item.id == Number(reason_token)) : null);
        if (reason || !resp.next || page >= 100) break;
        page += 1;
      } while (resp.next);
      reasonId.value = reason?.id || null;
    } catch (error) {
      console.error(`Error resolving order reason for '${configToken}':`, error);
    } finally {
      resolved.value = true;
    }
    return reasonId.value;
  };

  return { reasonId, resolved, getReasonId };
}
