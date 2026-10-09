<script setup>
const emits = defineEmits(['click']);

const props = defineProps({
    disabled: {
        type: Boolean,
        default: false
    }, 
    small: {
        type: Boolean,
        default: false
    }
})

const click = () => {
    emits('click');
};
</script>

<template>
    <button :disabled="disabled" @click="click" class="px-4 text-slate-600 rounded bg-gray-100 w-full text-left border-2 border-dashed disabled:cursor-auto enabled:hover:bg-gray-200 italic disabled:opacity-50"
    :class="{ 'py-10': !small, 'py-2': small }"><slot> </slot></button>
</template>

