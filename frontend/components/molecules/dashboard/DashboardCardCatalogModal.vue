<script setup>
import { useI18n } from 'vue-i18n';
import { DASHBOARD_CARDS } from '~/utils/dashboardCards';

// Catàleg de cards per afegir al dashboard (només les que l'usuari té permís de veure).
const open = defineModel('open', { type: Boolean, default: false });
const props = defineProps({
  cards: { type: Array, default: () => [] },
  // Claus ja presents al dashboard, per indicar-ho (es poden repetir amb una altra configuració)
  usedKeys: { type: Array, default: () => [] },
});
const emit = defineEmits(['add']);

const { t } = useI18n();

const add = (card) => {
  emit('add', card);
  open.value = false;
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="open = false" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" @click="open = false">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" @click="open = false">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <p class="text-base font-semibold text-slate-700 mb-4 pr-8">{{ t('home_dashboard.add_card') }}</p>
          <ul class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[60vh] overflow-y-auto">
            <li v-for="card in cards" :key="card.key">
              <button type="button" @click="add(card)"
                class="w-full h-full flex items-start gap-3 p-3 text-left rounded-md border border-slate-200 hover:border-sky-300 hover:bg-sky-50">
                <Icon :name="DASHBOARD_CARDS[card.key]?.icon || 'fa6-solid:square'" class="text-slate-400 mt-0.5 shrink-0" />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-700">
                    {{ t(`home_dashboard.cards.${card.key}.title`) }}
                    <span v-if="usedKeys.includes(card.key)" class="text-xs font-normal text-slate-400 ml-1">({{ t('home_dashboard.already_added') }})</span>
                  </span>
                  <span class="block text-xs text-slate-500">{{ t(`home_dashboard.cards.${card.key}.description`) }}</span>
                </span>
              </button>
            </li>
          </ul>
          <div class="flex justify-end gap-2 mt-4">
            <button type="button" class="button-default" @click="open = false">{{ t('common.cancel') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
