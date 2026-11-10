<script setup>
// SQL 修复循环轨迹：每轮一行（轮次/成败/错误分类/耗时/SQL 摘要）
defineProps({
  rounds: { type: Array, default: () => [] },
})

const shortSql = (s) => (s.length > 64 ? s.slice(0, 64) + '…' : s.replace(/\s+/g, ' '))
</script>

<template>
  <div v-if="rounds.length" class="trace">
    <div class="trace-title">⟳ NL → SQL 修复循环</div>
    <div v-for="t in rounds" :key="t.round_no" class="round">
      <span class="no">R{{ t.round_no }}</span>
      <el-tag v-if="t.ok" type="success" size="small" effect="plain">✅ {{ t.elapsed_ms }}ms</el-tag>
      <el-tag v-else type="danger" size="small" effect="plain">❌ {{ t.error_class }}</el-tag>
      <el-tooltip :content="t.sql" placement="top" :show-after="200">
        <code class="sql">{{ shortSql(t.sql) }}</code>
      </el-tooltip>
      <div v-if="!t.ok && t.error" class="err">{{ t.error.slice(0, 110) }}</div>
    </div>
  </div>
</template>

<style scoped>
.trace {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
  font-size: 12px;
}
.trace-title {
  color: #64748b;
  margin-bottom: 6px;
}
.round {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.no {
  color: #94a3b8;
  font-weight: 600;
}
.sql {
  font-family: Consolas, monospace;
  color: #334155;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.err {
  width: 100%;
  color: #dc2626;
  font-size: 11px;
  padding-left: 26px;
}
</style>
