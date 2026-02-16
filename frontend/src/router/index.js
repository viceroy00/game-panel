import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
  },
  {
    path: '/servers',
    name: 'ServerControl',
    component: () => import('../views/ServerControl.vue'),
  },
  {
    path: '/servers/:name/files',
    name: 'FileManager',
    component: () => import('../views/FileManager.vue'),
  },
  {
    path: '/request',
    name: 'GameRequest',
    component: () => import('../views/GameRequest.vue'),
  },
  // 관리자
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('../views/AdminUsers.vue'),
    meta: { admin: true },
  },
  {
    path: '/admin/permissions',
    name: 'AdminPermissions',
    component: () => import('../views/AdminPermissions.vue'),
    meta: { admin: true },
  },
  {
    path: '/admin/requests',
    name: 'AdminRequests',
    component: () => import('../views/AdminRequests.vue'),
    meta: { admin: true },
  },
  {
    path: '/admin/templates',
    name: 'AdminTemplates',
    component: () => import('../views/AdminTemplates.vue'),
    meta: { admin: true },
  },
  {
    path: '/admin/invites',
    name: 'AdminInvites',
    component: () => import('../views/AdminInvites.vue'),
    meta: { admin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) return true

  if (!auth.accessToken) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      auth.logout()
      return { name: 'Login' }
    }
  }

  if (to.meta.admin && !auth.user?.is_admin) {
    return { name: 'Dashboard' }
  }

  return true
})

export default router
