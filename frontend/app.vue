<script setup lang="ts">
import { useExploitationStore } from '~/stores/useExploitationStore';
import EnvBadge from '~/components/organisms/EnvBadge.vue';

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
    <!-- Etiqueta de l'entorn (i, a test/staging, configuració de la sincronització amb prod) -->
    <EnvBadge />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>
