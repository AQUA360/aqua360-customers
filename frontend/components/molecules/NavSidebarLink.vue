<script setup>
/**
 * Link of the side menu, with a star to add it to or remove it from the
 * favourites (only with the menu expanded).
 */
const props = defineProps({
  item: { type: Object, required: true },
  active: { type: Boolean, default: false },
  iconsOnly: { type: Boolean, default: false },
  favorite: { type: Boolean, default: false },
  hoverClass: { type: String, default: '' },
  highlightClass: { type: String, default: '' },
  newDailyDocuments: { type: Number, default: 0 },
  dailyDocumentSubmissionErrors: { type: Number, default: 0 },
});

defineEmits(['toggle-favorite']);

const hasDailyDocErrors = computed(() =>
  props.item.dailyDocumentsBadge && props.dailyDocumentSubmissionErrors > 0
);
const hasNewDailyDocs = computed(() =>
  props.item.dailyDocumentsBadge && props.newDailyDocuments > 0
);
const hasDailyDocActivity = computed(() => hasDailyDocErrors.value || hasNewDailyDocs.value);
const dailyDocBadgeCount = computed(() =>
  hasDailyDocErrors.value ? props.dailyDocumentSubmissionErrors : props.newDailyDocuments
);
</script>

<template>
  <div class="group relative">
    <NuxtLink :to="item.to"
      class="flex w-full items-center px-3 py-2 leading-[14px] text-slate-600 rounded"
      :class="[hoverClass, {
        [highlightClass]: active,
        'font-[750]': hasDailyDocActivity,
        'font-medium': !hasDailyDocActivity,
        'justify-center': iconsOnly,
        'pr-7': !iconsOnly,
      }]"
      :title="iconsOnly ? item.label + (hasDailyDocActivity ? ` (${dailyDocBadgeCount})` : '') : undefined">
      <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': iconsOnly }">
        <span class="relative flex w-6 shrink-0 justify-center">
          <img v-if="item.image" :src="item.image" alt="" class="h-4 grayscale brightness-75 opacity-70" />
          <Icon v-else :name="item.icon" class="text-slate-500"
            :class="{ 'text-red-500': hasDailyDocErrors }" />
          <span
            v-if="hasDailyDocErrors"
            class="pointer-events-none absolute -top-0.5 -right-0.5 flex size-2.5"
            aria-hidden="true">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"></span>
            <span class="relative inline-flex size-2.5 rounded-full bg-red-500"></span>
          </span>
          <span
            v-else-if="hasNewDailyDocs"
            class="pointer-events-none absolute -top-0.5 -right-0.5 flex size-2"
            aria-hidden="true">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
            <span class="relative inline-flex size-2 rounded-full bg-sky-500"></span>
          </span>
        </span>
        <span v-show="!iconsOnly" class="truncate"
          :class="{ 'text-red-600': hasDailyDocErrors }">{{ item.label }}</span>
        <span v-if="hasDailyDocErrors" v-show="!iconsOnly" class="text-red-600 font-bold">({{ dailyDocumentSubmissionErrors }})</span>
        <span v-else-if="item.dailyDocumentsBadge" v-show="!iconsOnly">({{ newDailyDocuments }})</span>
      </div>
    </NuxtLink>
    <button v-if="!iconsOnly" type="button"
      class="absolute right-1 top-1/2 -translate-y-1/2 px-1 text-xs focus:opacity-100"
      :class="favorite ? 'text-amber-400 hover:text-amber-500' : 'text-slate-400 hover:text-amber-400 opacity-0 group-hover:opacity-100'"
      :title="favorite ? $t('common.remove_favorite') : $t('common.add_favorite')"
      :aria-pressed="favorite"
      @click.stop.prevent="$emit('toggle-favorite')">
      <Icon :name="favorite ? 'fa6-solid:star' : 'fa6-regular:star'" />
    </button>
  </div>
</template>
