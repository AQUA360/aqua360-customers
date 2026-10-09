<template>
    <button @click="click" class="flex items-center justify-center gap-2 inline-block px-4 py-2 bg-slate-500 text-white rounded hover:bg-slate-600">
        <span><Icon name="fa6-solid:angles-right" class="text-white-500" /></span>
        <span>{{ $slots.default ? $slots.default() : $t('common.accept') }}</span>
    </button>
</template>

<script setup>
const emits = defineEmits(['click']);
const click = () => {
    emits('click');
};
</script>