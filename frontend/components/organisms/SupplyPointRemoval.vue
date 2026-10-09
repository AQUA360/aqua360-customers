<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
});

const emits = defineEmits(['save-success', 'save-error']);

const router = useRouter();
const { $SupplyPointApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

// Variables per als camps de data i motiu de baixa
const removal_at = ref('');
const removal_reason = ref('');

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $SupplyPointApiService.getDetail(props.id);
    data.value = result;
    // Assignar valors als camps si existeixen
    removal_at.value = result.removal_at || new Date().toISOString().split('T')[0];
    removal_reason.value = result.removal_reason || '';
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

// Funció per guardar les dades
const saveData = async () => {
  try {
    pending.value = true;
    await $SupplyPointApiService.deactivate(props.id, removal_at.value, removal_reason.value );
    // Emitir esdeveniment de guardat amb èxit
    emits('save-success');
  } catch (err) {
    // Emitir esdeveniment d'error
    emits('save-error', err);
  } finally {
    pending.value = false;
  }
};

watch(() => props.id, () => {
  getData();
});

getData();

</script>

<template>
  <div class="region__content">

    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{t('common.error')}}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button></p>
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('service_block.supply_point_termination') }}</H1Region>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <form @submit.prevent="saveData">
          <div class="mb-2">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.termination_date') }}</label>
            <input type="date" v-model="removal_at" class="input" />
          </div>
          <div class="mb-2">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('order_block.reason') }}</label>
            <input type="text" v-model="removal_reason" class="input" />
          </div>
          <div class="mt-4">
            <button type="submit" class="button-primary"><Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
