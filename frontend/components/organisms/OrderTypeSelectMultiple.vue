<script setup>
import AppLoading from '~/components/atoms/AppLoading.vue';
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $OrderTypeApiService } = useNuxtApp();

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);
const columnClass = ref('grid-cols-[35px,120px,1fr]');

const entity = ref('order/order-type');
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
    const dataResponse = await $OrderTypeApiService.getAll();
    items.value = dataResponse.results;
    pending.value = false;
    error.value = null;
  } catch (err) {
    error.value = err;
    pending.value = false;
  }
}

const handleRefreshList = () => {
  getData();
}

const handleChanged = () => {
  // Aquí pots afegir qualsevol lògica addicional després d'un canvi
}

const newItem = () => {
  const item_new = document.getElementById('item_new');
  item_new.classList.remove('hidden');
  item_new.querySelector('.edit_field_dialog button').click();
}

onMounted(() => {
  getData();
});
</script>

<template>
  <AppLoading v-if="pending" :text="$t('common.loading')" />
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}
      </button>
    </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ $t('order_block.order_types_long') }}</H1Region>
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
            </div>
          </template>
        </Draggable>

        <div id="item_new" :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white', 'hidden']">
          <span class="text-slate-900 p-1 border-r"><!-- move --></span>
          <span class="text-slate-900 p-1 border-r">
            <EditFieldDialog :entity="entity" property="token" :id="0" value="" @refreshList="handleRefreshList" @changed="handleChanged">
            </EditFieldDialog>
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- name -->
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- type -->
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- app -->
          </span>
          <span class="text-slate-900 p-1 flex gap-2">
            <button class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-500" />
            </button>
          </span>
        </div>
        <div class="footering">
          <button @click="newItem"
            class="block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
          </button>
        </div>
      </div><!-- end items -->
    </div><!-- end if items -->
  </div>
</template>
