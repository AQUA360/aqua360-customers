<script setup>
const props = defineProps({
  company: {
    type: Object,
    required: false
  }
});


</script>


<template>
  <!-- <abbr :title="person?.token" class="inline-block no-underline"><slot>{{ getName() }}</slot></abbr> -->
  <span class="badge-gray flex justify-between inline-block rounded px-2 py-0.5 text-sm cursor-default w-full">
    <slot>
      <span>{{ company?.alias || "-" }}</span>
      <span>{{ company?.vat || "-" }}</span>
    </slot>
  </span>
</template>