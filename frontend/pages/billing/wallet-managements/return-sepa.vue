<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import SEPAReturnManagementEdit from '~/components/organisms/SEPAReturnManagementEdit.vue';

const { t }= useI18n();

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`billing_block.mng_return_sepa`) }}</H1>
    </div>
    <div>
      <SEPAReturnManagementEdit />
    </div>
  </div>
</template>
