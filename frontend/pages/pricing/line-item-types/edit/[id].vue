<script setup>
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import LineItemTypeEdit from '~/components/organisms/LineItemTypeEdit.vue';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $PriceRateApiService } = useNuxtApp();
onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
const route = useRoute()
const lineItemTypeId = ref(route.params.id)


</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.modify') }} {{ t('pricing_block.line_item_detail') }}</H1>
    </div>
    <LineItemTypeEdit :id="parseInt(lineItemTypeId)" />
  </div>
</template>