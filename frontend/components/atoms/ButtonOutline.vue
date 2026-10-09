<template>
    <button @click="click" :disabled="disabled" 
    class="flex justify-start gap-3 items-center text-blue-500 px-4 py-1 bg-white rounded-md bg-slate-100 w-full border hover:bg-slate-50 border-blue-500 mb-2 rounded max-w-96"
    :class="{ 'opacity-60 cursor-not-allowed': disabled }">
        <span class="text-xl">&rarr;</span>
        <span class="pt-0.5"><slot /></span>
        
    </button>
</template>

<script setup>
const props = defineProps({
    disabled: {
        type: Boolean,
        default: false,
    },
});
const emits = defineEmits(['click']);
const click = () => {
    emits('click');
};
</script>