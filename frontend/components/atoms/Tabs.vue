<script setup>

// References to the scrollable container and the scroll position
const scrollContainer = ref(null);
const canScrollLeft = ref(false);
const canScrollRight = ref(true);

const props = defineProps({
  is_tab: {
    type: Boolean,
    default: true,
  }
});

// Handle wheel event for horizontal scrolling
const handleWheel = (event) => {
  if (event.deltaY !== 0) {
    event.preventDefault();
    scrollContainer.value.scrollBy({
      left: event.deltaY * 4,
      behavior: "smooth"
    });
    setTimeout(checkScroll, 500); // Check scroll after animation, matching the arrow buttons behavior
  }
};

const checkScroll = () => {
  if (scrollContainer.value) {
    // Check if the user can scroll left or right
    canScrollLeft.value = scrollContainer.value.scrollLeft > 0;
    canScrollRight.value =
      scrollContainer.value.scrollWidth > scrollContainer.value.clientWidth &&
      scrollContainer.value.scrollLeft + scrollContainer.value.clientWidth < scrollContainer.value.scrollWidth;
  }
};

// Scroll left by a set amount
const scrollLeft = () => {
  scrollContainer.value.scrollBy({ left: -150, behavior: "smooth" });
  setTimeout(checkScroll, 300); // Check scroll after scrolling
};

// Scroll right by a set amount
const scrollRight = () => {
  scrollContainer.value.scrollBy({ left: 150, behavior: "smooth" });
  setTimeout(checkScroll, 300); // Check scroll after scrolling
};

// Function to add the resize listener
const onResize = () => {
  checkScroll();
};

onMounted(() => {
  // Set the scroll position to the leftmost position by default
  scrollContainer.value.scrollLeft = 0;
  // Listen to the scroll event to continuously check the scroll position
  scrollContainer.value.addEventListener("scroll", checkScroll);
  // Add wheel event listener for horizontal scrolling
  scrollContainer.value.addEventListener("wheel", handleWheel, { passive: false });
  // Add window resize event listener
  window.addEventListener("resize", onResize);
  setTimeout(checkScroll, 100);
});

onBeforeUnmount(() => {
  // Clean up event listeners when the component is destroyed
  scrollContainer.value.removeEventListener("scroll", checkScroll);
  scrollContainer.value.removeEventListener("wheel", handleWheel);
  window.removeEventListener("resize", onResize);
});
</script>

<template>
  <div class="relative">
    <!-- Left Arrow -->
    <button
      @click="scrollLeft"
      :class="{'opacity-90': canScrollLeft}"
      class="absolute opacity-0 transition-all duration-150 left-0 top-1/2 transform -translate-y-1/2 z-10 bg-gray-200 text-gray-500 p-2 hover:bg-gray-300 rounded-full w-6 h-6 flex items-center justify-center"
    >
      <Icon name="fa6-solid:chevron-left" />
    </button>

    <!-- Scrollable Tab List -->
    <div id="region_tabs" ref="scrollContainer" class="overflow-x-auto over scrollbar-hide overflow-y-hidden"
    :class="{'border-b border-gray-200': is_tab}">
      <ul class="flex flex-nowrap -mb-px text-sm font-medium text-center text-gray-500 custom-tabs">
        <slot></slot>
      </ul>
    </div>

    <!-- Right Arrow -->
    <button
      @click="scrollRight"
      :class="{'opacity-90': canScrollRight}"
      class="absolute opacity-0 transition-all duration-150 right-0 top-1/2 transform -translate-y-1/2 z-10 bg-gray-200 text-gray-500 p-2 hover:bg-gray-300 rounded-full w-6 h-6 flex items-center justify-center"
    >
      <Icon name="fa6-solid:chevron-right" />
    </button>
  </div>
</template>
