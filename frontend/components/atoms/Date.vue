<script setup>
import { ref, computed } from 'vue';
import { formatDate, formatDateVerbose } from '~/utils/date';

const props = defineProps({
    date: String,
    class: String
});

const date_formatted = computed(() => {
    return props.date ? formatDate(props.date) : '-';
});

const date_formatted_verbose = computed(() => {
    return props.date ? formatDateVerbose(props.date) : '-';
});

</script>
<template>
    <time :class=props.class :datetime=props.date :title=date_formatted_verbose>{{ date_formatted }}</time>
</template>
    