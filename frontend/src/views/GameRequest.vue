<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="8">

        <!-- 신청 폼 -->
        <v-card class="mb-6" style="border:1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-h5 font-weight-bold" style="color:#E6EDF3;">🎮 게임 서버 신청</v-card-title>
          <v-card-subtitle style="color:#8B949E;">원하는 게임 서버를 신청하세요</v-card-subtitle>

          <v-card-text>
            <v-row>
              <v-col cols="12" sm="6">
                <v-text-field :model-value="auth.user?.display_name || auth.user?.username"
                  label="닉네임" readonly disabled prepend-inner-icon="mdi-account"
                  hint="디스코드 닉네임으로 자동 연동됩니다" persistent-hint />
              </v-col>
              <v-col cols="12" sm="6">
                <v-autocomplete v-model="form.game_name" :items="gameList" label="게임 선택"
                  prepend-inner-icon="mdi-gamepad-variant" :loading="templatesLoading"
                  @update:model-value="onGameSelect" clearable
                  hint="목록에 없으면 직접 입력 가능" persistent-hint
                  :custom-filter="() => true" editable />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field v-model.number="form.player_count" label="예상 인원" type="number" min="1" />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field v-model="form.preferred_time" label="희망 운영 시간대"
                  placeholder="예: 평일 저녁 8시~12시" />
              </v-col>

              <!-- 설정 양식 다운로드 & 업로드 -->
              <v-col cols="12" v-if="selectedTemplate">
                <v-alert type="info" variant="tonal" class="mb-3">
                  <div class="d-flex align-center">
                    <div>
                      📋 <strong>{{ selectedTemplate.game_name }}</strong> 설정 양식이 있습니다.
                      다운로드 후 원하는 값을 수정하여 업로드해주세요.
                    </div>
                    <v-spacer />
                    <v-btn variant="tonal" color="primary" size="small" @click="downloadTemplate">
                      <v-icon start size="16">mdi-download</v-icon> 양식 다운로드
                    </v-btn>
                  </div>
                </v-alert>
              </v-col>

              <v-col cols="12">
                <v-file-input v-model="configFile" label="서버 설정 파일 (엑셀)" accept=".xlsx,.xls"
                  prepend-icon="mdi-file-excel" variant="outlined" density="compact"
                  :hint="selectedTemplate ? '양식을 다운로드하여 수정 후 업로드해주세요' : '설정 양식이 있는 게임만 업로드 가능'"
                  persistent-hint />
              </v-col>

              <v-col cols="12">
                <v-textarea v-model="form.notes" label="비고" rows="2"
                  placeholder="추가 요청사항이 있으면 적어주세요" />
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-actions class="px-4 pb-4">
            <v-spacer />
            <v-btn color="primary" size="large" :loading="submitLoading" @click="submit">
              <v-icon start>mdi-send</v-icon> 신청하기
            </v-btn>
          </v-card-actions>

          <v-alert v-if="success" type="success" variant="tonal" class="ma-4">
            신청이 접수되었습니다! 관리자 검토 후 안내드리겠습니다.
          </v-alert>
          <v-alert v-if="error" type="error" variant="tonal" class="ma-4">{{ error }}</v-alert>
        </v-card>

        <!-- 내 신청 내역 -->
        <v-card style="border:1px solid rgba(88,166,255,0.15);">
          <v-card-title class="d-flex align-center" style="color:#E6EDF3;">
            📋 내 신청 내역
            <v-spacer />
            <v-btn icon="mdi-refresh" variant="text" color="primary" size="small"
              @click="fetchMyRequests" :loading="listLoading" />
          </v-card-title>
          <v-card-text>
            <div v-if="myRequests.length">
              <v-card v-for="r in myRequests" :key="r.id" class="mb-3 pa-3"
                variant="outlined" style="border-color:rgba(88,166,255,0.1);">
                <div class="d-flex align-center mb-2">
                  <strong class="text-h6" style="color:#E6EDF3;">{{ r.game_name }}</strong>
                  <v-spacer />
                  <v-chip :color="stageColor(r.status)" size="small" variant="tonal">
                    {{ r.status_label }}
                  </v-chip>
                </div>
                <div class="text-caption mb-2" style="color:#8B949E;">
                  {{ r.player_count }}명 · {{ formatDate(r.created_at) }}
                </div>

                <!-- 접속 정보 (ready 이후) -->
                <v-sheet v-if="r.server_address && ['ready','permission_granted','firewall_done','onboarded'].includes(r.status)"
                  style="background:#0d1117;border:1px solid rgba(88,166,255,0.1);" class="pa-3 rounded-lg mb-2">
                  <div style="font-family:monospace;color:#58A6FF;">
                    {{ r.server_address }}{{ r.server_port ? ':' + r.server_port : '' }}
                  </div>
                  <div v-if="r.server_password" style="color:#FFA726;font-size:0.85em;">
                    PW: <span style="font-family:monospace;">{{ r.server_password }}</span>
                  </div>
                  <div v-if="r.config_path" style="color:#8B949E;font-size:0.85em;">
                    설정: <span style="font-family:monospace;">{{ r.config_path }}</span>
                  </div>
                </v-sheet>

                <div v-if="r.admin_notes" style="color:#8B949E;font-size:0.85em;">
                  💬 {{ r.admin_notes }}
                </div>
              </v-card>
            </div>
            <v-alert v-else type="info" variant="tonal">
              아직 신청 내역이 없습니다.
            </v-alert>
          </v-card-text>
        </v-card>

      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()

const form = reactive({
  game_name: '',
  player_count: 1,
  preferred_time: '',
  notes: '',
})
const configFile = ref(null)

const submitLoading = ref(false)
const listLoading = ref(false)
const templatesLoading = ref(false)
const success = ref(false)
const error = ref('')
const myRequests = ref([])
const templates = ref([])
const selectedTemplate = ref(null)

const gameList = computed(() => templates.value.map(t => t.game_name))

async function fetchTemplates() {
  templatesLoading.value = true
  try {
    const res = await api.get('/api/templates/')
    templates.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    templatesLoading.value = false
  }
}

function onGameSelect(gameName) {
  selectedTemplate.value = templates.value.find(t => t.game_name === gameName) || null
}

async function downloadTemplate() {
  if (!selectedTemplate.value) return
  const res = await api.get(`/api/templates/${selectedTemplate.value.id}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = selectedTemplate.value.filename
  a.click()
  URL.revokeObjectURL(url)
}

async function submit() {
  if (!form.game_name) {
    error.value = '게임 이름은 필수입니다'
    return
  }

  submitLoading.value = true
  error.value = ''
  success.value = false

  try {
    const fd = new FormData()
    fd.append('game_name', form.game_name)
    fd.append('player_count', form.player_count)
    if (form.preferred_time) fd.append('preferred_time', form.preferred_time)
    if (form.notes) fd.append('notes', form.notes)
    const file = Array.isArray(configFile.value) ? configFile.value[0] : configFile.value
    if (file) {
      fd.append('config_file', file)
    }

    await api.post('/api/game-requests/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    success.value = true
    Object.assign(form, { game_name: '', player_count: 1, preferred_time: '', notes: '' })
    configFile.value = null
    selectedTemplate.value = null
    await fetchMyRequests()
  } catch (e) {
    error.value = e.response?.data?.detail || '신청 실패'
  } finally {
    submitLoading.value = false
  }
}

async function fetchMyRequests() {
  listLoading.value = true
  try {
    const res = await api.get('/api/game-requests/my')
    myRequests.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    listLoading.value = false
  }
}

function stageColor(s) {
  const map = {
    pending: 'warning', approved: 'success', building: 'info', ready: 'cyan',
    permission_granted: 'teal', firewall_done: 'deep-purple', onboarded: 'success', rejected: 'error',
  }
  return map[s] || 'grey'
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

onMounted(() => {
  fetchTemplates()
  fetchMyRequests()
})
</script>
