<script setup>
// 布局：顶栏品牌 + 左侧示例问题/数据字典 + 主区对话；未登录先出登录层
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import ChatWindow from './components/ChatWindow.vue'
import { getSchema, getToken, login } from './api'

const chatRef = ref(null)
const schemaVisible = ref(false)
const schemaDoc = ref('')
const loggedIn = ref(!!getToken())
const password = ref('')
const logging = ref(false)

const doLogin = async () => {
  if (!password.value) return
  logging.value = true
  try {
    await login(password.value)
    loggedIn.value = true
    password.value = ''
    ElMessage.success('登录成功')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    logging.value = false
  }
}

// token 过期/失效时（任何接口 401），弹回登录层
window.addEventListener('askdata:unauthorized', () => {
  loggedIn.value = false
})

onMounted(async () => {
  if (loggedIn.value) {
    // 用一个真实接口验 token 是否仍有效
    try {
      await getSchema()
    } catch {
      /* 401 已触发登录层 */
    }
  }
})

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
      return
    }
  }
  schemaVisible.value = true
}
</script>

<template>
  <div class="layout" v-if="loggedIn">
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

  <!-- 登录层：口令换 JWT -->
  <div v-else class="login-mask">
    <div class="login-card">
      <div class="login-logo">📊</div>
      <div class="login-title">AskData · 问数</div>
      <div class="login-sub">ChatBI 数据分析 Agent</div>
      <el-input
        v-model="password"
        type="password"
        placeholder="访问口令"
        size="large"
        show-password
        @keydown.enter="doLogin"
      />
      <el-button type="primary" size="large" :loading="logging" class="login-btn" @click="doLogin">
        进 入
      </el-button>
    </div>
  </div>
</template>

<style>
/* ---- 粗野主义全局基调：纸白/纯黑/电光黄，3px 边框 + 硬投影，零圆角零渐变 ---- */
body {
  margin: 0;
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  background: #fff;
  color: #000;
}
:root {
  --el-color-primary: #111;
  --el-border-radius-base: 0px;
}
.el-button {
  border: 2px solid #000 !important;
  border-radius: 0 !important;
  font-weight: 700;
  box-shadow: 3px 3px 0 #000;
  transition: none;
}
.el-button:not(.is-text):active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 #000;
}
.el-button--primary {
  background: #ffe800 !important;
  color: #000 !important;
}
.el-button--primary.is-text {
  background: transparent !important;
}
.el-button.is-text {
  border: none !important;
  box-shadow: none !important;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.el-input__wrapper, .el-textarea__inner {
  border-radius: 0 !important;
  border: 2px solid #000 !important;
  box-shadow: none !important;
  font-family: Consolas, 'Microsoft YaHei', monospace;
}
.el-dialog {
  border-radius: 0 !important;
  border: 3px solid #000;
  box-shadow: 8px 8px 0 #000;
}
.el-tag {
  border-radius: 0 !important;
  border: 2px solid #000 !important;
  font-family: Consolas, monospace;
  font-weight: 700;
  background: #fff !important;
  color: #000 !important;
}
.el-alert {
  border-radius: 0 !important;
  border: 2px solid #000 !important;
  background: #ff4b3e !important;
  color: #000 !important;
  font-weight: 700;
}
.el-table {
  --el-table-border-color: #000;
  --el-table-header-bg-color: #000;
  --el-table-header-text-color: #fff;
  --el-table-row-hover-bg-color: #ffe800;
}
.el-table th.el-table__cell {
  font-family: Consolas, monospace;
}
.el-table .el-table__cell {
  border: 1px solid #000 !important;
}
</style>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 58px;
  background: #000;
  color: #fff;
  border-bottom: 3px solid #000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  font-size: 22px;
  background: #ffe800;
  color: #000;
  border: 2px solid #fff;
  padding: 1px 6px;
  font-weight: 900;
}
.name {
  font-size: 19px;
  font-weight: 900;
  letter-spacing: 1px;
}
.sub {
  font-size: 12px;
  color: #ffe800;
  font-family: Consolas, monospace;
  border: 1px solid #ffe800;
  padding: 1px 6px;
}
.main-row {
  flex: 1;
  display: flex;
  min-height: 0;
  background: #fff;
}
.aside {
  width: 240px;
  background: #fff;
  border-right: 3px solid #000;
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.panel-title {
  font-size: 12px;
  color: #000;
  margin: 8px 0 2px;
  font-family: Consolas, monospace;
  font-weight: 700;
  border-bottom: 3px solid #000;
  padding-bottom: 4px;
}
.ex-btn {
  justify-content: flex-start;
  font-family: Consolas, 'Microsoft YaHei', monospace;
}
.meta {
  font-size: 13px;
  color: #000;
  line-height: 2.1;
  font-family: Consolas, 'Microsoft YaHei', monospace;
}
.meta-sub {
  font-size: 11px;
  color: #000;
  margin-top: 6px;
  background: #ffe800;
  border: 2px solid #000;
  padding: 2px 6px;
  display: inline-block;
  font-weight: 700;
}
.chat-area {
  flex: 1;
  min-width: 0;
  background: #fff;
  margin: 14px;
  border: 3px solid #000;
  box-shadow: 6px 6px 0 #000;
  overflow: hidden;
}
.schema {
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.7;
  font-family: Consolas, 'Microsoft YaHei', monospace;
  background: #fff;
  border: 2px solid #000;
  padding: 12px;
  max-height: 65vh;
  overflow-y: auto;
}
.login-mask {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: repeating-linear-gradient(45deg, #fff 0 24px, #f2f2ee 24px 48px);
}
.login-card {
  width: 340px;
  background: #ffe800;
  border: 3px solid #000;
  box-shadow: 10px 10px 0 #000;
  padding: 34px 30px 30px;
  text-align: center;
}
.login-logo {
  font-size: 38px;
  border: 2px solid #000;
  display: inline-block;
  padding: 4px 10px;
  background: #fff;
}
.login-title {
  font-size: 22px;
  font-weight: 900;
  margin-top: 12px;
  letter-spacing: 1px;
}
.login-sub {
  font-size: 12px;
  color: #000;
  margin: 4px 0 22px;
  font-family: Consolas, monospace;
  font-weight: 700;
}
.login-btn {
  width: 100%;
  margin-top: 14px;
  background: #000 !important;
  color: #ffe800 !important;
}
</style>
