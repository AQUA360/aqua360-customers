<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import OrderEdit from '~/components/organisms/OrderEdit.vue';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $OrderApiService } = useNuxtApp();
const route = useRoute();
const contractId = route.query.contract_id ? Number(route.query.contract_id) : null;
onMounted(async () => {
  objectPermissions.value = await checkPermission($OrderApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('order_block.new_order') }}</H1>
    </div>
    <div class="border m-2 rounded border-gray-300">
      <OrderEdit :id="null" :contract_id="contractId" />
    </div>
  </div>
</template>