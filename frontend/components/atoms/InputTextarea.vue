<script setup>
import { ref, watch, onMounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
// Define the props
// const props = defineProps({
//     text: String,
//     placeholder: String
// });

const props = defineProps({
  text: {
    type: String,
    required: false,
    default: ''
  },
  placeholder: {
    type: String,
    required: false,
    default: undefined
  },
  autosave: {
    type: Boolean,
    required: false,
    default: true
  },
  rows: {
    type: Number,
    required: false,
    // Fractional OK for min-height (e.g. 1.5 ≈ old single-line look before auto-resize bug).
    default: 1.25,
  },
});

/** HTML `rows` must be integer; min-height uses the full fractional value. */
const htmlRows = computed(() => Math.max(1, Math.floor(props.rows)));

const displayTitlePlaceholder = computed(() => {
  return props.placeholder ?? 'common.observation_enter';
});


// Define the emit function for `update:text`
const emit = defineEmits(['update:text']);

// Create a ref for the textarea element
const textareaRef = ref(null);

// Create a local ref for the text value
const localText = ref(props.text);

// Function to resize the textarea (never shrink below rows minimum)
const getMinHeightPx = (textarea) => {
  const style = window.getComputedStyle(textarea);
  const lineHeight = parseFloat(style.lineHeight) || 20;
  const padding =
    parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  const border =
    parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
  return lineHeight * props.rows + padding + border;
};

const resizeTextarea = () => {
  const textarea = textareaRef.value;
  if (textarea) {
    textarea.style.height = 'auto';
    const minHeight = getMinHeightPx(textarea);
    textarea.style.height = `${Math.max(textarea.scrollHeight, minHeight)}px`;
  }
};

// Watch for changes in the `text` prop to update the local text and resize the textarea
watch(() => props.text, (newText) => {
  localText.value = newText;
  nextTick(() => {
    resizeTextarea();
  });
});

watch(() => props.rows, () => {
  nextTick(() => {
    resizeTextarea();
  });
});


const updateText = (event) => {
  resizeTextarea();
};

const resetTextArea = () => {
  const textarea = textareaRef.value;
  localText.value = "";
  if (textarea) {
    localText.value = "";
    textarea.select();
  }

  setTimeout(() => resizeTextarea(), 1)
}

const handleKeydown = (event) => {
  if( ! props.autosave ) {
    return;
  }

  if (!event.shiftKey && event.key === 'Enter') {
    event.preventDefault();
    emitChange()
  }
  else if (event.shiftKey && event.key === 'Enter') {
    // Prevent default newline behavior (optional)
    event.preventDefault();

    localText.value += '\n';
    setTimeout(() => resizeTextarea(), 1);
  }
};

const handleChange = (event) => {
  if( ! props.autosave ) {
    // event.preventDefault();
    emitChange()
    return;
  }
};

const emitChange = () => {
  if (props.autosave && !localText.value?.trim()) {
    return;
  }

  emit('update:text', localText.value)
  if( props.autosave) {
    resetTextArea()
  }
}

// Call resizeTextarea once the component is mounted
onMounted(() => {
  nextTick(() => {
    resizeTextarea();
  });
});
</script>

<template>
  <div class="custom-text-input px-2 pt-2">
    <textarea v-model="localText" :placeholder="t(displayTitlePlaceholder)" @input="updateText" @keydown="handleKeydown" @change="handleChange"
      ref="textareaRef"
      class="auto-resizing-textarea pt-2 pb-2 px-3 w-full rounded-lg border border-slate-300 bg-white text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400 transition-all"
      :rows="htmlRows"></textarea>
    <div v-if="autosave" class="flex justify-end mt-1.5 mb-2">
      <button type="button" @click="emitChange"
        class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold bg-sky-500 text-white hover:bg-sky-600 active:bg-sky-700 transition-colors shadow-sm">
        <Icon name="fa6-solid:paper-plane" class="w-3 h-3" />
        {{ t('common.register') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.auto-resizing-textarea {
  width: 100%;
  overflow: hidden;
  resize: none;
  box-sizing: border-box;
}

.auto-resizing-textarea:focus-visible {
  outline: none;
}
</style>
