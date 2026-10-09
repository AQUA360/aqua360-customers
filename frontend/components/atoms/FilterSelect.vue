<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, format, startOfYear, endOfYear, eachDayOfInterval, isWithinInterval } from 'date-fns';
import DatePicker from './DatePicker.vue';

const props = defineProps({
    options: {
        type: Array,
        required: false,
    },
    filters: {
        type: Array,
        required: true,
    },
    multiple: {
        type: Boolean,
        default: true,
    },
    placeholder: {
        type: String,
        default: "Select options",
    },
    selector: {
        type: Boolean,
        default: false,
    },
    textInput: {
        type: Boolean,
        default: false
    },
    defaultOpen: {
        type: Boolean,
        default: false
    },
    initialValue: {
        type: String,
        default: ''
    },
    datePick: {
        type: Boolean,
        default: false,
    },
    plain: {
        type: Boolean,
        default: false,
    },
});

const { te, t } = useI18n();
const emit = defineEmits(['update:modelValue']);

const isDropdownVisible = ref(props.defaultOpen);
const selectedElements = ref([...props.filters]);

const textInputValue = ref(props.initialValue);

const selectedDateRange = ref(null);

const toggleDropdown = () => {
    isDropdownVisible.value = !isDropdownVisible.value;
};

const handleClickOutside = (event) => {
    if (!event.target.closest('.dropdown-container')) {
        isDropdownVisible.value = false;
    }
};

const translateOptionName = (name) => {
    if (!name) return '';
    if (name.startsWith('reading_alert_')) {
        return te(`billing_block.${name}`) ? t(`billing_block.${name}`) : name;
    }
    const blockKey = `billing_block.${name}`;
    const resBlock = te(blockKey) ? t(blockKey) : name;
    if (resBlock !== blockKey) return resBlock;

    const globalKey = name;
    const resGlobal = te(globalKey) ? t(globalKey) : name;
    if (resGlobal !== globalKey) return resGlobal;

    return name;
};

const getTotal = () => {
    if (props.selector) {
        if (props.multiple) {
            return props.placeholder.charAt(0).toUpperCase() + props.placeholder.slice(1) + " (" + selectedElements.value.length + ")";
        }
        return props.placeholder.charAt(0).toUpperCase() + props.placeholder.slice(1);
    }
    const totalTokens = selectedElements.value.map(el => translateOptionName(el.name)).join(', ');
    return totalTokens.length > 20 ? "(" + selectedElements.value.length + ") " + totalTokens.slice(0, 20) + "..." : totalTokens;
};


const handleSelection = (option) => {
    if (props.multiple) {
        const exists = selectedElements.value.find((el) => el.id === option.id);
        if (exists) {
            selectedElements.value = selectedElements.value.filter((el) => el.id !== option.id);
        } else {
            selectedElements.value.push(option);
        }
    } else {
        const exists = selectedElements.value.find((el) => el.id === option.id);
        selectedElements.value = exists ? [] : [option];
        isDropdownVisible.value = false;
    }

    if (props.selector) {
        isDropdownVisible.value = false
    }
    emit('update:modelValue', [...selectedElements.value]);
};

const handleDateRangeSelected = (range) => {
    selectedDateRange.value = range;
    emit('update:modelValue', range);
};

document.addEventListener('click', handleClickOutside);

onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside);
});

watch(
    () => props.filters,
    (newFilters) => {
        selectedElements.value = [...newFilters];
        if (props.datePick && newFilters.length === 0) {
            selectedDateRange.value = null;
        }
    }
);
</script>

<template>
    <div class="relative dropdown-container">
        <button @click="toggleDropdown"
            class="w-full text-left bg-whiterounded focus:outline-none focus:ring focus:ring-blue-300 mx-1 flex items-center gap-2"
            :class="{
                'hover:bg-gray-100 text-gray-400': selector && !plain,
                'border border-sky-500 bg-sky-50 hover:bg-sky-100 text-sky-600 rounded-3xl font-semibold': !selector && !plain,
                'hover:bg-slate-300 rounded text-slate-500': plain
            }">
            <span class="flex items-center">
                <slot name="icon"></slot>
            </span>
            <span class="flex items-center" v-if="textInput"> {{ textInputValue }}</span>
            <span v-else-if="datePick">
                <span v-if="selectedDateRange && selectedDateRange.start_date && selectedDateRange.end_date">
                    {{ selectedDateRange.start_date }}
                    <span class="text-lg">
                        &harr;
                    </span>
                    {{ selectedDateRange.end_date }}
                </span>
                <span v-else>
                    {{ placeholder.charAt(0).toUpperCase() + placeholder.slice(1) }}
                </span>
            </span>
            <span v-else>{{ selectedElements.length ? getTotal() : placeholder.charAt(0).toUpperCase() +
                placeholder.slice(1) }}</span>
        </button>


        <div v-show="isDropdownVisible" class="z-10 absolute bg-white border border-gray-300 rounded shadow-md"
            :class="{ 'dropdown-content': !datePick }">
            <ul>
                <li v-if="textInput" class="p-2 hover:bg-gray-100 flex items-center cursor-pointer">
                    <input type="text" :placeholder="placeholder" v-model="textInputValue"
                        @change="emit('update:modelValue', [textInputValue])" />
                </li>
                <li v-else-if="datePick" class="p-2 flex items-center cursor-pointer">
                    <DatePicker @date-range-selected="handleDateRangeSelected" />
                </li>
                <li v-else v-for="option in options" :key="option.id"
                    class="p-2 hover:bg-gray-100 flex items-center cursor-pointer" @click="handleSelection(option)">
                    <input v-if="multiple" type="checkbox" :checked="selectedElements.some((el) => el.id === option.id)"
                        class="mr-2" />
                    {{ translateOptionName(option.name) }}
                </li>
            </ul>
        </div>

    </div>
</template>

<style scoped>
.dropdown-container {
    position: relative;
    height: 25px !important;
    padding-inline: 3px;
    font-size: 13px !important;
    line-height: 1.5 !important;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
}

.dropdown-container button {
    height: 25px !important;
    padding: 0 10px;
    width: auto;
    font-size: 13px !important;
    line-height: 1.5 !important;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
}

.dropdown-container .dropdown-content {
    position: absolute;
    z-index: 40;
    background-color: white;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
    overflow: auto;
    max-height: 15rem;
    min-width: fit-content;
    white-space: nowrap;
}

.calendar {
    width: 300px;
}

.calendar .days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
}

.calendar .days div {
    padding: 5px;
    text-align: center;
    cursor: pointer;
}

.calendar .days div.highlighted {
    background-color: skyblue;
}
</style>
