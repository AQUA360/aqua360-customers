<script setup>
const emit = defineEmits(['update:modelValue', 'select']);

defineProps({
    modelValue: {
        type: [String, Number],
        default: null,
    },
    options: {
        type: Array,
        default: () => [],
    },
});

const getOptionValue = (option) => option.value;
const getOptionLabel = (option) => option.label ?? option.value;

const handleSelect = (value) => {
    emit('update:modelValue', value);
    emit('select', value);
};
</script>

<template>
    <div class="inline-flex rounded-lg border border-slate-200 bg-sky-400 p-0.5 text-white">
        <button v-for="option in options" :key="getOptionValue(option)" type="button"
            @click="handleSelect(getOptionValue(option))"
            class="rounded-md px-3 py-1.5 text-xs uppercase tracking-wide transition-all font-bold"
            :class="modelValue === getOptionValue(option) ? 'bg-white text-sky-700 shadow-sm' : 'hover:text-slate-700'">
            {{ getOptionLabel(option) }}
        </button>
    </div>
</template>
