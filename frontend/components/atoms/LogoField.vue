<script setup>
import { ref, watch } from 'vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const props = defineProps({
  label: String,
  name: String,
  logo: String
});

// Si el fitxer del logo no es pot carregar (p.ex. una base de dades copiada d'un altre
// entorn sense el directori `media`), abans quedava un requadre buit i es perdia el camp
// amb el nom: en aquest cas mostrem el camp normal, com si no hi hagués logo.
const logoFailed = ref(false);

watch(() => props.logo, () => {
  logoFailed.value = false;
});
</script>

<template>
  <FieldDetail v-if="!props.logo || logoFailed" :label="props.label" :value="props.name" />
  <div v-else :id="'field_' + props.label" class="mb-2 grid grid-cols-[120px,1fr] items-center">
    <img
      :src="props.logo"
      :alt="props.name"
      class="w-16 h-16 rounded-md border object-cover"
      @error="logoFailed = true" />
    <span class="text-black-900 font-medium">{{ props.name }}</span>
  </div>
</template>
