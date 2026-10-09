<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const route = useRoute()
import H1 from '~/components/atoms/H1.vue';
import AdjustmentEdit from '~/components/organisms/AdjustmentEdit.vue';
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $PriceRateApiService } = useNuxtApp();
const adjustment_id = ref(null);

onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  if (route.query.adjustment_id) {
    adjustment_id.value = route.query.adjustment_id;
  }
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ adjustment_id? `${$t('common.modify')} ${t('pricing_block.adjustment_detail')}` : $t('pricing_block.new_adjustment') }}</H1>
    </div>
    <AdjustmentEdit :id="null" />
  </div>
</template>