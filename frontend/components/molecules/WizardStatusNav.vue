<script setup>
const props = defineProps({
  steps: {
    type: Array,
    required: true,
  },
  currentStep: {
    type: Number,
    required: true,
  },
  maxStep: {
    type: Number,
    required: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  navigable: {
    type: Boolean,
    default: false,
  },
  progressPercent: {
    type: Number,
    default: 88,
  },
  lineInset: {
    type: String,
    default: '6%',
  },
  stepInfoMaxWidth: {
    type: String,
    default: 'max-w-[150px]',
  },
  lockFutureStepsOnly: {
    type: Boolean,
    default: false,
  },
  showDescription: {
    type: Boolean,
    default: true,
  },
});

const emit = defineEmits(['step-click']);

const progressWidth = computed(() => {
  if (props.steps.length <= 1) return '0%';
  return `${(props.maxStep / (props.steps.length - 1)) * props.progressPercent}%`;
});

const isStepDisabled = (index) => {
  if (props.disabled) return true;
  if (props.navigable) {
    if (props.lockFutureStepsOnly) {
      return index > props.maxStep;
    }
    return index > props.maxStep && index !== props.currentStep;
  }
  return index !== props.currentStep;
};

const onStepClick = (index) => {
  if (!props.navigable || isStepDisabled(index)) return;
  emit('step-click', index);
};
</script>

<template>
  <div class="mb-5 px-5 pt-4 pb-2 bg-slate-50/60 rounded-2xl border border-slate-200/50 shadow-sm text-base">
    <div class="flex items-start justify-between relative">
      <div class="absolute top-[22px] h-[3px] bg-slate-200 rounded-full z-0"
        :style="{ left: lineInset, right: lineInset }"></div>
      <div
        class="absolute top-[22px] h-[3px] bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full z-0 transition-all duration-500 ease-out"
        :style="{ left: lineInset, width: progressWidth }"></div>

      <div v-for="(step, index) in steps" :key="index" class="flex flex-col items-center relative z-10 flex-1 group">
        <button :disabled="isStepDisabled(index)"
          class="w-11 h-11 rounded-full flex items-center justify-center font-bold text-sm border-2 transition-all duration-300 relative focus:outline-none disabled:cursor-not-allowed"
          :class="{
            'bg-blue-600 border-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.4)] scale-110': currentStep === index,
            'bg-white border-blue-500 text-blue-600 shadow-sm': index <= maxStep && currentStep !== index,
            'hover:bg-blue-50 hover:scale-105 cursor-pointer': navigable && index <= maxStep && currentStep !== index,
            'bg-slate-100 border-slate-200 text-slate-400': index > maxStep,
          }" @click="onStepClick(index)">
          <Icon v-if="index < currentStep" name="fa6-solid:check" class="w-4 h-4" />
          <Icon v-else :name="step.icon" class="w-4 h-4" />

          <span v-if="currentStep === index"
            class="absolute -top-0.5 -right-0.5 w-3 h-3 bg-blue-400 rounded-full animate-ping opacity-75"></span>
        </button>

        <div class="text-center mt-3 px-1 select-none" :class="stepInfoMaxWidth">
          <span class="block text-[10px] font-bold uppercase tracking-wider transition-colors duration-200" :class="{
            'text-blue-600': currentStep === index,
            'text-slate-400': currentStep !== index,
          }">
            {{ step.label }}
          </span>
          <span class="block text-xs font-semibold text-slate-800 truncate mt-0.5" :title="step.title">
            {{ step.title }}
          </span>
          <span v-if="showDescription" class="block text-[10px] text-slate-400 leading-tight mt-0.5 line-clamp-2"
            :class="{ 'hover:line-clamp-none transition-all duration-300': navigable }" :title="step.description">
            {{ step.description }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
