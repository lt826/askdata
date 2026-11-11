<script setup>
// 助手气泡：修复循环轨迹 → 结论 → ECharts 图（PNG 兜底）→ 表格
import ProcessTrace from './ProcessTrace.vue'
import EChartBox from './EChartBox.vue'

defineProps({
  msg: { type: Object, required: true },
})
</script>

<template>
  <div class="row" :class="msg.role">
    <div class="bubble" :class="msg.role">
      <template v-if="msg.role === 'assistant'">
        <div v-if="msg.streaming && !msg.rounds.length" class="dots">生成 SQL 中…</div>
        <ProcessTrace :rounds="msg.rounds" />

        <div v-if="msg.summary" class="summary">{{ msg.summary }}</div>

        <EChartBox
          v-if="msg.chartType && msg.chartCols.length"
          :chart-type="msg.chartType"
          :columns="msg.chartCols"
          :rows="msg.chartRows"
        />
        <el-image
          v-else-if="msg.chartUrl"
          :src="msg.chartUrl"
          :preview-src-list="[msg.chartUrl]"
          fit="contain"
          class="chart"
        />

        <div v-if="msg.columns && msg.columns.length" class="table-card">
          <el-table
            :data="msg.tableRows"
            size="small"
            stripe
            max-height="360"
          >
            <el-table-column
              v-for="(c, i) in msg.columns"
              :key="c"
              :prop="String(c)"
              :label="String(c)"
              :min-width="i === 0 ? 110 : 100"
              :align="i === 0 ? 'left' : 'right'"
            >
              <template #default="{ row }">
                {{ row[c] }}
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="msg.total > msg.tableRows?.length" class="more">
          仅展示前 {{ msg.tableRows.length }} 行，共 {{ msg.total }} 行
        </div>

        <el-alert
          v-if="msg.error"
          :title="msg.error"
          type="error"
          :closable="false"
          class="notice"
        />
        <div v-if="msg.streaming && msg.rounds.length && !msg.summary" class="dots">
          执行中…
        </div>
      </template>
      <div v-else class="text">{{ msg.text }}</div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  margin-bottom: 18px;
}
.row.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 82%;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.65;
  border: 3px solid #000;
  box-shadow: 5px 5px 0 #000;
}
.bubble.user {
  background: #ffe800;
  color: #000;
  font-weight: 700;
  box-shadow: -5px 5px 0 #000;
}
.bubble.assistant {
  background: #fff;
  width: 100%;
  max-width: 100%;
  box-shadow: 5px 5px 0 #000;
}
.text {
  white-space: pre-wrap;
  word-break: break-word;
}
.summary {
  font-size: 15px;
  font-weight: 900;
  color: #000;
  margin: 6px 0 10px;
  background: #ffe800;
  border: 2px solid #000;
  padding: 6px 10px;
  display: inline-block;
}
.chart {
  width: 100%;
  border: 3px solid #000;
  margin-bottom: 10px;
  background: #fff;
}
.table-card {
  border: 2px solid #000;
  margin-bottom: 6px;
  font-family: Consolas, 'Microsoft YaHei', monospace;
}
.table-card :deep(thead th) {
  background: #000;
  color: #fff;
  font-weight: 700;
  font-family: Consolas, monospace;
}
.more {
  font-size: 11px;
  color: #000;
  font-family: Consolas, monospace;
}
.dots {
  color: #000;
  font-size: 13px;
  font-family: Consolas, monospace;
}
.notice {
  margin-top: 8px;
}
</style>
