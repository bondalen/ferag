import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/RagsView.vue'),
      meta: { requireAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/rags/:id',
      name: 'rag-detail',
      component: () => import('@/views/RagDetailView.vue'),
      meta: { requireAuth: true },
      redirect: (to) => ({ name: 'rag-upload', params: to.params }),
      children: [
        {
          path: 'upload',
          name: 'rag-upload',
          component: () => import('@/views/UploadView.vue'),
        },
        {
          path: 'chat',
          name: 'rag-chat',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'members',
          name: 'rag-members',
          component: () => import('@/views/MembersView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requireAuth) return true
  const auth = useAuthStore()
  if (auth.token && !auth.user) await auth.fetchUser()
  if (!auth.token) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
