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
  background: #f2f2ee;
  border: 2px solid #000;
  border-left: 6px solid #000;
  padding: 10px 12px;
  margin-bottom: 10px;
  font-size: 12px;
  font-family: Consolas, 'Microsoft YaHei', monospace;
}
.trace-title {
  color: #000;
  margin-bottom: 8px;
  font-weight: 900;
  letter-spacing: 1px;
}
.round {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.no {
  color: #000;
  font-weight: 900;
  background: #ffe800;
  border: 1px solid #000;
  padding: 0 4px;
}
.sql {
  font-family: Consolas, monospace;
  color: #000;
  background: #fff;
  border: 1px solid #000;
  padding: 1px 6px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.err {
  width: 100%;
  color: #fff;
  background: #ff4b3e;
  border: 1px solid #000;
  font-size: 11px;
  padding: 1px 6px;
  margin-left: 18px;
  display: inline-block;
}
</style>
