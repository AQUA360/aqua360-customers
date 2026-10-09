<script setup>
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import PriceRateEdit from '~/components/organisms/PriceRateEdit.vue';
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
const priceRateId = ref(route.params.id)

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ priceRateId? `${$t('common.modify')} ${t('price_rate')}` : $t('pricing_block.new_price_rate') }}</H1>
    </div>
    <PriceRateEdit :id="parseInt(priceRateId)" />
  </div>
</template>