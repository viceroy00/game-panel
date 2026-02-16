<template>
  <v-container>
    <h1 class="text-h4 mb-4 font-weight-bold" style="color:#E6EDF3;">게임 설정 양식 관리</h1>

    <!-- 업로드 폼 -->
    <v-card class="mb-6 pa-4" style="border:1px solid rgba(88,166,255,0.15);">
      <v-card-title class="text-h6" style="color:#E6EDF3;">📤 새 양식 업로드</v-card-title>
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" sm="4">
            <v-text-field v-model="uploadForm.game_name" label="게임 이름"
              prepend-inner-icon="mdi-gamepad-variant" placeholder="Palworld" />
          </v-col>
          <v-col cols="12" sm="5">
            <v-file-input v-model="uploadForm.file" label="엑셀 양식 파일" accept=".xlsx,.xls"
              prepend-icon="mdi-file-excel" variant="outlined" density="compact" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-btn color="primary" :loading="uploading" @click="uploadTemplate" block>
              <v-icon start>mdi-upload</v-icon> 업로드
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
      <v-alert v-if="uploadMsg" :type="uploadOk ? 'success' : 'error'" variant="tonal" class="mx-4 mb-4">
        {{ uploadMsg }}
      </v-alert>
    </v-card>

    <!-- 기존 양식 목록 -->
    <v-card style="border:1px solid rgba(88,166,255,0.15);">
      <v-card-title class="d-flex align-center" style="color:#E6EDF3;">
        📋 등록된 양식
        <v-spacer />
        <v-btn icon="mdi-refresh" variant="text" color="primary" size="small" @click="fetchTemplates" />
      </v-card-title>
      <v-table class="bg-transparent">
        <thead>
          <tr>
            <th style="color:#8B949E;">게임</th>
            <th style="color:#8B949E;">파일명</th>
            <th style="color:#8B949E;">등록일</th>
            <th style="color:#8B949E;">액션</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in templates" :key="t.id">
            <td class="font-weight-medium">{{ t.game_name }}</td>
            <td><code style="color:#79C0FF;">{{ t.filename }}</code></td>
            <td style="color:#8B949E;">{{ formatDate(t.created_at) }}</td>
            <td>
              <v-btn size="small" variant="text" color="primary" @click="download(t)">
                <v-icon size="16">mdi-download</v-icon> 다운로드
              </v-btn>
              <v-btn size="small" variant="text" color="error" @click="remove(t)">
                <v-icon size="16">mdi-delete</v-icon> 삭제
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
      <v-card-text v-if="!templates.length">
        <v-alert type="info" variant="tonal">등록된 양식이 없습니다.</v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const templates = ref([])
const uploading = ref(false)
const uploadMsg = ref('')
const uploadOk = ref(false)
const uploadForm = reactive({ game_name: '', file: null })

async function fetchTemplates() {
  const res = await api.get('/api/templates/')
  templates.value = res.data
}

async function uploadTemplate() {
  const file = Array.isArray(uploadForm.file) ? uploadForm.file[0] : uploadForm.file
  if (!uploadForm.game_name || !file) {
    uploadMsg.value = '게임 이름과 파일을 모두 입력해주세요'
    uploadOk.value = false
    return
  }
  uploading.value = true
  uploadMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('game_name', uploadForm.game_name)
    fd.append('file', file)
    const res = await api.post('/api/templates/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    uploadMsg.value = res.data.message
    uploadOk.value = true
    uploadForm.game_name = ''
    uploadForm.file = null
    await fetchTemplates()
  } catch (e) {
    uploadMsg.value = e.response?.data?.detail || '업로드 실패'
    uploadOk.value = false
  } finally {
    uploading.value = false
  }
}

async function download(t) {
  const res = await api.get(`/api/templates/${t.id}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url; a.download = t.filename; a.click()
  URL.revokeObjectURL(url)
}

async function remove(t) {
  if (!confirm(`'${t.game_name}' 양식을 삭제하시겠습니까?`)) return
  try {
    await api.delete(`/api/templates/${t.id}`)
    await fetchTemplates()
  } catch (e) {
    alert(e.response?.data?.detail || '삭제 실패')
  }
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ko-KR')
}

onMounted(fetchTemplates)
</script>
