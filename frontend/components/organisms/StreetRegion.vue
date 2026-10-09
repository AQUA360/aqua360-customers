<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: Number,
});

const emit = defineEmits(['close', 'changed']);

const { $StreetApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const saving = ref(false);

const streetName = ref('');

const getData = async () => {
  if (!props.id) return;
  pending.value = true;
  error.value = null;
  try {
    const result = await $StreetApiService.getDetail(props.id);
    data.value = result;
    streetName.value = result.name;
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const save = async () => {
  saving.value = true;
  try {
    await $StreetApiService.patch(props.id, { name: streetName.value });
    toast.success(t('common.correct_save'));
    emit('changed');
    emit('close');
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_save'));
  } finally {
    saving.value = false;
  }
}

watch(() => props.id, () => {
  getData();
});

onMounted(() => {
  getData();
});
</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <div class="p-6">
        <p class="text-red-500">{{ $t('common.error') }}: {{ error.message }}</p>
        <button @click="getData" class="button-default mt-4">{{ $t('common.load_again') }}</button>
      </div>
    </div>
    <div v-else class="pr-6 h-full overflow-y-auto">
      <div class="px-6 py-4">
        <H1Region class="mb-6">{{ $t('address_block.street') }}</H1Region>

        <div v-if="data" class="space-y-6">
          <div class="grid grid-cols-2 gap-6">
            <FieldDetail :label="$t('common.identificator')" :value="data.id" />
            <FieldDetail :label="$t('common.type')" :value="data.type_abbreviation || data.type?.abbreviation" />
            <FieldDetail class="col-span-2" :label="$t('address_block.city')" :value="data.city?.name || data.city_name || data.city" />
            
            <div class="space-y-2">
              <label class="block text-xs font-semibold text-slate-500 uppercase">
                {{ $t('common.name') }}
              </label>
              <input 
                v-model="streetName" 
                type="text" 
                class="input w-full"
                :placeholder="$t('address_block.street')"
              />
            </div>
          </div>

          <div class="pt-6 border-t border-gray-100 flex justify-end gap-3">
            <button @click="emit('close')" class="button-default" :disabled="saving">
              {{ $t('common.cancel') }}
            </button>
            <button @click="save" class="button-primary" :disabled="saving || !streetName">
              <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin mr-2" />
              {{ $t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
