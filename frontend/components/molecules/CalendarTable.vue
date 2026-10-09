<script setup>
import { ref, computed, onMounted } from 'vue';
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, subMonths, addMonths, isSameMonth, isSameDay, isToday } from 'date-fns';
import CalendarTaskRegion from '../organisms/CalendarTaskRegion.vue';

const { t } = useI18n()

const { $CalendarTaskApiService } = useNuxtApp();

const pending = ref(false)
const hoveredDay = ref(null)

const currentDate = ref(new Date());
const selectedDate = ref(new Date());
const month = ref(null);

const data = ref([])
const tasksByDay = ref({})

const showRegion = ref(false);
const isSubRegionOpen = ref(false);     //For future use
const detail = ref(null);

//TODO: MOVE MONTHS TO TRANSLATION UTILS WHEN DONE
const months = ref([
    { code: '01', label: t('date.january') },
    { code: '02', label: t('date.february') },
    { code: '03', label: t('date.march') },
    { code: '04', label: t('date.april') },
    { code: '05', label: t('date.may') },
    { code: '06', label: t('date.june') },
    { code: '07', label: t('date.july') },
    { code: '08', label: t('date.august') },
    { code: '09', label: t('date.september') },
    { code: '10', label: t('date.october') },
    { code: '11', label: t('date.november') },
    { code: '12', label: t('date.december') },
]);

const daysInMonth = computed(() => {
    const firstDayOfMonth = startOfMonth(currentDate.value);
    const lastDayOfMonth = endOfMonth(currentDate.value);

    const firstDayOfWeek = startOfWeek(firstDayOfMonth, { weekStartsOn: 1 });
    const lastDayOfWeek = endOfWeek(lastDayOfMonth, { weekStartsOn: 1 });

    const calendarDays = [];
    let currentDay = firstDayOfWeek;

    while (currentDay <= lastDayOfWeek) {
        calendarDays.push({
            date: currentDay,
            isCurrentMonth: isSameMonth(currentDay, currentDate.value),
            isToday: isToday(currentDay),
            isSelected: isSameDay(currentDay, selectedDate.value),
        });
        currentDay = addDays(currentDay, 1);
    }

    month.value = months.value.find(m => m.code == format(currentDate.value, 'MM'));

    return calendarDays;
});

const getData = async () => {
    pending.value = true;

    try {
        data.value = [];
        const response = await $CalendarTaskApiService.getAll(format(currentDate.value, 'yyyy'), format(currentDate.value, 'MM'));
        data.value = response.results;

        //group data by their set date day
        tasksByDay.value = {}
        tasksByDay.value = data.value.reduce((acc, item) => {
            const dateKey = format(new Date(item.set_date), 'yyyy-MM-dd');
            if (!acc[dateKey]) {
                acc[dateKey] = [];
            }
            acc[dateKey].push(item);
            return acc;
        }, {});

    } catch (err) {
        console.error(err);
    } finally {
        pending.value = false;
    }
}

const hoverDay = (day) => {
    hoveredDay.value = day
}

const previousMonth = () => {
    currentDate.value = subMonths(currentDate.value, 1);
    getData()
};

const nextMonth = () => {
    currentDate.value = addMonths(currentDate.value, 1);
    getData()
};

const selectDate = (day) => {
    selectedDate.value = day.date;
};

const showDetail = (date) => {
    console.log("showDetail")
    console.log(date)
    toggleRegion(false);
    let dateString = format(date, 'yyyy-MM-dd');
    detail.value = dateString;
    toggleRegion(true);
}

const toggleRegion = (force) => {
    showRegion.value = force !== undefined ? force : !showRegion.value;
    if (showRegion.value == false) {
        isSubRegionOpen.value = false;
        detail.value = null
    }
}

const getGridCols = (length) => {
    if (length < 4) {
        return `grid-cols-${length}`;
    }
    else {
        return `grid-cols-[auto,auto,auto,auto]`;
    }
}

/* const getClass = (color, is_done) => {
    let className = 'text-sky-300';
    if (color) {
        className = `text-${color}-500`;
    }
    if (is_done) {
        className += ' line-through';
    }
    console.log("getClass")
    console.log(className)
    return className
} */

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

onMounted(() => {
    getData()

});
</script>

<template>
    <div class="w-100 shadow-md rounded-lg overflow-hidden">
        <div class="flex justify-between items-center p-4 bg-gray-100">
            <button @click="previousMonth" class="focus:outline-none hover:bg-gray-200 p-2 rounded-full">
                &lt;
            </button>
            <span class="text-lg font-semibold">{{ month ? month.label : format(currentDate, 'MM') }}</span>
            <button @click="nextMonth" class="focus:outline-none hover:bg-gray-200 p-2 rounded-full">
                &gt;
            </button>
        </div>

        <div class="grid grid-cols-7 gap-2 p-4">
            <div class="text-center font-medium text-gray-600">{{ t('date.monday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.tuesday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.wednesday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.thursday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.friday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.saturday') }}</div>
            <div class="text-center font-medium text-gray-600">{{ t('date.sunday') }}</div>

            <button v-if="!pending" v-for="day in daysInMonth" :key="day.date" @click="selectDate(day)"
                class="relative text-center py-2 rounded-md focus:outline-none hover:bg-gray-200" :class="{
                    'text-gray-900': day.isCurrentMonth,
                    'text-gray-400': !day.isCurrentMonth,
                    'bg-blue-100': day.isToday,
                    'bg-blue-300 text-white': day.isSelected,
                }" @mouseenter="hoverDay(day)" @mouseleave="hoveredDay = null">
                {{ format(day.date, 'dd') }}
                <div v-if="format(day.date, 'yyyy-MM-dd') in tasksByDay" class="grid gap-1 items-center justify-items-center"
                    :class="getGridCols(tasksByDay[format(day.date, 'yyyy-MM-dd')].length)">
                    <div v-for="task in tasksByDay[format(day.date, 'yyyy-MM-dd')]" :key="task.id" class="flex items-center">
                        <Icon v-show="!task.task_done" name="fa6-solid:circle" class="text-xs"
                            :class="task.color ? 'text-' + task.color + '-500' : 'text-sky-500'" />
                        <Icon v-show="task.task_done" name="fa6-regular:circle-check" class="text-xs"
                            :class="task.color ? 'text-' + task.color + '-500' : 'text-sky-500'" />
                    </div>

                </div>
                <!-- <div v-if="hoveredDay">
                    {{ format(hoveredDay.date, 'dd') == format(day.date, 'dd') ? 'SI' : 'NO' }}
                </div>
                <div v-else>
                    NO
                </div> -->
                <div v-show="hoveredDay && format(hoveredDay.date, 'yyyy-MM-dd') == format(day.date, 'yyyy-MM-dd')"
                    class="absolute p-2 top-0 left-0 text-xs text-slate-400 mr-3">
                    <div class="bg-white rounded-md customers-shadow p-1 flex items-center">
                        <button class="default-xs h-3 w-3 rounded-full hover:bg-slate-200"
                            @click="showDetail(day.date)">
                            <abbr :title="t('dashboard.day_check')">
                                <Icon name="fa6-solid:eye" class="text-slate-500 text-xs p-1" />
                            </abbr>
                        </button>
                    </div>
                </div>
            </button>
            <div v-else>
                <AtomsSkeleton class="w-full" :height="5" :is_calendar="true" />
            </div>

        </div>
        <div v-if="showRegion" role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 z-10 ease py-2 text-base bg-white"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="toggleRegion(false)"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <CalendarTaskRegion v-if="detail" :current_date="detail" :isSubRegionOpen="isSubRegionOpen"
                    @show-subregion="handleSubRegionEvent" @changed="getData" />
            </div>
        </div>
    </div>
</template>
