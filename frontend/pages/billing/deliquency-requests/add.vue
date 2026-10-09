<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import DeliquencyRequestEdit from '~/components/organisms/DeliquencyRequestEdit.vue';
const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`billing_block.mng_delinquent`) }}</H1>
    </div>
    <div>
      <DeliquencyRequestEdit :request="null" />
    </div>
  </div>
</template>
