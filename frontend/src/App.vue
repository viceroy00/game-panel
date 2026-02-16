<template>
  <v-app :theme="'dark'">
    <!-- 사이드바 -->
    <v-navigation-drawer v-if="auth.user" v-model="drawer" app
      color="surface" border="none" style="border-right: 1px solid rgba(88,166,255,0.1);">

      <div class="pa-4 pb-2">
        <div class="d-flex align-center ga-3">
          <v-avatar v-if="auth.user?.discord_avatar" :image="auth.user.discord_avatar" size="40" />
          <v-avatar v-else color="primary-darken-1" size="40"><v-icon size="20">mdi-account</v-icon></v-avatar>
          <div>
            <div class="text-body-2 font-weight-bold">{{ auth.user?.display_name || auth.user?.username }}</div>
            <div class="text-caption" style="color: #8B949E;">{{ auth.user?.is_admin ? '관리자' : '사용자' }}</div>
          </div>
        </div>
      </div>

      <v-divider class="mx-3 mb-2" style="border-color: rgba(88,166,255,0.1);" />

      <v-list density="compact" nav class="px-2">
        <v-list-item prepend-icon="mdi-view-dashboard" title="대시보드" to="/"
          rounded="lg" class="mb-1" active-color="primary" />
        <v-list-item prepend-icon="mdi-server" title="서버 제어" to="/servers"
          rounded="lg" class="mb-1" active-color="primary" />
        <v-list-item prepend-icon="mdi-gamepad-variant" title="게임 신청" to="/request"
          rounded="lg" class="mb-1" active-color="primary" />

        <template v-if="auth.user?.is_admin">
          <div class="text-caption font-weight-bold px-3 pt-3 pb-1" style="color: #484F58;">관리자</div>
          <v-list-item prepend-icon="mdi-account-group" title="사용자 관리" to="/admin/users"
            rounded="lg" class="mb-1" active-color="primary" />
          <v-list-item prepend-icon="mdi-shield-key" title="권한 관리" to="/admin/permissions"
            rounded="lg" class="mb-1" active-color="primary" />
          <v-list-item prepend-icon="mdi-ticket" title="초대 코드" to="/admin/invites"
            rounded="lg" class="mb-1" active-color="primary" />
          <v-list-item prepend-icon="mdi-clipboard-list" title="신청 관리" to="/admin/requests"
            rounded="lg" class="mb-1" active-color="primary" />
          <v-list-item prepend-icon="mdi-file-cog" title="설정 양식" to="/admin/templates"
            rounded="lg" class="mb-1" active-color="primary" />
        </template>
      </v-list>

      <template v-slot:append>
        <v-divider class="mx-3" style="border-color: rgba(88,166,255,0.1);" />
        <v-list density="compact" class="px-2 py-2">
          <v-list-item prepend-icon="mdi-logout" title="로그아웃" @click="doLogout"
            rounded="lg" base-color="error" />
        </v-list>
      </template>
    </v-navigation-drawer>

    <!-- 상단 바 -->
    <v-app-bar v-if="auth.user" app density="compact" flat
      color="surface" border="none" style="border-bottom: 1px solid rgba(88,166,255,0.1);">
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title class="text-body-1 font-weight-bold">
        <span style="color: #58A6FF;">🎮</span> Game Panel
      </v-app-bar-title>
    </v-app-bar>

    <!-- 메인 -->
    <v-main style="background: #0D1117;">
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './store/auth'

const auth = useAuthStore()
const router = useRouter()
const drawer = ref(true)

function doLogout() {
  auth.logout()
  router.push('/login')
}
</script>
