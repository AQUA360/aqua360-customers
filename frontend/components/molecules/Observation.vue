<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n();

const props = defineProps({
    id: Number,
    object: Object,
    user: String,
    datetime: String,
    observation: String,
    status_name: String,
    allow_mark: Boolean
});

const emit = defineEmits(['delete:observation', 'mark:observation']);

const deleteObservation = () => {
    emit('delete:observation', props.id)
}

const markObservation = () => {
    emit('mark:observation', props.object);
}

</script>
<template>
    <article class="p-2 text-base bg-white rounded-lg group hover:bg-black hover:bg-opacity-10 relative"
    :class="{ 'bg-yellow-50': props?.object?.is_important }">
        <footer class="flex justify-between items-center relative pt-1">
            <div class="flex items-center mb-1">
                <p v-if="props.user?.trim() != ''" class="text-sm text-gray-700 mr-3">{{ props.user }}</p>
                <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
                <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
                    <TimeRelative :datetime=props.datetime></TimeRelative>
                </p>
                <Icon v-if="props?.object?.is_important" name="fa6-solid:circle-exclamation" class="ml-2 w-3 h-3 text-orange-500" />
            </div>
            <div>
                <span class="text-slate-400 text-sm">{{ formatDateTime(props.datetime) }}</span>
            </div>
        </footer>
        <button
            :class="{ 'top-[40px]': props.object.status_name, 'top-4': !props.object.status_name }"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-2 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
            @click="deleteObservation">
            <Icon name="fa6-solid:trash" />
        </button>
        <button v-if="props.allow_mark"
            :class="{ 'top-[40px]': props.object.status_name, 'top-4': !props.object.status_name }"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-10 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
            @click="markObservation">
            <Icon name="fa6-solid:exclamation" />
        </button>
        
        <div v-if="props.object.status_name" class="text-base mb-1 text-gray-500 flex items-center gap-2 font-semibold">
            <span>&rarr;</span> 
            <span>{{ props.object.status_name }}</span>
        </div>
        <p class="text-base text-gray-700 break-words whitespace-pre-wrap">{{ props.observation }}</p>
    </article>
</template>