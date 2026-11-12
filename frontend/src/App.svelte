<script>
  // L'Anneau n'a pas le rail des autres applis : son écran d'ouverture est l'anneau lui-même,
  // et sa vue réduite a sa propre colonne. Les réglages sont derrière la roue, en haut à droite.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import Connexion from './pages/Connexion.svelte'
  import Anneau from './pages/Anneau.svelte'
  import Reglages from './pages/Reglages.svelte'

  let connecte = $state(null) // null : on ne sait pas encore
  let session = $state({ version: '' })
  let page = $state(location.hash === '#/reglages' ? 'reglages' : 'anneau')

  async function verifier() {
    try { const s = await api.get('/api/session'); session = s; connecte = s.connecte } catch { connecte = false }
  }
  async function deconnecter() {
    try { await api.post('/api/deconnexion') } catch { /* déjà déconnecté */ }
    connecte = false
  }
  onMount(verifier)
</script>

<svelte:window onhashchange={() => (page = location.hash === '#/reglages' ? 'reglages' : 'anneau')} />

{#if connecte === false}
  <Connexion onconnecte={verifier} />
{:else if connecte}
  {#if page === 'reglages'}
    <Reglages {session} {deconnecter} ondeconnecte={() => (connecte = false)} />
  {:else}
    <Anneau ondeconnecte={() => (connecte = false)} onreglages={() => (location.hash = '#/reglages')} />
  {/if}
{/if}
