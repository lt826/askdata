<script setup>
// 助手气泡：修复循环轨迹 → 结论 → 图 → 表格
import ProcessTrace from './ProcessTrace.vue'

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

        <el-image
          v-if="msg.chartUrl"
          :src="msg.chartUrl"
          :preview-src-list="[msg.chartUrl]"
          fit="contain"
          class="chart"
        />

        <el-table
          v-if="msg.columns && msg.columns.length"
          :data="msg.tableRows"
          size="small"
          border
          max-height="360"
          class="table"
        >
          <el-table-column
            v-for="c in msg.columns"
            :key="c"
            :prop="String(c)"
            :label="String(c)"
            min-width="90"
          >
            <template #default="{ row }">
              {{ row[c] }}
            </template>
          </el-table-column>
        </el-table>
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
  margin-bottom: 14px;
}
.row.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.bubble.user {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
  width: 100%;
  max-width: 100%;
}
.text {
  white-space: pre-wrap;
  word-break: break-word;
}
.summary {
  font-size: 14.5px;
  font-weight: 600;
  color: #0f172a;
  margin: 4px 0 8px;
}
.chart {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fff;
}
.table {
  margin-bottom: 4px;
}
.more {
  font-size: 11px;
  color: #94a3b8;
}
.dots {
  color: #94a3b8;
  font-size: 13px;
}
.notice {
  margin-top: 6px;
}
</style>
