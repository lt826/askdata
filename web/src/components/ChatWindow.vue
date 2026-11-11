<script setup>
// 对话窗口：发送问题、SSE 事件装配进助手消息、自动滚动
import { nextTick, onMounted, reactive, ref } from 'vue'
import MessageBubble from './MessageBubble.vue'
import { streamAsk } from '../api'

const emit = defineEmits(['asked'])
const messages = ref([])
const input = ref('')
const sending = ref(false)
const listEl = ref(null)

const scrollDown = async () => {
  await nextTick()
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'smooth' })
}

const send = async (text) => {
  const q = (text ?? input.value).trim()
  if (!q || sending.value) return
  input.value = ''
  sending.value = true
  messages.value.push({ role: 'user', text: q })
  // 必须是 reactive：普通对象 push 进 reactive 数组后，改原对象不触发渲染（Vue3 经典坑）
  const assistant = reactive({
    role: 'assistant', streaming: true,
    rounds: [], summary: '',
    chartType: '', chartUrl: '', chartCols: [], chartRows: [],
    columns: [], tableRows: [], total: 0, error: '',
  })
  messages.value.push(assistant)
  scrollDown()

  const touch = () => scrollDown()
  try {
    await streamAsk(q, {
      round: (d) => { assistant.rounds.push(d); touch() },
      summary: (d) => { assistant.summary = d.text; touch() },
      chart: (d) => {
        assistant.chartType = d.chart_type
        assistant.chartUrl = d.url || ''
        if (d.columns?.length && d.rows?.length) {
          assistant.chartCols = d.columns
          assistant.chartRows = d.rows
        }
        touch()
      },
      table: (d) => {
        assistant.columns = d.columns
        // el-table 的 prop 必须是字符串键
        assistant.tableRows = d.rows.map((r) =>
          Object.fromEntries(d.columns.map((c) => [String(c), r[c] ?? r[d.columns.indexOf(c)]])))
        assistant.total = d.total
        touch()
      },
      error: (d) => { assistant.error = d.message; touch() },
    })
  } catch (e) {
    assistant.error = String(e)
  } finally {
    assistant.streaming = false
    sending.value = false
    emit('asked')
    touch()
  }
}

defineExpose({ send })
onMounted(scrollDown)
</script>

<template>
  <div class="chat">
    <div ref="listEl" class="list">
      <div class="welcome">
        <div class="w-title">用中文问数据，<br /><span class="hl">SQL 我来写</span>。</div>
        <div class="w-sub">
          生成 SQL → 沙箱执行 → 出错自动修复 → 出表格和图。<br />
          试试左侧的示例问题。
        </div>
      </div>
      <MessageBubble v-for="(m, i) in messages" :key="i" :msg="m" />
    </div>

    <div class="input-bar">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="问点什么，如：上个月销售额最高的五个品类"
        @keydown.enter.prevent="send()"
      />
      <el-button type="primary" :loading="sending" @click="send()">
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.list {
  flex: 1;
  overflow-y: auto;
  padding: 18px 22px;
}
.welcome {
  text-align: left;
  padding: 40px 0 24px;
}
.w-title {
  font-size: 30px;
  font-weight: 900;
  color: #000;
  line-height: 1.3;
}
.w-title .hl {
  background: #ffe800;
  padding: 0 8px;
  border: 3px solid #000;
  display: inline-block;
  box-shadow: 5px 5px 0 #000;
}
.w-sub {
  color: #000;
  font-size: 13px;
  margin-top: 14px;
  font-family: Consolas, 'Microsoft YaHei', monospace;
  border-left: 5px solid #000;
  padding-left: 10px;
}
.input-bar {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-top: 3px solid #000;
  background: #fff;
  align-items: flex-end;
}
</style>
