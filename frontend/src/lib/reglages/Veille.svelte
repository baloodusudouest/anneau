<script>
  // 0.22 — Réglages › Services › « Applis en veille » : une case par tuile marquée conteneur:, rangée par famille.
  // Cocher = mettre en veille (l'appli, puis ses compagnons, s'arrêtent ; sa tuile reste grise, jamais rouge) ;
  // décocher = démarrer (compagnons d'abord). Une case impossible est grisée avec sa raison (le serveur la refuse aussi).
  // Une appli en veille revenue sans ordre (redéploiement, Portainer) est signalée ici et dans « À traiter ».
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'

  let { ondeconnecte } = $props()
  let v = $state(null)
  let message = $state('')
  let enVol = $state({})            // clé → vrai pendant l'envoi
  const echec = (x) => { if (x?.statut === 401) ondeconnecte?.(); else message = x?.message || String(x) }

  async function lire() { try { v = await api.get('/api/veille') } catch (x) { echec(x) } }
  onMount(() => { lire() })
  // un ordre en cours (phrase « extinction… », « démarrage… ») : relire toutes les 2,5 s jusqu'à sa fin
  const occupe = $derived(Object.values(enVol).some(Boolean) || (v?.tuiles || []).some((t) => /…$/.test(t.phrase || '')))
  $effect(() => {
    if (!occupe) return
    const t = setInterval(lire, 2500)
    return () => clearInterval(t)
  })

  const familles = $derived.by(() => {
    const m = new Map()
    for (const t of v?.tuiles || []) { if (!m.has(t.famille)) m.set(t.famille, []); m.get(t.famille).push(t) }
    return [...m.entries()]
  })
  const nb = $derived((v?.tuiles || []).filter((t) => t.en_veille).length)

  async function basculer(t, ev) {
    const voulu = ev.currentTarget.checked
    enVol = { ...enVol, [t.cle]: true }; message = ''
    try { await api.post(`/api/veille/${encodeURIComponent(t.cle)}`, { veille: voulu }) } catch (x) { echec(x); ev.currentTarget && (ev.currentTarget.checked = !voulu) }
    enVol = { ...enVol, [t.cle]: false }
    await lire()
  }
  const etat = (t) => /…$/.test(t.phrase || '') ? t.phrase
    : t.statut === 'running' ? 'tourne' : t.statut === 'exited' ? (t.en_veille ? 'en veille' : 'arrêtée') : 'état inconnu'
</script>

<section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Applis en veille" id="section-veille" tabindex="-1">
  <h2 class="text-lg font-semibold">Applis en veille{#if nb}<span class="compte">{nb}</span>{/if}</h2>
  <p class="mt-1 text-sm text-muted-foreground">
    Coche une appli que tu n'utilises pas : l'Anneau l'arrête (et ses compagnons), sa tuile reste grise, jamais rouge, et
    la sauvegarde de nuit la saute. Un clic sur sa tuile la redémarre. Watchtower la met encore à jour la nuit, sans la rallumer.
  </p>
  {#if !v}<p class="mt-2 text-sm text-muted-foreground" role="status">{message || 'Lecture…'}</p>
  {:else if !v.tuiles.length}
    <p class="mt-2 text-sm">Aucune tuile n'a de <code>conteneur:</code> dans le fichier des services.</p>
  {:else}
    {#if v.erreur}<p class="mt-2 text-sm text-muted-foreground">Portainer : {v.erreur}. Les applis cochées restent en veille (grises).</p>{/if}
    {#each familles as [famille, tuiles] (famille)}
      <fieldset class="famille">
        <legend>{famille}</legend>
        {#each tuiles as t (t.cle)}
          <label class="ligne" class:impossible={!t.possible}>
            <input type="checkbox" checked={t.en_veille} disabled={!t.possible || enVol[t.cle]} onchange={(ev) => basculer(t, ev)}
                   aria-describedby={'etat-' + t.cle} />
            <span class="nom">{t.nom}{#if t.machine === 'QNAP'}<small class="machine">QNAP</small>{/if}</span>
            <span class="etat" id={'etat-' + t.cle}>
              {#if enVol[t.cle]}envoi…{:else if t.revenue}<b class="revenue">revenue sans ordre : elle tourne</b>{:else}{etat(t)}{/if}{#if t.compagnons.length} · avec {t.compagnons.join(', ')}{/if}
              {#if !t.possible}<small>{t.pourquoi}</small>{/if}
            </span>
          </label>
        {/each}
      </fieldset>
    {/each}
  {/if}
  {#if message}<p class="mt-3 text-sm text-destructive" role="alert">{message}</p>{/if}
</section>

<style>
  section:focus { outline: none; }
  .compte { margin-left: 0.5rem; padding: 0.05rem 0.5rem; border-radius: 999px; font-size: 0.8rem; background: color-mix(in srgb, var(--eteint) 35%, transparent); }
  .famille { margin-top: 0.9rem; border: 0; padding: 0; min-width: 0; }
  .famille legend { font-size: 0.74rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted-foreground); }
  .ligne { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 0.75rem; align-items: start; min-height: 2.75rem;
           padding: 0.55rem 0; border-top: 1px solid var(--border); cursor: pointer; }
  .ligne input { width: 1.25rem; height: 1.25rem; margin-top: 0.1rem; accent-color: var(--app); }
  .ligne .nom { font-weight: 600; overflow-wrap: anywhere; }
  .ligne .etat { grid-column: 2; font-size: 0.85rem; color: var(--muted-foreground); overflow-wrap: anywhere; }
  .ligne .etat small { display: block; }
  .ligne.impossible { cursor: default; }
  .ligne.impossible .nom { color: var(--muted-foreground); }
  .machine { margin-left: 0.4rem; font-size: 0.7rem; font-weight: 600; color: var(--muted-foreground); }
  .revenue { color: var(--braise); font-weight: 600; }
  @media (min-width: 640px) {
    .ligne { grid-template-columns: auto minmax(8rem, 14rem) minmax(0, 1fr); }
    .ligne .etat { grid-column: 3; }
  }
</style>
