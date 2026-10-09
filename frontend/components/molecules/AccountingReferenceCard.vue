<script setup>
defineProps({
  index: {
    type: String,
    required: true,
  },
  icon: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  accent: {
    type: String,
    required: true,
  },
  accentSoft: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['check']);

const { t } = useI18n();
</script>

<template>
  <section class="w-full max-w-[280px]">
    <div class="relative flex flex-col items-center rounded-md border bg-white p-4 transition-colors" :style="{
      '--accent': accent,
      '--accent-soft': accentSoft,
      borderColor: 'var(--accent-soft)',
    }">
      <span class="absolute left-3 top-2.5 font-mono text-[10px] font-bold tracking-[0.14em]"
        :style="{ color: 'var(--accent-soft)' }">
        {{ index }}
      </span>
      <span class="absolute right-0 top-0 h-8 w-1 rounded-bl-md rounded-tr-md"
        :style="{ backgroundColor: 'var(--accent)' }" />

      <div class="relative mb-2 flex h-12 w-12 items-center justify-center">
        <span class="absolute left-0 top-0 h-4 w-4 border-l-2 border-t-2 border-gray-200" />
        <span class="absolute right-0 top-0 h-4 w-4 border-r-2 border-t-2 border-gray-200" />
        <span class="absolute bottom-0 left-0 h-4 w-4 border-b-2 border-l-2 border-gray-200" />
        <span class="absolute bottom-0 right-0 h-4 w-4 border-b-2 border-r-2 border-gray-200" />
        <Icon :name="icon" class="size-6" :style="{ color: accent }" />
      </div>

      <h2 class="mb-1 text-center text-base font-bold text-sky-950">
        {{ title }}
      </h2>
      <!-- <p class="mb-3 line-clamp-1 max-w-xs text-center text-sm leading-snug text-slate-500" :title="description">
        {{ description }}
      </p> -->

      <button type="button"
        class="inline-flex items-center justify-center rounded-md bg-[var(--accent-soft)] px-4 py-1.5 text-sm font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-60"
        :disabled="loading" @click="emit('check')">
        {{ t('common.check') }}
      </button>
    </div>
  </section>
</template>
