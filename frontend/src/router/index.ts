import { createRouter, createWebHistory, START_LOCATION } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ROUTE_NAMES, ROUTES } from '@/constants'
import { hasValidStoredAdminSession } from '@/utils/auth-storage'

const publicPageMeta = {
  showGlobalControls: true,
  showRouteLoading: false,
  routeTransition: 'transfer-fade'
}

const adminPageMeta = {
  requiresAuth: true,
  showGlobalControls: false,
  showRouteLoading: false
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: ROUTE_NAMES.RETRIEVE,
    component: () => import('@/views/RelayView.vue'),
    meta: {
      ...publicPageMeta,
      title: 'retrieve'
    }
  },
  {
    path: ROUTES.SEND,
    name: ROUTE_NAMES.SEND,
    redirect: '/'
  },
  {
    path: ROUTES.ADMIN,
    name: ROUTE_NAMES.ADMIN,
    component: () => import('@/layout/AdminLayout/AdminLayout.vue'),
    redirect: ROUTES.DASHBOARD,
    meta: adminPageMeta,
    children: [
      {
        path: 'dashboard',
        name: ROUTE_NAMES.DASHBOARD,
        component: () => import('@/views/manage/DashboardView.vue'),
        meta: {
          ...adminPageMeta,
          title: 'dashboard'
        }
      },
      {
        path: 'files',
        name: ROUTE_NAMES.FILE_MANAGE,
        component: () => import('@/views/manage/FileManageView.vue'),
        meta: {
          ...adminPageMeta,
          title: 'files'
        }
      },
      { path: 'local', redirect: ROUTES.DASHBOARD },
      { path: 'mcp', redirect: ROUTES.DASHBOARD },
      {
        path: 'settings',
        name: ROUTE_NAMES.SETTINGS,
        component: () => import('@/views/manage/SystemSettingsView.vue'),
        meta: {
          ...adminPageMeta,
          title: 'settings'
        }
      }
    ]
  },
  {
    path: ROUTES.LOGIN,
    name: ROUTE_NAMES.LOGIN,
    component: () => import('@/views/manage/LoginView.vue'),
    meta: {
      showGlobalControls: true,
      showRouteLoading: true,
      title: 'login'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: ROUTES.HOME
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, from) => {
  if (from === START_LOCATION && to.path === ROUTES.HOME && to.hash.startsWith('#/')) {
    const legacy = to.fullPath.slice(to.fullPath.indexOf('#') + 1)
    const target = router.resolve(legacy)
    if (target.path !== ROUTES.HOME &&
        (target.name || target.matched.some((record) => record.path === ROUTES.ADMIN))) {
      return { path: target.path, query: target.query, hash: target.hash, replace: true }
    }
  }

  if (to.meta.requiresAuth && !hasValidStoredAdminSession()) {
    return {
      path: ROUTES.LOGIN,
      query: {
        redirect: to.fullPath
      }
    }
  }
})

export default router
