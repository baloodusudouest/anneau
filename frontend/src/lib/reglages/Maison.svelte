<script>
  // 0.19 — Réglages › Maison : la carte de la maison en haut, pleine largeur (ancienne page Carte, 0.11), puis les
  // disques et les dernières pannes closes (venus de l'ancienne page Réglages). Un raccourci « Maison » y mène depuis
  // l'anneau, à côté de la roue.
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

  let e = $state(null)               // /api/etat : volumes, seuil, pannes closes
  async function lire() {
    try { vue = await api.get('/api/carte') } catch (x) { if (x.statut === 401) ondeconnecte?.(); else message = x.message }
    try { e = await api.get('/api/etat') } catch { /* la carte suffit */ }
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
  const ec = $derived(vue?.etat)
  const c = $derived(vue?.carte)
  const pannes = $derived(c ? c.services.filter((s) => s.voyant === 'panne').length : 0)
  const virgule = (n) => String(n).replace('.', ',')
</script>

<section aria-label="Carte de la maison" id="section-carte" tabindex="-1">
  <h2 class="sr-only">Carte de la maison</h2>

  <div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
    {#if ec}
      {#if !ec.regle}<span>Pas réglée : <code>ANNEAU_ATLAS_DEPOT</code> et <code>ANNEAU_GITHUB_JETON</code> manquent dans la stack.</span>
      {:else if c}
        <span class="text-muted-foreground">Fabriquée par le coffre {c.genere_le ? 'il y a ' + duree(c.genere_le) : ''}{c.commit ? ' (commit ' + c.commit + ')' : ''}
          · relue {ec.essaye_le ? 'il y a ' + duree(ec.essaye_le) : '—'} · {c.services.length} services, {c.flux.length} flux{pannes ? ` · ${pannes} en panne` : ''}</span>
      {:else}<span>Pas encore reçue.</span>{/if}
      {#if ec.erreur}<span class="text-destructive" role="alert">{ec.erreur}</span>{/if}
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
</section>

{#if e}
<div class="mx-auto mt-6 grid max-w-3xl gap-3">
  <section class="rounded-2xl border bg-card p-5" aria-label="Disques" id="section-disques" tabindex="-1">
    <h2 class="text-lg font-semibold">Disques</h2>
    <p class="mt-1 text-sm">Un volume est « en panne » à partir de {virgule(e.fraicheur.seuil_disque)} % d'occupation (réglage <code>seuil_disque</code> du fichier des services).</p>
    {#if e.volumes.length}
      <ul class="mt-2 divide-y text-sm" aria-label="Volumes">
        {#each e.volumes as v}
          <li class="flex flex-wrap justify-between gap-x-4 py-1.5"><span>{v.nom}{v.machine ? ' sur ' + v.machine : ''}</span>
            <span class={v.etat === 'panne' ? 'text-[var(--lave)]' : 'text-muted-foreground'}>{v.pourcentage == null ? 'inconnu' : virgule(v.pourcentage) + ' %'}{v.etat ? ', ' + v.etat : ''}</span></li>
        {/each}
      </ul>
    {:else}
      <p class="mt-2 text-sm text-muted-foreground">{e.fraicheur.ha_attendu ? 'Home Assistant n\'a encore rien envoyé.' : 'Home Assistant n\'est pas encore branché : aucun volume n\'est surveillé.'}</p>
    {/if}
  </section>

  <section class="rounded-2xl border bg-card p-5" aria-label="Dernières pannes closes" id="section-pannes" tabindex="-1">
    <h2 class="text-lg font-semibold">Dernières pannes closes</h2>
    {#if e.closes.length}
      <ul class="mt-2 divide-y text-sm">
        {#each e.closes as p}<li class="flex flex-wrap justify-between gap-x-4 py-1.5"><span>{p.phrase}</span><span class="text-muted-foreground">close il y a {duree(p.close_le)}</span></li>{/each}
      </ul>
    {:else}<p class="mt-1 text-sm text-muted-foreground">Aucune panne close depuis le démarrage.</p>{/if}
  </section>
</div>
{/if}

<style>
  section:focus { outline: none; }
</style>
