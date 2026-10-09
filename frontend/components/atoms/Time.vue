<template>
<time :class=props.class :datetime=props.time :title=time_formatted_verbose>{{ time_formatted }}</time>
</template>

<script setup>
import { ref, computed } from 'vue';
import { formatDate, formatDateVerbose } from '~/utils/date';

const props = defineProps({
    time: String,
    class: String
});

const time_formatted = computed(() => {
    return props.time ? formatDate(props.time) : '-';
});

const time_formatted_verbose = computed(() => {
    return props.time ? formatDateVerbose(props.time) : '-';
});

</script>
