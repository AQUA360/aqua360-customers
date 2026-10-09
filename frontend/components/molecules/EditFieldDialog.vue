<script setup>
import { ref, watch } from 'vue';
const { $apiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  entity: String,
  property: String,
  id: Number,
  value: String,
  inputClass: String,
  parent_entity: String,
  parent_id: Number,
  related_id: Number,
  maxlength: Number,
});

const ident = ref([props.entity, props.property, props.id].join('_'));
const dialog = ref(null);
const inputValue = ref(props.value);

watch(() => props.value, (newVal) => {
  inputValue.value = newVal;
});

function openDialog() {
  if (ident.value != null && ident.value != '') {
    let wrapper = document.getElementById(ident.value);
    var bodyRect = document.body.getBoundingClientRect();
    var elemRect = wrapper.getBoundingClientRect();
    var offset_top = elemRect.top - bodyRect.top;
    var offset_left = elemRect.left - bodyRect.left;

    dialog.value.style.position = "absolute";
    dialog.value.style.top = offset_top + "px";
    dialog.value.style.left = offset_left + "px";
    dialog.value.showModal();
    wrapper.querySelector('form input[type=text]').style.width = (elemRect.width + 10) + 'px';
  }
}

function closeDialog() {
  dialog.value.close();
}

function checkDialogClick(event) {
  const rect = dialog.value.querySelector('input[type=text]').getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
    closeDialog();
  }
}

function submitToken() {
  closeDialog();
}

function onDialogClose() {
  const isEmpty = inputValue.value == '' || !inputValue.value;
  if (isEmpty && props.id == 0) {
    // Nothing to create: a brand-new row needs a value to be identified by.
    emits('refreshList');
    return;
  }
  if (props.related_id && props.id == 0) {
    $apiService.newItem(props.entity, props.property, inputValue.value, props.parent_entity, props.parent_id, props.related_id)
      .then(() => {
        emits('refreshList');  // Notifica al pare per refrescar la llista
      });
  } else {
    if (props.id == 0) {
      $apiService.newItem(props.entity, props.property, inputValue.value, props.parent_entity, props.parent_id)
        .then(() => {
          emits('refreshList');  // Notifica al pare per refrescar la llista
        });
    } else {
      $apiService.updateValue(props.entity, props.property, props.id, inputValue.value, props.parent_entity || null, props.parent_id || null)
        .then(() => {
          emits('changed');  // Notifica al pare per refrescar l'item
        });
    }
  }


}

function submitOnTab(event) {
  event.preventDefault();
  submitToken();
}


const emits = defineEmits(['refreshList', 'changed']);
</script>

<template>
  <div :id=ident class="edit_field_dialog w-full">
    <button @click="openDialog" :data-id="ident"
      class="group flex justify-between w-full focus:outline-none focus-visible:border-white text-start">
      <span :class=props.inputClass>{{ inputValue }}</span>
      <Icon name="fa6-solid:pencil"
        class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out flex-shrink-0 text-base self-center" />
    </button>
    <dialog ref="dialog" @click="checkDialogClick" @close="onDialogClose" class=""
      style="margin: 0px; margin-left: calc(-170px + -12px); margin-top: calc(-80px + -3px); padding: 80px 170px; background: transparent;">
      <form @submit.prevent="submitToken">
        <input type="text" v-model="inputValue" @keydown.tab="submitOnTab" :maxlength="props.maxlength"
          class="p-1 rounded border-slate-500 focus:outline-none focus-visible:border-slate-800" />
        <button type="submit" class="hidden">{{ t('common.save') }}</button>
      </form>
    </dialog>
  </div>
</template>

<style>
dialog input[type=text] {
  box-shadow: rgba(15, 15, 15, 0.05) 0px 0px 0px 1px, rgba(15, 15, 15, 0.1) 0px 3px 6px, rgba(15, 15, 15, 0.2) 0px 9px 24px;
}

::backdrop {
  opacity: 0;
}
</style>
