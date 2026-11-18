<script>
  // L'Anneau n'a pas le rail des autres applis : son écran d'ouverture est l'anneau lui-même,
  // et sa vue réduite a sa propre colonne. Les réglages sont derrière la roue, en haut à droite.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import Connexion from './pages/Connexion.svelte'
  import Anneau from './pages/Anneau.svelte'
  import Reglages from './pages/Reglages.svelte'
  import Sauvegardes from './pages/Sauvegardes.svelte'
  import Variables from './pages/Variables.svelte'
  import Carte from './pages/Carte.svelte'

  let connecte = $state(null) // null : on ne sait pas encore
  let session = $state({ version: '' })
  // 0.10 : deux pages de plus, Sauvegardes et Variables (venues d'Atlas)
  const PAGES = { '#/reglages': 'reglages', '#/sauvegardes': 'sauvegardes', '#/variables': 'variables', '#/carte': 'carte' }   // 0.11 : la carte (ex-Atlas)
  const lirePage = () => PAGES[location.hash] || 'anneau'
  let page = $state(lirePage())

  async function verifier() {
    try { const s = await api.get('/api/session'); session = s; connecte = s.connecte } catch { connecte = false }
  }
  async function deconnecter() {
    try { await api.post('/api/deconnexion') } catch { /* déjà déconnecté */ }
    connecte = false
  }
  onMount(verifier)
</script>

<svelte:window onhashchange={() => { page = lirePage(); scrollTo(0, 0) }} />

{#if connecte === false}
  <Connexion onconnecte={verifier} />
{:else if connecte}
  {#if page === 'reglages'}
    <Reglages {session} {deconnecter} ondeconnecte={() => (connecte = false)} />
  {:else if page === 'sauvegardes'}
    <Sauvegardes ondeconnecte={() => (connecte = false)} />
  {:else if page === 'variables'}
    <Variables ondeconnecte={() => (connecte = false)} />
  {:else if page === 'carte'}
    <Carte ondeconnecte={() => (connecte = false)} />
  {:else}
    <Anneau ondeconnecte={() => (connecte = false)} onreglages={() => (location.hash = '#/reglages')} />
  {/if}
{/if}
