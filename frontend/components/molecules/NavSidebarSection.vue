<script setup>
/**
 * Section of the side menu with a title that folds and unfolds its links.
 * With the menu reduced to icons the title is hidden, so the links are
 * always shown (otherwise a folded section could not be unfolded).
 */
defineProps({
  title: { type: String, required: true },
  folded: { type: Boolean, default: false },
  iconsOnly: { type: Boolean, default: false },
});

defineEmits(['toggle']);
</script>

<template>
  <div class="mb-2">
    <button v-show="!iconsOnly" type="button"
      class="group flex w-full items-center gap-1 rounded p-1 text-left text-sm text-slate-400 hover:text-slate-600"
      :aria-expanded="!folded" :title="folded ? $t('common.unfold_section') : $t('common.fold_section')"
      @click="$emit('toggle')">
      <span class="truncate flex-1">{{ title }}</span>
      <Icon name="fa6-solid:chevron-down" class="shrink-0 text-xs transition-transform"
        :class="folded ? '-rotate-90' : 'opacity-0 group-hover:opacity-100'" />
    </button>
    <div v-show="iconsOnly || !folded">
      <slot />
    </div>
  </div>
</template>
