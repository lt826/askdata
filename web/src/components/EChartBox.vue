<script setup>
// ECharts 渲染容器：按 chart_type 把查询结果列映射为图配置
// 约定：第一列=维度（类目/时间），其余列=数值系列
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  chartType: { type: String, required: true },   // bar / line / pie
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
})

const el = ref(null)
let chart = null

const PALETTE = ['#2563eb', '#7c3aed', '#0ea5e9', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#64748b']

function isNum(v) {
  return typeof v === 'number' || (typeof v === 'string' && v !== '' && !Number.isNaN(Number(v)))
}

function buildOption() {
  const cats = props.rows.map((r) => String(r[0]))
  const numCols = props.columns.slice(1)
  // 纯数值列才进系列（防御：模型判定 chart 但混入文本列时只画数值列）
  const seriesCols = numCols.filter((c) => props.rows.every((r) => isNum(r[numCols.indexOf(c) + 1])))
  const series = seriesCols.map((c, i) => ({
    name: String(c),
    type: props.chartType === 'line' ? 'line' : 'bar',
    smooth: true,
    symbolSize: 6,
    data: props.rows.map((r) => r[numCols.indexOf(c) + 1]),
    itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: props.chartType === 'bar' ? [4, 4, 0, 0] : 0 },
    areaStyle:
      seriesCols.length === 1 && props.chartType === 'line'
        ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(37, 99, 235, 0.25)' },
              { offset: 1, color: 'rgba(37, 99, 235, 0.02)' },
            ]),
          }
        : undefined,
  }))

  if (props.chartType === 'pie') {
    return {
      color: PALETTE,
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, icon: 'circle' },
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 6 },
        label: { formatter: '{b}\n{d}%' },
        data: props.rows
          .filter((r) => isNum(r[1]))
          .map((r) => ({ name: String(r[0]), value: r[1] })),
      }],
    }
  }

  const isTime = /\d{4}-\d{2}/.test(cats[0] || '')
  return {
    color: PALETTE,
    tooltip: { trigger: 'axis' },
    legend: series.length > 1 ? { top: 0 } : undefined,
    grid: { left: 8, right: 16, top: series.length > 1 ? 34 : 24, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { rotate: cats.length > 8 ? 38 : 0, fontSize: 11 },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: {
        fontSize: 11,
        formatter: (v) => (v >= 1e8 ? v / 1e8 + '亿' : v >= 1e4 ? v / 1e4 + '万' : v),
      },
    },
    series,
    ...(isTime ? { dataZoom: [{ type: 'inside' }] } : {}),
  }
}

function render() {
  if (!el.value) return
  chart = chart || echarts.init(el.value)
  chart.setOption(buildOption(), true)
}

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
const onResize = () => chart?.resize()
watch(() => [props.chartType, props.rows], render)
</script>

<template>
  <div ref="el" class="echart" />
</template>

<style scoped>
.echart {
  width: 100%;
  height: 340px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 6px 4px 0;
  margin-bottom: 10px;
}
</style>
