<script setup>
import { ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';

import AddBillingRange from '../molecules/AddBillingRange.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  step: Object,
  isSubRegion: Boolean,
});

const { $ClaimRequestApiService } = useNuxtApp();

const pending = ref(false);
const error = ref(null);
const data = ref(null);

const showRegion = ref(false);

const emit = defineEmits(['show-detail']);

const getData = async () => {
  if (props.step) {
    data.value = props.step;
  }
};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
};

watch(
  () => props.id,
  () => {
    getData();
  }
);

onMounted(async () => {
  await getData();
});


const stepsInOrder = computed(() => {
  if (!data.value) {
    return [];
  }

  return [...data.value.previous_steps, data.value, ...data.value.related_steps];
});
</script>

<template>
  <div class="region__content">
    <div>
      <div v-if="pending">
        <p>{{ $t('common.loading') }}...</p>
      </div>
      <div v-else-if="error">
        <p>{{ $t('common.error') }}: {{ error.message }}</p>
        <p>
          <button @click="getData" class="underline text-sky-500 hover:no-underline">
            {{ $t('common.load_again') }}
          </button>
        </p>
      </div>
      <div v-else>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-100">
              <tr>
                <th scope="col" class="px-4 py-2 text-left text-sm font-bold text-slate-800 tracking-wider">
                  {{ t('billing_block.step') }}
                </th>
                <th scope="col" class="px-4 py-2 text-left text-sm font-bold text-slate-800 tracking-wider">
                  {{ t('common.action') }}
                </th>
                <th scope="col" class="relative px-4 py-2">
                  <span class=""></span>
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(step, index) in stepsInOrder" :key="step.id" :class="{ 'bg-yellow-50': step === data }">
                <td class="px-4 py-2 whitespace-nowrap">
                  <div class="text-sm text-gray-900">
                    {{ index + 1 }} - {{ step.name }}
                  </div>
                </td>
                <td class="px-4 py-2 whitespace-nowrap">
                  <div class="text-sm text-slate-500">
                    <span v-if="step.document_type_name || step.document_type">
                      {{ step.document_type_name? step.document_type_name : step.document_type.name }}
                    </span>
                    <span v-else-if="step.order_type_name || step.order_type">
                      {{ step.order_type_name? step.order_type_name : step.order_type.name }}
                    </span>
                    <span v-else class="italic">
                      {{ t('order_block.no_action_assigned') }}
                    </span>
                  </div>
                </td>
                <td v-if="!isSubRegion" class="px-4 py-2 whitespace-nowrap text-right text-sm font-medium">
                  <button class="bg-white py-1 px-2 mr-2 border border-slate-400 rounded-lg hover:bg-gray-100"
                  @click="showDetail('ClaimStepEdit', step.id)">
                    <Icon name="fa6-solid:pencil" />
                  </button>
                  <!-- TODO: CHECK IF STEPS ARE FLEXIBLE AND EDITABLE -->
                  <!-- <button class="bg-red-500 text-white py-1 px-2 border border-slate-400 rounded-lg hover:bg-red-600">
                    <Icon name="fa6-solid:trash" />
                  </button> -->
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
