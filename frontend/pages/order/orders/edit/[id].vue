<script setup>
import H1 from '~/components/atoms/H1.vue';
import OrderEdit from '~/components/organisms/OrderEdit.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const route = useRoute()
const id = parseInt(route.params.id)
const toast = useToast();
const objectPermissions = ref(null);
const { $OrderApiService } = useNuxtApp();
onMounted(async () => {
  objectPermissions.value = await checkPermission($OrderApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-2 md:p-4 max-w-full">
    <div class="flex justify-between items-center mb-4 md:mb-6">
      <H1 class="text-lg md:text-xl">{{ $t('common.modify') }} {{ $t('common.work_order') }}</H1>
    </div>
    <div class="border m-0 md:m-2 rounded border-gray-300">
      <OrderEdit :id="id" />
    </div>
  </div>
</template>