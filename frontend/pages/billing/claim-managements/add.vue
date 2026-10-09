<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import ContractRequestEdit from '~/components/organisms/ContractRequestEdit.vue';
import ClaimRequestEdit from '~/components/organisms/ClaimRequestEdit.vue';

const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`claim_block.new_claim_request`) }}</H1>
    </div>
    <div>
      <ClaimRequestEdit :request="null" />
    </div>
  </div>
</template>
