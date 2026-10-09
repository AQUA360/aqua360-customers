<script setup lang="ts">
import { useExploitationStore } from '~/stores/useExploitationStore';

const config = useRuntimeConfig();
const env = config.public.env;
const exploitationStore = useExploitationStore();

useHead({
  title: () => {
    const name = exploitationStore.current?.name;
    return name ? `Customers - ${name}` : 'Customers';
  },
  meta: [
    { name: 'description', content: "Programa d'abonats" }
  ],
})
</script>
<template>
  <div>
    <!-- Environment Badge -->
    <div 
      v-if="env && env !== 'prod' && env !== 'production'" 
      :class="[
        'fixed top-0 left-0 z-[9999] text-white px-4 pb-1 text-sm font-bold shadow-lg rounded-br-md',
        env.toUpperCase() === 'LOCAL' ? 'bg-green-500' : 'bg-orange-500'
      ]"
    >
      {{ env.toUpperCase() }}
    </div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>
