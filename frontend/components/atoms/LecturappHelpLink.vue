<script setup>
defineProps({
  // Només la icona, per a llocs amb poc espai (p. ex. al costat d'una opció de formulari)
  iconOnly: { type: Boolean, default: false },
});
</script>

<template>
  <NuxtLink to="/reading/lecturapp" target="_blank"
    class="inline-flex items-center gap-1 text-sm text-sky-500 hover:text-sky-700 hover:underline"
    :title="$t('lecturapp_help.help_link')">
    <Icon name="fa6-solid:circle-question" />
    <span v-if="!iconOnly">{{ $t('lecturapp_help.help_link') }}</span>
  </NuxtLink>
</template>
