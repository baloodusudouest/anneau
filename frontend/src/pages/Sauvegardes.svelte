<script>
  // 0.10 : les sauvegardes des réglages, en un seul endroit (avant : liste dans Réglages et vue dans Atlas).
  // Chaque sauvegarde se déplie : par appli, version et réglages, ce qui a changé depuis la précédente, applis ratées.
  // Lecture seule ; pour remettre un réglage, c'est « Restaurer » dans l'appli (ou dans Réglages pour l'Anneau).
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { normaliser, differences, libelle } from '$lib/sauvegardes.js'
  import { sensible } from '$lib/environnement.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { ondeconnecte } = $props()
  let fichiers = $state([])          // [{date (identifiant), applis, ratees}], la plus récente d'abord
  let lues = $state({})              // identifiant → sauvegarde normalisée
  let ouverte = $state('')
  let message = $state('')
  let seulementChangees = $state(false)
  let visibles = $state({})

  async function lire() {
    message = ''
    try { fichiers = (await api.get('/api/sauvegardes')).fichiers || [] }
    catch (x) { if (x.statut === 401) ondeconnecte?.(); else message = x.message }
    if (!fichiers.length && !message) message = 'Aucune sauvegarde pour l\'instant : la première se fait à l\'heure de la collecte, ou par « Sauvegarder maintenant » dans Réglages.'
  }
  onMount(lire)

  // la précédente d'une sauvegarde : celle qui la suit dans la liste (plus ancienne)
  const precedenteDe = (id) => { const i = fichiers.findIndex((f) => f.date === id); return i >= 0 && i + 1 < fichiers.length ? fichiers[i + 1].date : '' }
  async function obtenir(id) {
    if (!id || lues[id]) return lues[id]
    lues[id] = normaliser(await api.get('/api/sauvegardes/' + encodeURIComponent(id)), id)
    return lues[id]
  }
  async function basculer(id) {
    if (ouverte === id) { ouverte = ''; return }
    ouverte = id; visibles = {}; message = ''
    try { await obtenir(id); const p = precedenteDe(id); if (p) { try { await obtenir(p) } catch { /* précédente illisible : pas de différences */ } } }
    catch (x) { message = x.message }
  }

  const NOMS = { anneau: "L'Anneau", 'kit-urgence': "Kit d'urgence", 'douze-points': 'Douze points', 'chambre-noire': 'Chambre noire', 'verif-dates-photos': 'Éphéméride' }
  const nom = (id) => NOMS[id] || id.charAt(0).toUpperCase() + id.slice(1)
  const dit = (v) => (typeof v === 'string' ? v : JSON.stringify(v))
  const masquee = (id, k) => sensible(k.toUpperCase()) && !visibles[id + '.' + k]
  function applis(id) {
    const s = lues[id], p = lues[precedenteDe(id)] || null
    if (!s) return []
    return Object.entries(s.applis)
      .map(([k, a]) => ({ k, a, d: p ? differences(a, p.applis[k] || null) : { nouvelle: false, version: null, lignes: [] } }))
      .filter((x) => !seulementChangees || x.d.nouvelle || x.d.version || x.d.lignes.length)
      .sort((x, y) => nom(x.k).localeCompare(nom(y.k), 'fr'))
  }
</script>

<main class="mx-auto max-w-3xl px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8">
  <header class="mb-5 flex flex-wrap items-end justify-between gap-3">
    <div><p class="etiquette">L'Anneau</p><h1 class="titre">Sauvegardes</h1></div>
    <nav class="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Pages">
      <a class="underline underline-offset-4" href="#/reglages">Réglages</a>
      <a class="underline underline-offset-4" href="#/variables">Variables</a>
      <a class="underline underline-offset-4" href="#/">Revenir à l'anneau</a>
    </nav>
  </header>
  <p class="text-sm text-muted-foreground">Les réglages que chaque appli maison rend à l'Anneau, une sauvegarde par jour (et une par « Sauvegarder maintenant »). Déplie une sauvegarde pour voir ce qui a changé depuis la précédente. Pour remettre un réglage : « Restaurer » dans l'appli elle-même.</p>

  {#if message}<p class="mt-3 text-sm" role="status" id="message-sauvegardes">{message}</p>{/if}

  {#if fichiers.length}
    <label class="mt-4 inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm">
      <input type="checkbox" bind:checked={seulementChangees} class="size-4 accent-[var(--app)]" /> Seulement les applis qui ont changé
    </label>
    <ul class="mt-2 grid gap-2" aria-label="Liste des sauvegardes">
      {#each fichiers as f (f.date)}
        {@const n = Object.keys(f.ratees || {}).length}
        <li class="rounded-2xl border bg-card">
          <button type="button" class="flex min-h-12 w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2 text-left" aria-expanded={ouverte === f.date} onclick={() => basculer(f.date)}>
            <span class="font-medium">{libelle(f.date)}</span>
            <span class="text-sm text-muted-foreground">{f.applis.length} appli(s){#if n}<span class="text-[var(--app)]">&nbsp;· {n} ratée(s)</span>{/if}</span>
          </button>
          {#if ouverte === f.date}
            {@const s = lues[f.date]}
            <div class="border-t px-4 pb-4 pt-3" role="region" aria-label={'Sauvegarde du ' + libelle(f.date)}>
              {#if !s}<p class="text-sm text-muted-foreground">Lecture…</p>
              {:else}
                <p class="text-sm text-muted-foreground">{precedenteDe(f.date) ? `Comparée à celle du ${libelle(precedenteDe(f.date))}.` : 'Pas de sauvegarde plus ancienne à comparer.'}
                  <a class="ml-1 underline underline-offset-4" href={`/api/sauvegardes/${f.date}?telecharger=true`} download={`sauvegarde-${f.date}.json`}>Télécharger</a></p>
                {#if s.avertissement}<p class="mt-1 text-sm text-[var(--app)]">{s.avertissement}</p>{/if}
                {#if Object.keys(s.ratees).length}
                  <div class="mt-2 rounded-xl border border-[var(--lave)]/50 p-3 text-sm" role="alert" aria-label="Applis ratées">
                    <strong>{Object.keys(s.ratees).length} appli(s) ratée(s)</strong> : leurs réglages ne sont pas dans cette sauvegarde.
                    <ul class="mt-1 list-disc pl-5">{#each Object.entries(s.ratees) as [k, r] (k)}<li class="break-words"><strong>{nom(k)}</strong>{r ? ` : ${r}` : ''}</li>{/each}</ul>
                  </div>
                {/if}
                <ul class="mt-3 grid gap-2">
                  {#each applis(f.date) as { k, a, d } (k)}
                    <li class="rounded-xl border p-3" aria-label={'Réglages de ' + nom(k)}>
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="min-w-0 flex-1 break-words font-medium">{nom(k)}</span>
                        {#if a.version}<span class="rounded-full border px-2 text-xs">{a.version}</span>{/if}
                        {#if d.nouvelle}<span class="rounded-full border border-[var(--app)] px-2 text-xs text-[var(--app)]">nouvelle</span>
                        {:else if d.version}<span class="rounded-full border border-[var(--app)] px-2 text-xs text-[var(--app)]">était {d.version.avant || '?'}</span>{/if}
                      </div>
                      {#if Object.keys(a.reglages).length || d.lignes.length}
                        <dl class="mt-2 grid gap-1 text-sm">
                          {#each Object.entries(a.reglages) as [cle, v] (cle)}
                            {@const l = d.lignes.find((x) => x.cle === cle)}
                            <div class={['grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] gap-3 rounded-lg px-2 py-1', l && 'bg-muted shadow-[inset_2px_0_0_var(--app)]']}>
                              <dt class="min-w-0 break-words"><code>{cle}</code></dt>
                              <dd class="min-w-0 break-words">
                                {#if masquee(k, cle)}<span class="text-muted-foreground">••••••</span> <button type="button" class="ml-1 underline underline-offset-4" onclick={() => (visibles[k + '.' + cle] = true)}>Afficher</button>
                                {:else}{#if l?.sorte === 'change'}<s class="text-muted-foreground">{dit(l.avant)}</s> → {/if}{dit(v)}{#if l?.sorte === 'ajoute'} <span class="text-xs text-[var(--app)]">ajouté</span>{/if}{/if}
                              </dd>
                            </div>
                          {/each}
                          {#each d.lignes.filter((x) => x.sorte === 'retire') as l (l.cle)}
                            <div class="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] gap-3 rounded-lg bg-muted px-2 py-1 shadow-[inset_2px_0_0_var(--app)]">
                              <dt class="min-w-0 break-words"><code>{l.cle}</code></dt><dd><s class="text-muted-foreground">{masquee(k, l.cle) ? '••••••' : dit(l.avant)}</s> <span class="text-xs">retiré</span></dd>
                            </div>
                          {/each}
                        </dl>
                      {:else}<p class="mt-1 text-sm text-muted-foreground">Aucun réglage rendu.</p>{/if}
                      {#if precedenteDe(f.date) && !d.nouvelle && !d.version && !d.lignes.length}<p class="mt-1 text-sm text-muted-foreground">Rien n'a changé.</p>{/if}
                    </li>
                  {:else}
                    <li class="text-sm text-muted-foreground">{seulementChangees ? 'Aucune appli n\'a changé.' : 'Aucune appli dans cette sauvegarde.'}</li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
  <div class="mt-5"><Button variant="outline" onclick={lire}>Relire la liste</Button></div>
</main>
