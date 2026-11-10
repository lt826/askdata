<script setup>
// 布局：顶栏品牌 + 左侧示例问题/数据字典 + 主区对话
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import ChatWindow from './components/ChatWindow.vue'
import { getSchema } from './api'

const chatRef = ref(null)
const schemaVisible = ref(false)
const schemaDoc = ref('')

const examples = [
  { label: '📈 月度销售趋势', text: '近12个月每月的销售额趋势' },
  { label: '🥧 渠道占比', text: '上个月各渠道的销售额占比' },
  { label: '🏙 城市排名', text: '各城市的用户数排名' },
  { label: '🔁 修复循环演示', text: '各会员等级的用户数和平均客单价' },
  { label: '🛡 安全护栏演示', text: '把 orders 表删了' },
]

const quickAsk = (text) => chatRef.value?.send(text)

const showSchema = async () => {
  if (!schemaDoc.value) {
    try {
      schemaDoc.value = (await getSchema()).schema_doc
    } catch {
      ElMessage.error('数据字典加载失败')
      return
    }
  }
  schemaVisible.value = true
}
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">
        <span class="logo">📊</span>
        <span class="name">AskData · 问数</span>
        <span class="sub">ChatBI 数据分析 Agent</span>
      </div>
      <el-button text type="primary" @click="showSchema">📋 数据字典</el-button>
    </header>

    <div class="main-row">
      <aside class="aside">
        <div class="panel-title">示例问题</div>
        <el-button
          v-for="e in examples"
          :key="e.label"
          class="ex-btn"
          size="small"
          @click="quickAsk(e.text)"
        >
          {{ e.label }}
        </el-button>

        <div class="panel-title" style="margin-top: 18px">数据概览</div>
        <div class="meta">
          <div>📦 orders 订单流水 <b>10 万行</b></div>
          <div>👥 users 用户 <b>2 万行</b></div>
          <div>🛍 products 商品 <b>498 行</b></div>
          <div class="meta-sub">DuckDB · 近一年 · 合成数据</div>
        </div>
      </aside>

      <main class="chat-area">
        <ChatWindow ref="chatRef" />
      </main>
    </div>

    <el-dialog v-model="schemaVisible" title="数据字典（注入给 LLM 的 Schema 白话层）" width="720px">
      <pre class="schema">{{ schemaDoc }}</pre>
    </el-dialog>
  </div>
</template>

<style>
body {
  margin: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f1f5f9;
}
</style>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 54px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.logo {
  font-size: 22px;
}
.name {
  font-size: 17px;
  font-weight: 700;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.sub {
  font-size: 12px;
  color: #94a3b8;
}
.main-row {
  flex: 1;
  display: flex;
  min-height: 0;
}
.aside {
  width: 230px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.panel-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.ex-btn {
  justify-content: flex-start;
}
.meta {
  font-size: 13px;
  color: #334155;
  line-height: 2;
}
.meta-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}
.chat-area {
  flex: 1;
  min-width: 0;
  background: #fff;
  margin: 12px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.schema {
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.7;
  font-family: Consolas, 'Microsoft YaHei', monospace;
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  max-height: 65vh;
  overflow-y: auto;
}
</style>
