<template>
  <v-container>
    <h1 class="text-h4 mb-4 font-weight-bold" style="color:#E6EDF3;">게임 신청 관리</h1>

    <v-chip-group v-model="statusFilter" mandatory class="mb-4">
      <v-chip value="" variant="tonal">전체</v-chip>
      <v-chip v-for="(label, key) in stageLabels" :key="key" :value="key"
        :color="stageColor(key)" variant="tonal">{{ label }}</v-chip>
    </v-chip-group>

    <v-card style="border:1px solid rgba(88,166,255,0.15);">
      <v-table class="bg-transparent">
        <thead>
          <tr>
            <th style="color:#8B949E;">신청일</th>
            <th style="color:#8B949E;">신청자</th>
            <th style="color:#8B949E;">게임</th>
            <th style="color:#8B949E;">인원</th>
            <th style="color:#8B949E;">설정파일</th>
            <th style="color:#8B949E;">상태</th>
            <th style="color:#8B949E;">액션</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filteredRequests" :key="r.id">
            <td>{{ formatDate(r.created_at) }}</td>
            <td class="font-weight-medium">{{ r.requester_name }}</td>
            <td>{{ r.game_name }}</td>
            <td>{{ r.player_count }}명</td>
            <td>
              <v-btn v-if="r.config_file_path" size="x-small" variant="text" color="primary"
                @click="downloadConfig(r.id)">
                <v-icon size="16">mdi-file-excel</v-icon> 다운로드
              </v-btn>
              <span v-else style="color:#8B949E;">-</span>
            </td>
            <td>
              <v-chip :color="stageColor(r.status)" size="small" variant="tonal">
                {{ r.status_label }}
              </v-chip>
            </td>
            <td>
              <v-btn v-if="r.status !== 'onboarded' && r.status !== 'rejected'"
                size="small" color="primary" variant="tonal" @click="openStageDialog(r)">
                단계 변경
              </v-btn>
              <v-btn v-if="r.server_address" size="small" variant="text" color="info"
                class="ml-1" @click="openDetailDialog(r)">
                접속정보
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- ═══ 단계 변경 다이얼로그 ═══ -->
    <v-dialog v-model="stageDialog" max-width="600" persistent>
      <v-card class="pa-4" style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title class="text-h6" style="color:#58A6FF;">
          📋 {{ sel?.requester_name }} — {{ sel?.game_name }}
        </v-card-title>
        <v-card-subtitle>현재: {{ sel?.status_label }}</v-card-subtitle>
        <v-card-text>
          <v-select v-model="stageForm.status" :items="nextStages" item-title="label" item-value="key"
            label="변경할 단계" prepend-inner-icon="mdi-arrow-right-bold" />

          <!-- 승인 이후 단계에서 접속 정보 입력 -->
          <template v-if="showServerFields">
            <v-text-field v-model="stageForm.server_address" label="접속 IP / 도메인"
              prepend-inner-icon="mdi-ip-network" placeholder="game.example.com" />
            <v-text-field v-model="stageForm.server_port" label="포트"
              prepend-inner-icon="mdi-ethernet" placeholder="25565" />
            <v-text-field v-model="stageForm.server_password" label="초기 접속 비밀번호"
              prepend-inner-icon="mdi-lock" />
            <v-text-field v-model="stageForm.config_path" label="설정 파일 경로"
              prepend-inner-icon="mdi-file-cog" placeholder="/data/server.properties" />
          </template>

          <v-textarea v-model="stageForm.admin_notes" label="관리자 메모 (신청자에게 전달)" rows="2" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="stageDialog = false">취소</v-btn>
          <v-btn color="primary" variant="elevated" :loading="reviewLoading" @click="submitStage">
            <v-icon start>mdi-check</v-icon> 변경 및 알림 발송
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ═══ 접속 정보 다이얼로그 ═══ -->
    <v-dialog v-model="detailDialog" max-width="480">
      <v-card class="pa-4" style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title class="text-h6" style="color:#58A6FF;">
          🖥️ {{ sel?.game_name }} 접속 정보
        </v-card-title>
        <v-card-text>
          <v-list class="bg-transparent">
            <v-list-item v-if="sel?.server_address">
              <template #prepend><v-icon color="primary">mdi-ip-network</v-icon></template>
              <v-list-item-title>접속 주소</v-list-item-title>
              <v-list-item-subtitle style="font-family:monospace;">
                {{ sel.server_address }}{{ sel.server_port ? ':' + sel.server_port : '' }}
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="sel?.server_password">
              <template #prepend><v-icon color="warning">mdi-lock</v-icon></template>
              <v-list-item-title>비밀번호</v-list-item-title>
              <v-list-item-subtitle style="font-family:monospace;">{{ sel.server_password }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="sel?.config_path">
              <template #prepend><v-icon color="info">mdi-file-cog</v-icon></template>
              <v-list-item-title>설정 파일</v-list-item-title>
              <v-list-item-subtitle style="font-family:monospace;">{{ sel.config_path }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="sel?.admin_notes">
              <template #prepend><v-icon color="grey">mdi-note-text</v-icon></template>
              <v-list-item-title>관리자 메모</v-list-item-title>
              <v-list-item-subtitle>{{ sel.admin_notes }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="detailDialog = false">닫기</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import api from '../api'

const requests = ref([])
const statusFilter = ref('')
const sel = ref(null)
const reviewLoading = ref(false)

const stageDialog = ref(false)
const detailDialog = ref(false)
const stageForm = reactive({
  status: '', server_address: '', server_port: '',
  server_password: '', config_path: '', admin_notes: '',
})

const stageLabels = {
  pending: '대기', approved: '승인', building: '생성중',
  ready: '생성완료', permission_granted: '권한부여',
  firewall_done: '방화벽', onboarded: '온보딩', rejected: '거절',
}

const stageOrder = ['pending','approved','building','ready','permission_granted','firewall_done','onboarded']

const filteredRequests = computed(() => {
  if (!statusFilter.value) return requests.value
  return requests.value.filter(r => r.status === statusFilter.value)
})

const nextStages = computed(() => {
  if (!sel.value) return []
  const cur = sel.value.status
  const idx = stageOrder.indexOf(cur)
  const candidates = []
  if (cur === 'pending') {
    candidates.push({ key: 'approved', label: '✅ 승인' })
    candidates.push({ key: 'rejected', label: '❌ 거절' })
  } else if (idx >= 0 && idx < stageOrder.length - 1) {
    for (let i = idx + 1; i < stageOrder.length; i++) {
      const k = stageOrder[i]
      candidates.push({ key: k, label: stageLabels[k] })
    }
  }
  return candidates
})

const showServerFields = computed(() => {
  return ['approved','building','ready','permission_granted','firewall_done','onboarded'].includes(stageForm.status)
})

async function fetchRequests() {
  const res = await api.get('/api/game-requests/')
  requests.value = res.data
}

function openStageDialog(r) {
  sel.value = r
  const ns = nextStages.value
  Object.assign(stageForm, {
    status: ns.length ? ns[0].key : '',
    server_address: r.server_address || '',
    server_port: r.server_port || '',
    server_password: r.server_password || '',
    config_path: r.config_path || '',
    admin_notes: '',
  })
  stageDialog.value = true
}

function openDetailDialog(r) {
  sel.value = r
  detailDialog.value = true
}

async function submitStage() {
  reviewLoading.value = true
  try {
    await api.patch(`/api/game-requests/${sel.value.id}`, stageForm)
    stageDialog.value = false
    await fetchRequests()
  } catch (e) {
    alert(e.response?.data?.detail || '처리 실패')
  } finally {
    reviewLoading.value = false
  }
}

async function downloadConfig(requestId) {
  const res = await api.get(`/api/game-requests/${requestId}/config-download`, { responseType: 'blob' })
  const disp = res.headers['content-disposition']
  const filename = disp ? disp.split('filename=')[1]?.replace(/"/g,'') : 'config.xlsx'
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function stageColor(s) {
  const map = {
    pending: 'warning', approved: 'success', building: 'info', ready: 'cyan',
    permission_granted: 'teal', firewall_done: 'deep-purple', onboarded: 'success', rejected: 'error',
  }
  return map[s] || 'grey'
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ko-KR')
}

onMounted(fetchRequests)
</script>
