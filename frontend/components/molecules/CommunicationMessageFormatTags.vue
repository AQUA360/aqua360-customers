<script setup>
import { getMessageFormatTagMarker, getMessageFormatTags } from '~/utils/messages'

const { t } = useI18n()

defineProps({
    open: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['apply'])

const formatTags = computed(() => getMessageFormatTags(t))
</script>

<template>
    <details class="border-t border-gray-200 group" :open="open">
        <summary class="flex items-center mb-3 py-3 px-1 hover:bg-sky-50 cursor-pointer list-none gap-2">
            <Icon name="fa6-solid:angle-right"
                class="w-4 h-4 text-sky-600 transition-transform duration-200 group-open:rotate-90" />
            <Icon name="fa6-solid:text-height" class="w-4 h-4 text-slate-600" />
            <h4 class="text-sm font-semibold text-slate-700">{{ t('customer_service_block.available_format_tags') }}
            </h4>
        </summary>
        <div>
            <p class="text-xs text-slate-500 mb-3">{{ t('informative_block.info_click_format_tag_to_apply') }}</p>
            <div class="flex flex-wrap gap-2 items-center">
                <button v-for="tag in formatTags" :key="tag.key" type="button" @click="emit('apply', tag.token)"
                    class="group/tag inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs text-slate-700 transition-colors duration-200 hover:bg-slate-200"
                    :title="getMessageFormatTagMarker(tag.token)"
                    :aria-label="`${tag.label} (${getMessageFormatTagMarker(tag.token)})`">
                    <Icon :name="tag.icon" class="h-3 w-3 text-slate-600" />
                    <span class="inline-grid whitespace-nowrap">
                        <span aria-hidden="true"
                            class="col-start-1 row-start-1 py-0.5 font-medium transition-opacity duration-150 group-hover/tag:opacity-0">
                            {{ tag.label }}
                        </span>
                        <span aria-hidden="true"
                            class="col-start-1 row-start-1 font-mono text-[11px] text-slate-500 transition-opacity duration-150 opacity-0 group-hover/tag:opacity-100">
                            {{ getMessageFormatTagMarker(tag.token) }}
                        </span>
                    </span>
                </button>
            </div>
        </div>
    </details>
</template>
