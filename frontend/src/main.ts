import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Aura from '@primevue/themes/aura'

import App from './App.vue'
import router from './router'
import { installGuards } from './router/guards'
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

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
installGuards(router, pinia)

app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.app-dark'
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

app.mount('#app')
