<script setup>
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import InvoiceView from '~/components/organisms/InvoiceView.vue';
const { t } = useI18n();

const route = useRoute()
const lineItemTypeId = ref(route.params.id)


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <!-- <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('Factura') }}</H1>
    </div> -->
    <InvoiceView :id="parseInt(lineItemTypeId)" />
  </div>
</template>