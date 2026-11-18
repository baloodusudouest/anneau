import { mount } from 'svelte'
import '@fontsource-variable/inter'
import '@fontsource/tangerine/700.css'
import './app.css'
import App from './App.svelte'

// 0.11.2 (audit M49) : l'ancien Atlas gardait le fichier d'environnement en clair sous « atlas-environnement ».
// Atlas est retiré ; si cette mémoire existe à l'adresse de l'Anneau (Atlas ouvert ici), elle est effacée.
try { localStorage.removeItem('atlas-environnement') } catch { /* navigation privée : rien à effacer */ }

export default mount(App, { target: document.getElementById('app') })
