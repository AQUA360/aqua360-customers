<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import OperatorEdit from '~/components/organisms/OperatorEdit.vue';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $OperatorApiService } = useNuxtApp();

const route = useRoute()
const id = parseInt(route.params.id)

onMounted(async () => {
  objectPermissions.value = await checkPermission($OperatorApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.modify') }} {{ t('operator') }}</H1>
    </div>
    <OperatorEdit :id="id" />
  </div>
</template>