<script setup>
import { useI18n } from 'vue-i18n';
import H1 from '~/components/atoms/H1.vue';
import AddReadings from '~/components/molecules/AddReadings.vue';

const PENDING_READING_DOCUMENT_KEY = 'avsis.pendingReadingDocument';

const { t } = useI18n();
const route = useRoute();

const safeReturnTo = computed(() => {
  const value = route.query.returnTo;
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) {
    return '/reading/readings';
  }
  return value;
});

const goBack = () => {
  navigateTo(safeReturnTo.value);
};

const onProcessed = (document) => {
  const returnTo = route.query.returnTo;
  if (typeof returnTo === 'string' && returnTo.startsWith('/') && !returnTo.startsWith('//')) {
    try {
      sessionStorage.setItem(PENDING_READING_DOCUMENT_KEY, JSON.stringify(document));
    } catch (err) {
      console.error(err);
    }
    navigateTo(returnTo);
    return;
  }
  navigateTo('/reading/readings');
};

const onClose = () => {
  goBack();
};
</script>

<template>
  <div class="text-base p-4 max-w-6xl mx-auto">
    <div class="flex items-center gap-4 mb-6">
      <button
        type="button"
        class="p-2 hover:bg-slate-100 rounded-full transition-colors"
        :title="t('common.close')"
        :aria-label="t('common.close')"
        @click="goBack"
      >
        <Icon name="fa6-solid:arrow-left" class="text-slate-500" />
      </button>
      <H1>{{ t('common.add') }} {{ t('readings') }}</H1>
    </div>

    <AddReadings :show-title="false" @on-processed="onProcessed" @close="onClose" />
  </div>
</template>
