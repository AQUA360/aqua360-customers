<script setup>

import { DurationTypeChoices } from '~/utils/claim-request';

const { t } = useI18n();
const props = defineProps({
    value: {
        type: Object,
        required: true
    }
});

const displayValue = computed(() => {
    if (!props.value) return ''
    let duration = props.value.duration
    let days = props.value.duration === 1 ? t('date.day') : t('date.days')
    let duration_word = t(DurationTypeChoices[props.value.duration_type])
    let duration_type = duration_word.toLowerCase()
    return `${duration} ${days} ${duration_type}`
});
</script>

<template>
    <span class="text-black-900">{{ displayValue }}</span>
</template>