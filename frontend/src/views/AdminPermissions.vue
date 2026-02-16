<template>
  <v-container>
    <div class="d-flex align-center mb-4">
      <h1 class="text-h4 font-weight-bold" style="color:#E6EDF3;">권한 관리</h1>
      <v-spacer />
      <v-btn color="primary" @click="openGrantDialog">
        <v-icon start>mdi-plus</v-icon> 권한 부여
      </v-btn>
    </div>

    <v-card style="border:1px solid rgba(88,166,255,0.15);">
      <v-table class="bg-transparent">
        <thead>
          <tr>
            <th style="color:#8B949E;">사용자</th>
            <th style="color:#8B949E;">컨테이너</th>
            <th style="color:#8B949E;">허용 액션</th>
            <th style="color:#8B949E;">부여일</th>
            <th style="color:#8B949E;">삭제</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in permissions" :key="p.id">
            <td class="font-weight-medium">{{ p.username }}</td>
            <td><code style="color:#79C0FF;">{{ p.container_name }}</code></td>
            <td>
              <v-chip v-for="a in p.actions" :key="a" size="x-small" color="primary" variant="tonal" class="mr-1">{{ a }}</v-chip>
            </td>
            <td>{{ p.granted_at }}</td>
            <td>
              <v-btn icon="mdi-delete" size="small" variant="text" color="error" @click="revoke(p.id)" />
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- 권한 부여 다이얼로그 -->
    <v-dialog v-model="showGrant" max-width="500">
      <v-card style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title style="color:#E6EDF3;">권한 부여</v-card-title>
        <v-card-text>
          <v-select v-model="grant.user_id" :items="users" item-title="username"
            item-value="id" label="사용자" />
          <v-select v-model="grant.container_name" :items="containers" item-title="name"
            item-value="name" label="컨테이너">
            <template #item="{ item, props }">
              <v-list-item v-bind="props">
                <template #append>
                  <v-chip :color="item.raw.status === 'running' ? 'success' : 'default'" size="x-small" variant="tonal">{{ item.raw.status }}</v-chip>
                </template>
              </v-list-item>
            </template>
          </v-select>
          <v-select v-model="grant.actions" :items="allActions" label="액션" multiple chips />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" color="primary" @click="showGrant = false">취소</v-btn>
          <v-btn color="primary" @click="grantPermission">부여</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const permissions = ref([])
const users = ref([])
const containers = ref([])
const showGrant = ref(false)
const allActions = ['start', 'stop', 'restart', 'logs', 'files', 'rcon', 'config', 'backup']
const grant = reactive({ user_id: '', container_name: '', actions: [] })

async function fetchPermissions() {
  const res = await api.get('/api/permissions/')
  permissions.value = res.data
}

async function fetchUsers() {
  const res = await api.get('/api/auth/users')
  users.value = res.data
}

async function fetchContainers() {
  try {
    const res = await api.get('/api/containers/')
    containers.value = res.data
  } catch (e) {
    containers.value = []
  }
}

async function grantPermission() {
  try {
    await api.post('/api/permissions/', grant)
    showGrant.value = false
    await fetchPermissions()
  } catch (e) {
    alert(e.response?.data?.detail || '권한 부여 실패')
  }
}

async function openGrantDialog() {
  await fetchContainers()
  grant.user_id = ''
  grant.container_name = ''
  grant.actions = []
  showGrant.value = true
}

async function revoke(id) {
  if (!confirm('이 권한을 삭제하시겠습니까?')) return
  await api.delete(`/api/permissions/${id}`)
  await fetchPermissions()
}

onMounted(() => {
  fetchPermissions()
  fetchUsers()
  fetchContainers()
})
</script>
