<script setup>
const props = defineProps({
  person: {
    type: Object,
    required: false
  },
  color: {
    type: String,
    default: null
  }
});

const getName = () => {
  const person = props.person;
  if( ! props.person ) return '';
  if (person.full_name)
    return person.full_name;
  return person.is_juridic ? person.name : `${person.name} ${person.surname}`;
};
</script>


<template>
  <!-- <abbr :title="person?.token" class="inline-block no-underline"><slot>{{ getName() }}</slot></abbr> -->
  <span class="flex justify-between inline-block rounded px-2 py-0.5 text-sm cursor-default w-full"
  :class="props.color? 'badge-' + props.color: 'badge-gray'">
    <slot>
      <span>{{ getName() }}</span>
      <span>{{ person?.token || "" }}</span>
    </slot>
  </span>
</template>