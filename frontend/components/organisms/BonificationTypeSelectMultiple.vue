<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $BonificationTypeApiService } = useNuxtApp();

import { VariableTypeDataTypeChoices, VariableTypeApplicationChoices } from '~/utils/variable-type';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[35px,1fr,2fr]');

const entity = ref('contract/bonification-type');
const apiUrl = ref(`${apiHost}/${entity.value}/`);
const pending = ref(true);
const error = ref(null);
const items = ref([]);

const selectedItems = computed({
  get() {
    return props.modelValue;
  },
  set(value) {
    emit('update:modelValue', value);
  }
});

const getData = async () => {
  pending.value = true;
  try {
    const dataResponse = await $BonificationTypeApiService.getAll();
    items.value = dataResponse.results;
    pending.value = false;
    error.value = null;
  } catch (err) {
    error.value = err;
    pending.value = false;
  }
}

onMounted(() => {
  getData();
});
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>{{t('common.error')}}: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}
      </button>
    </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ $t('contract_block.variable_types') }}</H1Region>
    <!-- Total -->
    <div v-if="items">
      <div id="config__totals" class="text-sm text-right text-slate-500">
        {{ $t('common.total') }}: {{ items.length }}
      </div>
      <div id="config__items" class="text-base">
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }} </span>
        </div>
        <Draggable v-model="items" itemKey="id" handle=".handle-move" class="dragArea">
          <template #item="{ element: item }">
            <div :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white']">
              <span class="text-slate-900 p-1 border-r">
                <input type="checkbox" :value="item.id" v-model="selectedItems" />
              </span>
              <span class="text-slate-900 p-1 border-r cursor-pointer relative">
                {{ item.token }}
              </span>
              <span class="text-slate-900 p-1 border-r font-semibold">
                {{ item.name }}
              </span>
              <!-- <div v-if="item.variable_types.length > 0" class="col-span-3 flex items-center gap-x-2">
                <span v-for="variable in item.variable_types" :key="variable.id">
                  {{ variable.name }}
                </span>
              </div> -->
            </div>
          </template>
        </Draggable>

      </div><!-- end items -->
    </div><!-- end if items -->
  </div>
</template>
