<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';

const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`service_block.new_connection_request`) }}</H1>
    </div>
    <div>
      <OrganismsConnectionRequestEdit :request="null"/>
    </div>
  </div>
</template>
