import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'

import App from './App.vue'
import router from './router'
import { installGuards } from './router/guards'
import { responsiveTable } from './directives/responsiveTable'
import { useUiStore } from './stores/ui'
import './styles/main.css'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Toast from 'primevue/toast'
import Badge from 'primevue/badge'
import Textarea from 'primevue/textarea'
import Divider from 'primevue/divider'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import ToggleSwitch from 'primevue/toggleswitch'
import ProgressSpinner from 'primevue/progressspinner'
import InputNumber from 'primevue/inputnumber'
import Drawer from 'primevue/drawer'

const ProjectPreset = definePreset(Aura, {
  primitive: {
    borderRadius: {
      none: '0',
      xs: '2px',
      sm: '6px',
      md: '8px',
      lg: '10px',
      xl: '14px'
    }
  },
  semantic: {
    primary: {
      50: '{indigo.50}',
      100: '{indigo.100}',
      200: '{indigo.200}',
      300: '{indigo.300}',
      400: '{indigo.400}',
      500: '{indigo.500}',
      600: '{indigo.600}',
      700: '{indigo.700}',
      800: '{indigo.800}',
      900: '{indigo.900}',
      950: '{indigo.950}'
    },
    colorScheme: {
      light: {
        primary: {
          color: '{primary.600}',
          contrastColor: '#ffffff',
          hoverColor: '{primary.700}',
          activeColor: '{primary.800}'
        },
        highlight: {
          background: '{primary.50}',
          focusBackground: '{primary.100}',
          color: '{primary.700}',
          focusColor: '{primary.800}'
        },
        surface: {
          0: '#ffffff',
          50: '#f8f9fa',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
          950: '#030712'
        }
      },
      dark: {
        primary: {
          color: '{primary.400}',
          contrastColor: '{surface.900}',
          hoverColor: '{primary.300}',
          activeColor: '{primary.200}'
        },
        highlight: {
          background: 'color-mix(in srgb, {primary.400}, transparent 84%)',
          focusBackground: 'color-mix(in srgb, {primary.400}, transparent 76%)',
          color: 'rgba(255,255,255,.87)',
          focusColor: 'rgba(255,255,255,.87)'
        },
        surface: {
          0: '#ffffff',
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617'
        }
      }
    }
  }
})

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
installGuards(router, pinia)

app.use(PrimeVue, {
  theme: {
    preset: ProjectPreset,
    options: {
      darkModeSelector: '.app-dark',
      cssLayer: false
    }
  }
})

app.use(ToastService)

app.component('PButton', Button)
app.component('PInputText', InputText)
app.component('PPassword', Password)
app.component('PCard', Card)
app.component('PDataTable', DataTable)
app.component('PColumn', Column)
app.component('PDialog', Dialog)
app.component('PTag', Tag)
app.component('PProgressBar', ProgressBar)
app.component('PToast', Toast)
app.component('PBadge', Badge)
app.component('PTextarea', Textarea)
app.component('PDivider', Divider)
app.component('PSelect', Select)
app.component('PMultiSelect', MultiSelect)
app.component('PToggleSwitch', ToggleSwitch)
app.component('PProgressSpinner', ProgressSpinner)
app.component('PInputNumber', InputNumber)
app.component('PDrawer', Drawer)

app.directive('responsive-table', responsiveTable)

useUiStore(pinia).initTheme()

app.mount('#app')
