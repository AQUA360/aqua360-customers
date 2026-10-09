<script setup>
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, startOfYear, endOfYear, format } from 'date-fns';
import { useI18n } from 'vue-i18n';
import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css'

const { t, locale } = useI18n();
const emit = defineEmits(['date-range-selected']);

const dateRange = ref({ start: new Date(), end: new Date() });

const emitDateRange = (newRange, clean_date) => {
    let formattedRange = {
        start_date: null,
        end_date: null,
    };

    formattedRange.start_date = newRange[0] ? format(newRange[0], 'yyyy-MM-dd') : null;
    formattedRange.end_date = newRange[1] ? format(newRange[1], 'yyyy-MM-dd') : null;

    dateRange.value = newRange;
    if (clean_date) formattedRange = { start_date: null, end_date: null };
    emit('date-range-selected', formattedRange);
};

const selectPreset = (preset) => {
    const today = new Date();
    let start, end;
    let clean_date = false

    switch (preset) {
        case 'none':
            start = new Date();
            end = new Date();
            clean_date = true
            break;
        case 'thisWeek':
            start = startOfWeek(today, { weekStartsOn: 1 });
            end = endOfWeek(today, { weekStartsOn: 1 });
            break;
        case 'thisMonth':
            start = startOfMonth(today);
            end = endOfMonth(today);
            break;
        case 'thisQuarter': {
            const currentMonth = today.getMonth();
            const quarterStartMonth = Math.floor(currentMonth / 3) * 3;
            start = new Date(today.getFullYear(), quarterStartMonth, 1);
            end = new Date(
                today.getFullYear(),
                quarterStartMonth + 3,
                0
            );
            break;
        }
        case 'prevQuarter': {
            const currentMonth = today.getMonth();
            const quarterStartMonth = Math.floor(currentMonth / 3) * 3;
            start = new Date(today.getFullYear(), quarterStartMonth - 3, 1);
            end = new Date(
                today.getFullYear(),
                quarterStartMonth,
                0
            );
            break;
        }
        case 'thisYear':
            start = startOfYear(today);
            end = endOfYear(today);
            break;
        case 'prevYear':
            start = startOfYear(new Date(today.getFullYear() - 1, 0, 1));
            end = endOfYear(new Date(today.getFullYear() - 1, 0, 1));
            break;
    }

    dateRange.value = { start, end };
    emitDateRange([start, end], clean_date);
};

onMounted(() => {

});

</script>

<template>
    <div class="date-picker">
        <VueDatePicker v-model="dateRange" inline auto-apply range :enable-time-picker="false" :locale="locale"
            @update:model-value="emitDateRange" />
        <div class="grid grid-cols-2 gap-2 mt-2">
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('thisWeek')">
                {{ t('date.this_week') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('thisMonth')">
                {{ t('date.this_month') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('thisQuarter')">
                {{ t('date.this_quarter') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('prevQuarter')">
                {{ t('date.previous_quarter') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('thisYear')">
                {{ t('date.this_year') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('prevYear')">
                {{ t('date.previous_year') }}
            </button>
            <button
                class="px-1 text-sm font-semibold text-sky-700 bg-white border border-sky-300 rounded-full shadow-sm hover:bg-sky-50 active:bg-sky-100 transition duration-200 ease-in-out"
                @click="selectPreset('none')">
                {{ t('common.remove_selection') }}
            </button>
        </div>

    </div>
</template>

<style scoped>
.date-picker {
    padding: 10px;
}
</style>