import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Vuetify
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        dark: true,
        colors: {
          background: '#0D1117',
          surface: '#161B22',
          'surface-variant': '#1C2333',
          'on-surface-variant': '#8B949E',
          primary: '#58A6FF',
          'primary-darken-1': '#1F6FEB',
          secondary: '#3D5AFE',
          accent: '#79C0FF',
          success: '#3FB950',
          warning: '#D29922',
          error: '#F85149',
          info: '#58A6FF',
        },
      },
    },
  },
  defaults: {
    VBtn: { variant: 'flat', rounded: 'lg', style: 'text-transform:none; font-weight:600; letter-spacing:0;' },
    VCard: { rounded: 'lg', elevation: 0 },
    VTextField: { variant: 'outlined', density: 'comfortable', color: 'primary' },
    VSelect: { variant: 'outlined', density: 'comfortable', color: 'primary' },
    VChip: { rounded: 'lg' },
    VAlert: { rounded: 'lg', border: false },
    VCheckbox: { color: 'primary' },
  },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(vuetify)
app.mount('#app')
