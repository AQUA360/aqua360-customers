<script setup>
import _ from 'lodash';
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
const props = defineProps({
    options: {
        type: Array,
        required: true,
    },
    modelValue: {
        type: Array,
        default: () => [],
    },
    optionTitle: {
        type: String,
        default: 'Option',
    },
});

const emit = defineEmits(['update:modelValue']);

const showPopup = ref(false);
const selectedValues = ref([...props.modelValue]);

const selectedOptions = ref([])
const allSelected = computed(() => {
    return selectedValues.value.length === props.options.length;
});

const openPopup = () => {
    showPopup.value = true;
};

const closePopup = (save) => {
    showPopup.value = false;
    if (save) {
        emit('update:modelValue', selectedValues.value);
    } else {
        selectedValues.value = [...props.modelValue];
    }
};

const selectAll = (event) => {
    if (event.target.checked) {
        selectedValues.value = props.options.map(option => option.code);
    } else {
        selectedValues.value = [];
    }
};

onMounted(() => {
    selectedOptions.value = props.options
})

watch(() => props.modelValue, (newValue) => {
    selectedValues.value = [...newValue];
});

watch(selectedValues, (newValue) => {
    emit('update:modelValue', newValue);
});
</script>
<template>
    <div class="relative inline-block ">
        <button @click="openPopup" class="button-default">
            {{ t('common.select') }} {{ optionTitle }}
        </button>

        <div v-if="showPopup"
            class="fixed top-0 left-0 w-full h-full bg-gray-500 bg-opacity-50 flex items-center justify-center z-20 h-[80vh]">
            <div class="bg-white rounded shadow-lg p-4 w-1/2">
                <h2 class="text-lg font-semibold mb-2">{{ t('common.select') }} {{ optionTitle }}</h2>

                <label class="block mb-2 flex items-center">
                    <input type="checkbox" @change="selectAll" :checked="allSelected"
                        class="mr-2 form-checkbox h-5 w-5 text-blue-600">
                    {{ t('common.select') }} {{ t('common.select') }}
                </label>

                <div v-for="option in options" :key="option.code" class="mb-1">
                    <label class="flex items-center">
                        <input type="checkbox" :value="option.code" v-model="selectedValues"
                            class="mr-2 form-checkbox h-5 w-5 text-blue-600">
                        {{ option.label }}
                    </label>
                </div>

                <div class="flex justify-end mt-4">
                    <button @click="closePopup(true)"
                        class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-700 focus:outline-none">
                        {{ t('common.accept') }}
                    </button>
                </div>
            </div>
        </div>

        <div v-if="selectedOptions.length > 0"
            class="mt-4 absolute top-full left-0 bg-white flex flex-col gap-2 rounded customers-shadow p-2 w-[550px] z-10">
            <details>
                <summary class="cursor-pointer font-semibold mb-2">{{ t('common.selected') }}: ({{ selectedOptions.length
                    }})</summary>
                <div class="grid grid-cols-3 gap-2">
                    <span v-for="option in selectedOptions" :key="option.code" class="px-2" 
                    :class="{
                        'bg-gray-100': (selectedOptions.indexOf(option) + 1) % 2 === 0, 
                        'bg-white': (selectedOptions.indexOf(option) + 1) % 2 !== 0 
                    }">
                        {{ option.label }}
                    </span>
                </div>
            </details>
        </div>
    </div>
</template>