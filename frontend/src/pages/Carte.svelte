<script>
  // 0.11 : la carte de la maison (ex-Atlas), ouverte depuis Réglages. Elle est fabriquée par le coffre à chaque envoi
  // et relue par l'Anneau toutes les heures ; chaque service porte le voyant de sa tuile. Graphe sur les écrans larges,
  // liste sur téléphone.
  import { onMount } from 'svelte'
  import { SvelteFlowProvider } from '@xyflow/svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import Graphe from '$lib/carte/Graphe.svelte'
  import Liste from '$lib/carte/Liste.svelte'

  let { ondeconnecte } = $props()
  let vue = $state(null)             // { etat, carte }
  let message = $state('')
  let attente = $state(false)
  let large = $state(typeof window !== 'undefined' ? window.matchMedia('(min-width: 900px)').matches : true)
  let forcerListe = $state(false)

  async function lire() {
    try { vue = await api.get('/api/carte') } catch (x) { if (x.statut === 401) ondeconnecte?.(); else message = x.message }
  }
  async function relire() {
    attente = true; message = ''
    try { vue = await api.post('/api/carte/relire'); message = vue.etat.erreur ? '' : 'Carte relue.' } catch (x) { message = x.message }
    attente = false
  }
  onMount(() => {
    lire()
    const m = window.matchMedia('(min-width: 900px)')
    const f = () => (large = m.matches)
    m.addEventListener('change', f)
    const t = setInterval(lire, 60000)          // les voyants suivent la sonde
    return () => { m.removeEventListener('change', f); clearInterval(t) }
  })
  const e = $derived(vue?.etat)
  const c = $derived(vue?.carte)
  const pannes = $derived(c ? c.services.filter((s) => s.voyant === 'panne').length : 0)
</script>

<main class="mx-auto px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))] md:px-6 md:pt-6">
  <header class="mb-3 flex flex-wrap items-end justify-between gap-3">
    <div><p class="etiquette">L'Anneau › Réglages</p><h1 class="titre">Carte de la maison</h1></div>
    <nav class="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Pages">
      <a class="underline underline-offset-4" href="#/reglages">Réglages</a>
      <a class="underline underline-offset-4" href="#/">Revenir à l'anneau</a>
    </nav>
  </header>

  <div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
    {#if e}
      {#if !e.regle}<span>Pas réglée : <code>ANNEAU_ATLAS_DEPOT</code> et <code>ANNEAU_GITHUB_JETON</code> manquent dans la stack.</span>
      {:else if c}
        <span class="text-muted-foreground">Fabriquée par le coffre {c.genere_le ? 'il y a ' + duree(c.genere_le) : ''}{c.commit ? ' (commit ' + c.commit + ')' : ''}
          · relue {e.essaye_le ? 'il y a ' + duree(e.essaye_le) : '—'} · {c.services.length} services, {c.flux.length} flux{pannes ? ` · ${pannes} en panne` : ''}</span>
      {:else}<span>Pas encore reçue.</span>{/if}
      {#if e.erreur}<span class="text-destructive" role="alert">{e.erreur}</span>{/if}
    {/if}
    <Button variant="outline" size="sm" onclick={relire} disabled={attente}>{attente ? 'Lecture…' : 'Relire la carte'}</Button>
    {#if large && c}<button class="text-sm underline underline-offset-4" onclick={() => (forcerListe = !forcerListe)}>{forcerListe ? 'Voir la carte' : 'Voir en liste'}</button>{/if}
    {#if message}<span role="status">{message}</span>{/if}
  </div>

  {#if c}
    {#if large && !forcerListe}
      <SvelteFlowProvider><Graphe carte={c} /></SvelteFlowProvider>
    {:else}
      <div class="mx-auto max-w-3xl"><Liste carte={c} /></div>
    {/if}
    {#if c.hors_carte?.length}
      <p class="mt-3 text-sm text-muted-foreground">Tuiles de l'Anneau qui ne sont sur aucune carte : {c.hors_carte.map((t) => t.nom).join(', ')}.</p>
    {/if}
  {/if}
</main>
