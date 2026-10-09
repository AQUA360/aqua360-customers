<script setup>
const props = defineProps({
  options: {
    type: Array,
    default: () => [],
  },
  selectedValues: {
    type: Array,
    default: () => [],
  },
  selectedValue: {
    type: [String, Number, null],
    default: null,
  },
  selectionMode: {
    type: String,
    default: 'multiple',
  },
  indicatorType: {
    type: String,
    default: 'radio',
  },
  disabledValues: {
    type: Array,
    default: () => [],
  },
  translateLabels: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['select'])
const { t } = useI18n()

const isMultiple = computed(() => props.selectionMode === 'multiple')
const isCheckbox = computed(() => props.indicatorType === 'checkbox')

const isSelected = (optionValue) => {
  if (isMultiple.value) {
    return props.selectedValues.includes(optionValue)
  }

  return props.selectedValue === optionValue
}

const isDisabled = (optionValue) => props.disabledValues.includes(optionValue)

const onSelect = (optionValue) => {
  if (isDisabled(optionValue)) {
    return
  }
  emit('select', optionValue)
}

const getLabel = (option) => {
  if (props.translateLabels) {
    return t(option.name)
  }
  return option.name
}
</script>

<template>
  <div class="flex gap-3">
    <div v-for="option in options" :key="option.value" @click="onSelect(option.value)"
      class="flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200" :class="[
        isSelected(option.value)
          ? 'cursor-pointer bg-sky-50 ring-1 ring-sky-500'
          : isDisabled(option.value)
            ? 'opacity-50 cursor-not-allowed'
            : 'cursor-pointer hover:bg-gray-50'
      ]">
      <div class="w-3.5 h-3.5 border-2 flex items-center justify-center shrink-0" :class="[
        isCheckbox ? 'rounded-sm' : 'rounded-full',
        isSelected(option.value)
          ? isCheckbox ? 'border-sky-500 bg-sky-500' : 'border-sky-500'
          : 'border-gray-300'
      ]">
        <Icon v-if="isCheckbox && isSelected(option.value)" name="fa6-solid:check" class="text-white" />
        <div v-else-if="!isCheckbox && isSelected(option.value)" class="w-1.5 h-1.5 rounded-full bg-sky-500" />
      </div>
      <span class="text-xs font-medium" :class="[
        isSelected(option.value)
          ? 'text-sky-700'
          : isDisabled(option.value)
            ? 'text-gray-400'
            : 'text-gray-600'
      ]">
        {{ getLabel(option) }}
      </span>
    </div>
  </div>
</template>
