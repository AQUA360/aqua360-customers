<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import Draggable from 'vuedraggable';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const { $OrderReasonApiService } = useNuxtApp();

const emit = defineEmits(['update:modelValue']);

const columnClass = ref('grid-cols-[35px,120px,1fr]');

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
    const dataResponse = await $OrderReasonApiService.getAll();
    items.value = dataResponse.results;
    pending.value = false;
    error.value = null;
  } 
  catch (err) {
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
        <p>Error: {{ error.message }}</p>
        <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
            {{ $t('common.load_again') }}
        </button>
        </p>
    </div>
    <div v-else>
        <H1Region class="mb-3">{{ $t('order_block.reasons') }}</H1Region>
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
                        </div>
                    </template>
                </Draggable>
            </div> <!-- end items -->
        </div> <!-- end if items -->
    </div>
</template>