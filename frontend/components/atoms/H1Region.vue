<script setup>
defineProps({
  // Icona opcional que es mostra davant del títol (opcional per no trencar els
  // encapçalaments que ja existien sense icono).
  icon: {
    type: String,
    default: null,
  },
})
</script>
<template>
    <h1 class="text-lg font-bold text-gray-900 antialiased">
        <Icon v-if="icon" :name="icon" class="inline-block mr-2 align-middle text-gray-500" />
        <slot />
    </h1>
</template>
