<script>
  // L'Anneau n'a pas le rail des autres applis : son écran d'ouverture est l'anneau lui-même,
  // et sa vue réduite a sa propre colonne. Les réglages sont derrière la roue, en haut à droite.
  // 0.19 : un seul écran Réglages en cinq thèmes (#/reglages, #/reglages/<thème>[/<section>]) ; les anciennes pages
  // Variables, Sauvegardes et Carte y mènent (adresse remplacée, sans entrée de plus dans l'historique).
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { lireAdresse } from '$lib/reglages/themes.js'
  import Connexion from './pages/Connexion.svelte'
  import Anneau from './pages/Anneau.svelte'
  import Reglages from './pages/Reglages.svelte'
  import Nouveautes from '$lib/Nouveautes.svelte'

  let connecte = $state(null) // null : on ne sait pas encore
  let session = $state({ version: '' })

  function lire() {
    const a = lireAdresse(location.hash)
    if (a.page === 'reglages' && a.adresse !== location.hash) history.replaceState(null, '', a.adresse)
    return a
  }
  let ou = $state(lire())

  async function verifier() {
    try { const s = await api.get('/api/session'); session = s; connecte = s.connecte } catch { connecte = false }
  }
  async function deconnecter() {
    try { await api.post('/api/deconnexion') } catch { /* déjà déconnecté */ }
    connecte = false
  }
  function changer() {
    const avant = ou
    ou = lire()
    // une section dans le même thème : on y descend (le thème s'en charge) ; sinon on remonte en haut
    if (!(avant.page === 'reglages' && ou.page === 'reglages' && avant.theme === ou.theme && ou.section)) scrollTo(0, 0)
  }
  onMount(verifier)
</script>

<svelte:window onhashchange={changer} />

{#if connecte === false}
  <Connexion onconnecte={verifier} />
{:else if connecte}
  {#if ou.page === 'reglages'}
    <Reglages {session} {deconnecter} theme={ou.theme} section={ou.section} ondeconnecte={() => (connecte = false)} />
  {:else}
    <Anneau ondeconnecte={() => (connecte = false)} onreglages={() => (location.hash = '#/reglages')} />
  {/if}
  <!-- 0.13 : à l'ouverture (après une connexion, ou premier chargement avec une session valide), ce qui a été mis à jour
       depuis le dernier « Vu » ; montée une seule fois par ouverture, pas à chaque changement de page -->
  <Nouveautes />
{/if}
