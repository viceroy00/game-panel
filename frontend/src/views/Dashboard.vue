<template>
  <v-container>
    <h1 class="text-h4 mb-4 font-weight-bold" style="color:#E6EDF3;">대시보드</h1>

    <!-- 요약 카드 -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card style="border:1px solid rgba(63,185,80,0.3); background:rgba(63,185,80,0.06);">
          <v-card-text class="text-center">
            <v-icon size="28" color="success" class="mb-1">mdi-play-circle</v-icon>
            <div class="text-h3 font-weight-bold" style="color:#3FB950;">{{ runningCount }}</div>
            <div style="color:#8B949E;">실행 중</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card style="border:1px solid rgba(248,81,73,0.3); background:rgba(248,81,73,0.06);">
          <v-card-text class="text-center">
            <v-icon size="28" color="error" class="mb-1">mdi-stop-circle</v-icon>
            <div class="text-h3 font-weight-bold" style="color:#F85149;">{{ stoppedCount }}</div>
            <div style="color:#8B949E;">정지됨</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card style="border:1px solid rgba(88,166,255,0.3); background:rgba(88,166,255,0.06);">
          <v-card-text class="text-center">
            <v-icon size="28" color="primary" class="mb-1">mdi-server</v-icon>
            <div class="text-h3 font-weight-bold" style="color:#58A6FF;">{{ containers.length }}</div>
            <div style="color:#8B949E;">전체 서버</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card style="border:1px solid rgba(210,153,34,0.3); background:rgba(210,153,34,0.06);">
          <v-card-text class="text-center">
            <v-icon size="28" color="warning" class="mb-1">mdi-clipboard-clock</v-icon>
            <div class="text-h3 font-weight-bold" style="color:#D29922;">{{ pendingRequests }}</div>
            <div style="color:#8B949E;">대기 신청</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 컨테이너 목록 -->
    <v-card style="border:1px solid rgba(88,166,255,0.15);">
      <v-card-title class="d-flex align-center" style="color:#E6EDF3;">
        게임 서버 현황
        <v-spacer />
        <v-btn icon="mdi-refresh" variant="text" color="primary" size="small"
          @click="fetchContainers" :loading="loading" />
      </v-card-title>
      <v-card-text>
        <v-table v-if="containers.length" class="bg-transparent">
          <thead>
            <tr>
              <th style="color:#8B949E;">서버명</th>
              <th style="color:#8B949E;">이미지</th>
              <th style="color:#8B949E;">상태</th>
              <th style="color:#8B949E;">CPU</th>
              <th style="color:#8B949E;">메모리</th>
              <th style="color:#8B949E;">액션</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in containers" :key="c.id">
              <td class="font-weight-medium">{{ c.name }}</td>
              <td><code style="color:#79C0FF;">{{ c.image }}</code></td>
              <td>
                <v-chip :color="c.status === 'running' ? 'success' : 'error'" size="small" variant="tonal">
                  {{ c.status }}
                </v-chip>
              </td>
              <td>{{ c.cpu_percent ?? '-' }}%</td>
              <td>{{ c.memory_usage ?? '-' }}</td>
              <td>
                <v-btn v-if="c.status !== 'running'" icon="mdi-play" size="x-small" color="success"
                  variant="tonal" class="mr-1" @click="doAction(c.name, 'start')" />
                <v-btn v-if="c.status === 'running'" icon="mdi-stop" size="x-small" color="error"
                  variant="tonal" class="mr-1" @click="doAction(c.name, 'stop')" />
                <v-btn icon="mdi-restart" size="x-small" color="primary"
                  variant="tonal" @click="doAction(c.name, 'restart')" />
              </td>
            </tr>
          </tbody>
        </v-table>
        <v-alert v-else type="info" variant="tonal">
          관리 중인 게임 서버가 없습니다.
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const containers = ref([])
const pendingRequests = ref(0)
const loading = ref(false)

const runningCount = computed(() => containers.value.filter(c => c.status === 'running').length)
const stoppedCount = computed(() => containers.value.filter(c => c.status !== 'running').length)

async function fetchContainers() {
  loading.value = true
  try {
    const res = await api.get('/api/containers/')
    containers.value = res.data
    // stats는 비동기로 별도 로딩 (목록 먼저 표시)
    fetchAllStats()
  } catch (e) {
    console.error('컨테이너 조회 실패:', e)
  } finally {
    loading.value = false
  }
}

async function fetchAllStats() {
  const running = containers.value.filter(c => c.status === 'running')
  for (const c of running) {
    try {
      const res = await api.get(`/api/containers/${c.name}/stats`)
      const idx = containers.value.findIndex(x => x.name === c.name)
      if (idx !== -1) {
        containers.value[idx] = { ...containers.value[idx], ...res.data }
      }
    } catch (e) {
      // stats 실패는 무시
    }
  }
}

async function doAction(name, action) {
  try {
    await api.post(`/api/containers/${name}/${action}`)
    await fetchContainers()
  } catch (e) {
    alert(e.response?.data?.detail || '작업 실패')
  }
}

onMounted(() => {
  fetchContainers()
})
</script>
