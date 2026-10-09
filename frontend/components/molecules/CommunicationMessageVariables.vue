<script setup>
import { getMessageVariableGroups } from '~/utils/messages'

const { t } = useI18n()

const props = defineProps({
    no_contracts: {
        type: Boolean,
        default: false
    },
    open: {
        type: Boolean,
        default: true
    }
})

const emit = defineEmits(['insert'])

const variableGroups = computed(() => getMessageVariableGroups(t, props.no_contracts))
</script>

<template>
    <details class="border-t border-gray-200 group" :open="open">
        <summary class="flex items-center mb-3 py-3 px-1 hover:bg-sky-50 cursor-pointer list-none gap-2">
            <Icon name="fa6-solid:angle-right"
                class="w-4 h-4 text-sky-600 transition-transform duration-200 group-open:rotate-90" />
            <Icon name="fa6-solid:code" class="w-4 h-4 text-slate-600" />
            <h4 class="text-sm font-semibold text-slate-700">{{ t('customer_service_block.available_variables') }}
            </h4>
        </summary>
        <div>
            <p class="text-xs text-slate-500 mb-3">{{ t('informative_block.info_click_variable_to_insert') }}</p>
            <div
                class="inline-flex w-fit mb-2 max-w-full items-start gap-1.5 rounded-md border px-2 py-1 text-[11px] leading-4 border-amber-200 bg-amber-50 text-amber-800">
                <Icon name="fa6-solid:circle-info" class="mt-0.5 h-3 w-3 flex-shrink-0" />
                <span>{{ t('informative_block.info_individual_group') }}</span>
            </div>
            <div v-for="group in variableGroups" :key="group.key" class="space-y-1 mb-3">
                <span class="text-xs flex items-center font-medium"
                    :class="group.warning ? 'border-amber-200 text-amber-700' : 'text-slate-500'">
                    {{ group.title }}</span>
                <div class="flex flex-wrap gap-2 items-center">
                    <button v-for="variable in group.variables" :key="variable.token" type="button"
                        @click="emit('insert', variable.token)"
                        class="group/variable inline-flex items-center rounded-md border px-2.5 py-1 text-xs transition-colors duration-200"
                        :class="group.warning ? 'border-amber-500 bg-amber-50 text-amber-800 hover:bg-amber-100' : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'"
                        :title="variable.token" :aria-label="`${variable.label} (${variable.token})`">
                        <span class="inline-grid whitespace-nowrap">
                            <span aria-hidden="true"
                                class="col-start-1 row-start-1 py-0.5 font-medium transition-opacity duration-150 group-hover/variable:opacity-0">
                                {{ variable.label }}
                            </span>
                            <span aria-hidden="true"
                                class="col-start-1 row-start-1 font-mono text-[11px] transition-opacity duration-150 opacity-0 group-hover/variable:opacity-100"
                                :class="group.warning ? 'text-amber-700' : 'text-slate-500'">
                                {{ variable.token }}
                            </span>
                        </span>
                    </button>
                </div>
                <div v-if="group.notes.length" class="flex flex-col gap-1">
                    <div v-for="note in group.notes" :key="note.text"
                        class="inline-flex w-fit max-w-full items-start gap-1.5 rounded-md border px-2 py-1 text-[11px] leading-4"
                        :class="note.tone === 'warning'
                            ? 'border-amber-200 bg-amber-50 text-amber-800'
                            : 'border-sky-200 bg-sky-50 text-sky-700'">
                        <Icon name="fa6-solid:circle-info" class="mt-0.5 h-3 w-3 flex-shrink-0" />
                        <span>{{ note.text }}</span>
                    </div>
                </div>
            </div>
        </div>
    </details>
</template>
