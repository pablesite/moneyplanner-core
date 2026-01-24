// import { createApp } from 'vue'

// import App from './App.vue'

// createApp(App).mount('#app')


import { createApp } from "vue";
import './style.css'
import { createPinia } from "pinia";
import { router } from "./router";
import App from "./App.vue";
import "./styles/app.css";

createApp(App).use(createPinia()).use(router).mount("#app");
