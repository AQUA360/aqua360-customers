<script setup>
import { useI18n } from 'vue-i18n';
import H1 from '~/components/atoms/H1.vue';
import BillingRangeEdit from '~/components/organisms/BillingRangeEdit.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const route = useRoute()
const billintRangeEditId = ref(route.params.id)
const returnPriceRateId = ref(route.query.price_rate_id ? parseInt(route.query.price_rate_id) : null)
const toast = useToast();
const { t } = useI18n();
const objectPermissions = ref(null);
const { $PriceRateApiService } = useNuxtApp();
onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
</script>

<template>
    <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
        <div v-if="billintRangeEditId != null">
            <div class="flex justify-between items-center mb-6">
                <H1>{{ $t('common.modify') }} {{ t('common.range') }}</H1>
            </div>
            <BillingRangeEdit :id="billintRangeEditId" :returnPriceRateId="returnPriceRateId"/>
        </div>
    </div>
</template>