<script setup>

const props = defineProps({
  id: Number,
  path: String,
});

const emit = defineEmits(['click']);

const redirect = () => {
  redirectDetail(props.path, props.id)
}

</script>
<template>
    <button @click="redirect"  class="text-start text-sky-500 underline flex items-center gap-2">
        <slot name="text"></slot>
        <Icon name="fa6-solid:arrow-up-right-from-square" class="" />
    </button>

</template>