<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import H1Region from '../atoms/H1Region.vue';
import { se } from 'date-fns/locale';

import { toolbarButtons, editorConditions, editorValues, htmlEditorParts } from '~/utils/editor';

const { t } = useI18n();
</script>

<template>
  <div>
    <H1Region>
      {{ t('editor_block.editor_title') }}
    </H1Region>

    <div class="mt-2">

      <details class="my-2">
        <summary class="font-semibold p-2 italic">
          {{ t('common.conditionals') }}
        </summary>
        <div class="mb-2 bg-slate-200 rounded-lg py-2 px-5 customers-shadow">
          <div v-for="element in editorConditions" class="flex justify-between items-center gap-2 mb-2">
            <span class="bg-white py-1 px-2 rounded-md font-medium text-center">
              {{ t(element.label) }}
            </span>
            <span class="text-sm text-gray-700">
              {{ t(element.description) }}
            </span>
          </div>
        </div>
      </details>


      <details class="my-2">
        <summary class="font-semibold p-2 italic">
          {{ t('common.values') }}
        </summary>
        <div class="mb-2 bg-slate-200 rounded-lg py-2 px-5 customers-shadow">
          <div v-for="(group, groupName) in editorValues" :key="groupName">
            <span class="m-1 font-bold italic text-slate-600"> 
              {{ t(groupName.charAt(0).toUpperCase() + groupName.slice(1))}}
            </span>
            <div v-for="element in group" :key="element.label" class="flex justify-between items-center gap-2 my-2">
              <span class="bg-white py-1 px-2 rounded-md font-medium">
                {{ t(element.label) }}
              </span>
              <span class="text-sm text-gray-700">
                {{ t(element.description) }}
              </span>
            </div>
          </div>
        </div>
      </details>

      <details class="my-2">
        <summary class="font-semibold p-2 italic">
          {{ t('editor_block.tags') }}
        </summary>
        <div class="mb-2 bg-slate-200 rounded-lg py-2 px-5 customers-shadow">
          <div v-for="(group, groupName) in htmlEditorParts" :key="groupName">
            <span class="m-1 font-bold italic text-slate-600"> 
              {{ t(groupName.charAt(0).toUpperCase() + groupName.slice(1))}}
            </span>
            <div v-for="element in group" :key="element.label" class="flex justify-between items-center gap-2 my-2">
              <span class="bg-white py-1 px-2 rounded-md font-medium">
                {{ t(element.label) }}
              </span>
              <span class="text-sm text-gray-700">
                {{ t(element.description) }}
              </span>
            </div>
          </div>
        </div>
      </details>

      <details class="my-2">
        <summary class="font-semibold p-2 italic">
          {{ t('editor_block.examples') }}
        </summary>
        <div class="mb-2 bg-slate-200 rounded-lg py-2 px-5 customers-shadow">
          <div v-for="element in editorFunctions" class="flex justify-between items-center gap-2 mb-2">
            <span class="toolbar-button">
              {{ t(element.label) }}
            </span>
            <span class="text-sm text-gray-700">
              {{ t(element.description) }}
            </span>
          </div>
        </div>
      </details>

    </div>
  </div>
</template>
