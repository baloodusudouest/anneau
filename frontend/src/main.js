import { mount } from 'svelte'
import '@fontsource-variable/inter'
import '@fontsource/tangerine/700.css'
import './app.css'
import App from './App.svelte'

export default mount(App, { target: document.getElementById('app') })
