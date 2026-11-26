<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as echarts from "echarts";
const props = defineProps<{ option: any }>();
const el = ref<HTMLElement>();
let chart: echarts.ECharts | undefined;
let observer: ResizeObserver;
let themeObserver: MutationObserver;
function initialize() {
  chart?.dispose();
  chart = echarts.init(
    el.value,
    document.documentElement.classList.contains("dark") ? "dark" : undefined,
  );
  chart.setOption({
    ...props.option,
    backgroundColor: "transparent",
    animation: false,
  });
}
onMounted(() => {
  initialize();
  themeObserver = new MutationObserver(initialize);
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(el.value!);
});
watch(
  () => props.option,
  (v) =>
    chart?.setOption(
      { ...v, backgroundColor: "transparent", animation: false },
      true,
    ),
  { deep: true },
);
onBeforeUnmount(() => {
  observer?.disconnect();
  themeObserver?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div ref="el" class="chart" role="img" aria-label="任务执行统计图"></div>
</template>
