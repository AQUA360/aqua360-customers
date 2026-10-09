<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import ContractRequestEdit from '~/components/organisms/ContractRequestEdit.vue';

const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`contract_block.new_contract_request`) }}</H1>
    </div>
    <div>
      <ContractRequestEdit :request="null" />
    </div>
  </div>
</template>
