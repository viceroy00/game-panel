<template>
  <v-container>
    <div class="d-flex align-center mb-4">
      <h1 class="text-h4 font-weight-bold" style="color:#E6EDF3;">사용자 관리</h1>
      <v-spacer />
      <v-btn color="primary" @click="showCreate = true">
        <v-icon start>mdi-plus</v-icon> 사용자 추가
      </v-btn>
    </div>

    <!-- 사용자 목록 -->
    <v-card style="border:1px solid rgba(88,166,255,0.15);">
      <v-table class="bg-transparent">
        <thead>
          <tr>
            <th style="color:#8B949E;">사용자명</th>
            <th style="color:#8B949E;">이름</th>
            <th style="color:#8B949E;">이메일</th>
            <th style="color:#8B949E;">관리자</th>
            <th style="color:#8B949E;">2FA</th>
            <th style="color:#8B949E;">상태</th>
            <th style="color:#8B949E;">액션</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="font-weight-medium">{{ u.username }}</td>
            <td>{{ u.display_name || '-' }}</td>
            <td>{{ u.email || '-' }}</td>
            <td><v-icon :color="u.is_admin ? 'warning' : 'default'" size="20">mdi-shield</v-icon></td>
            <td><v-icon :color="u.totp_enabled ? 'success' : 'default'" size="20">mdi-cellphone-key</v-icon></td>
            <td>
              <v-chip :color="u.is_active ? 'success' : 'error'" size="small" variant="tonal">
                {{ u.is_active ? '활성' : '비활성' }}
              </v-chip>
            </td>
            <td>
              <v-btn icon="mdi-pencil" size="small" variant="text" color="primary" @click="editUser(u)" />
              <v-btn icon="mdi-delete" size="small" variant="text" color="error" @click="deleteUser(u)" />
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- 사용자 생성 다이얼로그 -->
    <v-dialog v-model="showCreate" max-width="500">
      <v-card style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title style="color:#E6EDF3;">새 사용자 추가</v-card-title>
        <v-card-text>
          <v-text-field v-model="newUser.username" label="사용자명" />
          <v-text-field v-model="newUser.password" label="비밀번호" type="password" />
          <v-text-field v-model="newUser.display_name" label="표시 이름" />
          <v-text-field v-model="newUser.email" label="이메일" />
          <v-checkbox v-model="newUser.is_admin" label="관리자 권한" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" color="primary" @click="showCreate = false">취소</v-btn>
          <v-btn color="primary" @click="createUser">생성</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const users = ref([])
const showCreate = ref(false)
const newUser = reactive({
  username: '', password: '', display_name: '', email: '', is_admin: false,
})

async function fetchUsers() {
  const res = await api.get('/api/auth/users')
  users.value = res.data
}

async function createUser() {
  try {
    await api.post('/api/auth/users', newUser)
    showCreate.value = false
    Object.assign(newUser, { username: '', password: '', display_name: '', email: '', is_admin: false })
    await fetchUsers()
  } catch (e) {
    alert(e.response?.data?.detail || '생성 실패')
  }
}

async function deleteUser(u) {
  if (!confirm(`${u.username} 계정을 삭제하시겠습니까?`)) return
  try {
    await api.delete(`/api/auth/users/${u.id}`)
    await fetchUsers()
  } catch (e) {
    alert(e.response?.data?.detail || '삭제 실패')
  }
}

function editUser(u) {
  // TODO: 수정 다이얼로그
  alert('수정 기능은 Phase 4에서 구현')
}

onMounted(fetchUsers)
</script>
