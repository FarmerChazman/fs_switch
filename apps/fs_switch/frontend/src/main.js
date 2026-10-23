import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import 'primeicons/primeicons.css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

import App from './App.vue'
import './styles.css'

// Match the neutral Frappe UI palette: quiet surfaces, dark ink buttons and
// blue links. Status colours stay semantic.
const Frappe = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#f7f7f7',
      100: '#efefef',
      200: '#e5e5e5',
      300: '#d4d4d4',
      400: '#a3a3a3',
      500: '#262626',
      600: '#1f1f1f',
      700: '#171717',
      800: '#111111',
      900: '#0a0a0a',
      950: '#000000',
    },
  },
})

const app = createApp(App)
app.use(PrimeVue, {
  theme: {
    preset: Frappe,
    options: {
      darkModeSelector: '.fs-dark',
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)
app.mount('#app')
