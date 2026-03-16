import { create } from 'zustand'

const useAuthStore = create((set) => ({
  user: null,
  isLoggedIn: false,
  isBootstrapping: true,

  setUser: (user) => set({
    user,
    isLoggedIn: Boolean(user),
    isBootstrapping: false,
  }),

  clearUser: () => set({
    user: null,
    isLoggedIn: false,
    isBootstrapping: false,
  }),

  setBootstrapping: (val) => set({ isBootstrapping: val }),
}))

export default useAuthStore
