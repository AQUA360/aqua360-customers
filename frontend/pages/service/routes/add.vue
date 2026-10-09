<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $RouteApiService } = useNuxtApp();
onMounted(async () => {
  objectPermissions.value = await checkPermission($RouteApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('service_block.new_route') }}</H1>
    </div>
    <OrganismsRouteEdit />
  </div>
</template>
