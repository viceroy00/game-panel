<template>
  <v-container>
    <h1 class="text-h4 mb-4 font-weight-bold" style="color:#E6EDF3;">서버 관리</h1>

    <v-row>
      <!-- 서버 목록 -->
      <v-col cols="12" md="4">
        <v-card style="border:1px solid rgba(88,166,255,0.15);">
          <v-card-title style="color:#E6EDF3;">서버 목록</v-card-title>
          <v-list density="compact" bg-color="transparent">
            <v-list-item v-for="c in containers" :key="c.id"
              :active="selected?.name === c.name" active-color="primary"
              @click="selectServer(c)" rounded="lg" class="mx-2 mb-1">
              <template v-slot:prepend>
                <v-icon :color="c.status === 'running' ? 'success' : 'grey'" size="20">
                  mdi-server
                </v-icon>
              </template>
              <v-list-item-title>{{ c.name }}</v-list-item-title>
              <v-list-item-subtitle>{{ c.image }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>

      <!-- 서버 상세 -->
      <v-col cols="12" md="8">
        <v-card v-if="selected" style="border:1px solid rgba(88,166,255,0.15);">
          <v-card-title style="color:#E6EDF3;">{{ selected.name }}</v-card-title>
          <v-card-text>
            <!-- 제어 버튼 -->
            <div class="d-flex flex-wrap mb-4" style="gap:8px;">
              <v-btn color="success" variant="tonal" @click="doAction('start')"
                :disabled="selected.status === 'running'">
                <v-icon start>mdi-play</v-icon> 시작
              </v-btn>
              <v-btn color="error" variant="tonal" @click="doAction('stop')"
                :disabled="selected.status !== 'running'">
                <v-icon start>mdi-stop</v-icon> 정지
              </v-btn>
              <v-btn color="primary" variant="tonal" @click="doAction('restart')">
                <v-icon start>mdi-restart</v-icon> 재시작
              </v-btn>
              <v-btn color="primary" variant="outlined" :to="`/servers/${selected.name}/files`">
                <v-icon start>mdi-folder-open</v-icon> 파일 관리
              </v-btn>
            </div>

            <!-- 리소스 정보 -->
            <v-row class="mb-4">
              <v-col cols="6">
                <v-card variant="outlined" style="border-color:rgba(88,166,255,0.15);">
                  <v-card-text>
                    <div class="text-caption" style="color:#8B949E;">CPU</div>
                    <div class="text-h6" style="color:#E6EDF3;">{{ selected.cpu_percent ?? '-' }}%</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="6">
                <v-card variant="outlined" style="border-color:rgba(88,166,255,0.15);">
                  <v-card-text>
                    <div class="text-caption" style="color:#8B949E;">메모리</div>
                    <div class="text-h6" style="color:#E6EDF3;">{{ selected.memory_usage ?? '-' }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- 로그 -->
            <div class="d-flex align-center mb-2">
              <h3 style="color:#E6EDF3;">로그</h3>
              <v-spacer />
              <v-btn size="small" variant="tonal" color="primary" @click="fetchLogs">
                <v-icon start size="16">mdi-refresh</v-icon> 새로고침
              </v-btn>
            </div>
            <v-sheet style="background:#010409; border:1px solid rgba(88,166,255,0.1);" class="pa-3 rounded-lg" :style="{maxHeight: '400px', overflowY: 'auto'}">
              <pre style="color: #3FB950; font-size: 12px; white-space: pre-wrap;">{{ logs }}</pre>
            </v-sheet>
          </v-card-text>
        </v-card>

        <v-card v-else style="border:1px solid rgba(88,166,255,0.15);">
          <v-card-text class="text-center py-12" style="color:#8B949E;">
            좌측에서 서버를 선택하세요
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const containers = ref([])
const selected = ref(null)
const logs = ref('')

async function fetchContainers() {
  try {
    const res = await api.get('/api/containers/')
    containers.value = res.data
  } catch (e) {
    console.error(e)
  }
}

function selectServer(c) {
  selected.value = c
  fetchLogs()
  fetchStats()
}

async function fetchStats() {
  if (!selected.value || selected.value.status !== 'running') return
  try {
    const res = await api.get(`/api/containers/${selected.value.name}/stats`)
    if (selected.value) {
      selected.value = { ...selected.value, ...res.data }
    }
  } catch (e) {
    // stats 실패는 무시 (표시만 안 됨)
  }
}

async function fetchLogs() {
  if (!selected.value) return
  try {
    const res = await api.get(`/api/containers/${selected.value.name}/logs`, {
      params: { tail: 200 },
    })
    logs.value = res.data.logs
  } catch (e) {
    logs.value = '로그 조회 실패: ' + (e.response?.data?.detail || e.message)
  }
}

async function doAction(action) {
  if (!selected.value) return
  try {
    await api.post(`/api/containers/${selected.value.name}/${action}`)
    await fetchContainers()
    // 선택된 서버 정보 갱신
    selected.value = containers.value.find(c => c.name === selected.value.name)
  } catch (e) {
    alert(e.response?.data?.detail || '작업 실패')
  }
}

onMounted(fetchContainers)
</script>
