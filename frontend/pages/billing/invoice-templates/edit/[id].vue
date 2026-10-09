<script setup>
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import InvoiceTemplateHTMLModify from '~/components/organisms/InvoiceTemplateHTMLModify.vue';

const { t } = useI18n();
const route = useRoute()
const toast = useToast();
const objectPermissions = ref(null);
const { $InvoiceApiService } = useNuxtApp();

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <InvoiceTemplateHTMLModify :id="parseInt(route.params.id)"/>
  </div>
</template>