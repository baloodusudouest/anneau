<script>
  // 0.17 : le conteneur d'une tuile marquée « conteneur: » (Portainer). Sur la fiche de la tuile et dans la fiche « État ».
  // 0.17.1 : « Mettre à jour » passe par Watchtower (absent sans Watchtower ou avec l'étiquette watchtower.enable=false :
  // la fiche dit pourquoi) ; Allumer et Éteindre restent par Portainer.
  //  - Allumé : « Éteindre » et « Mettre à jour » (confirmation dans une fenêtre) ; mémoire et processeur (lus à l'ouverture).
  //  - Éteint : « Allumer » (sans confirmation) et « Allumer et mettre à jour » (confirmation) ; âge de l'image.
  //  - Pendant un ordre : la phrase (« démarrage… », « mise à jour en cours… ») ; l'écran se relit plus souvent.
  // Le serveur vérifie tout (session, origine, liste blanche, interdits, étiquette de la stack, lecture seule) : ici, on
  // n'envoie que la clé de la tuile et le geste, jamais un nom de conteneur.
  import { tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { s, onfait } = $props()
  const c = $derived(s.conteneur)
  let stats = $state(null)
  let message = $state('')
  let attente = $state(false)
  let confirmer = $state(null)        // geste à confirmer (fenêtre)
  let boutonOui = $state(null)
  let declencheur = null

  const enCours = $derived(c?.ordre?.etat === 'en_cours')
  const eteint = $derived(c?.statut === 'exited')
  const date = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) : '')
  const mo = (n) => (n == null ? '' : n < 1073741824 ? `${Math.round(n / 1048576)} Mo` : `${(n / 1073741824).toFixed(1).replace('.', ',')} Go`)
  const age = (n) => (n == null ? '' : n === 0 ? "aujourd'hui" : n === 1 ? 'il y a 1 jour' : `il y a ${n} jours`)
  const TEXTES = {
    eteindre: { titre: (n) => `Éteindre ${n} ?`, oui: 'Éteindre' },
    'mettre-a-jour': { titre: (n) => `Mettre à jour ${n} ?`, oui: 'Mettre à jour' },
    'allumer-et-mettre-a-jour': { titre: (n) => `Allumer et mettre à jour ${n} ?`, oui: 'Allumer et mettre à jour' },
  }

  // mémoire et processeur : lus à l'ouverture, et de nouveau quand le conteneur se rallume (pas à chaque relecture)
  const cleStats = $derived(c?.gerable && c.statut === 'running' ? s.cle : '')
  $effect(() => {
    const k = cleStats
    stats = null
    if (k) api.get(`/api/conteneurs/${encodeURIComponent(k)}/stats`).then((r) => { if (k === cleStats) stats = r }).catch(() => {})
  })

  async function lancer(geste) {
    confirmer = null
    attente = true; message = ''
    try {
      await api.post(`/api/conteneurs/${encodeURIComponent(s.cle)}/${geste}`)
      await onfait?.()
    } catch (x) { message = x.message }
    attente = false
    declencheur?.focus?.()
  }
  async function demander(geste, ev) {
    declencheur = ev?.currentTarget
    if (geste === 'allumer') return lancer(geste)
    confirmer = geste
    await tick()
    boutonOui?.focus()
  }
  function annuler() { confirmer = null; declencheur?.focus?.() }
  function clavier(ev) { if (confirmer && ev.key === 'Escape') annuler() }
</script>

<svelte:window onkeydown={clavier} />

{#if c}
<section class="conteneur" aria-label={'Conteneur de ' + s.nom}>
  <h2 class="etiquette">Conteneur</h2>
  {#if !c.gerable}
    <p class="text-sm text-muted-foreground">Pas de bouton : {c.pourquoi}.</p>
  {:else}
    <p class="text-sm" role="status">
      {#if enCours}<span class="tourne" aria-hidden="true"></span>{c.ordre.phrase}
      {:else if eteint}Éteint{c.image_date ? ` · image du ${date(c.image_date)}, ${age(c.image_age)} (plus mise à jour la nuit tant qu'il est éteint)` : ''}.
      {:else}Allumé{c.image_date ? ` · image du ${date(c.image_date)}` : ''}{stats ? ` · mémoire ${mo(stats.memoire)} · processeur ${String(stats.processeur).replace('.', ',')} %` : ''}.{/if}
    </p>
    {#if c.ordre && !enCours}
      <p class="text-sm" class:text-destructive={c.ordre.etat !== 'fini'}>Dernier ordre : {c.ordre.phrase}{c.ordre.detail ? ` (${c.ordre.detail})` : ''}</p>
    {:else if enCours && c.ordre.detail}
      <p class="text-sm text-muted-foreground">{c.ordre.detail}</p>
    {/if}
    {#if c.lecture_seule}
      <p class="text-sm text-muted-foreground">Lecture seule : l'Anneau ne donne aucun ordre à Portainer.</p>
    {/if}
    <div class="boutons">
      {#if eteint}
        <Button class="h-10 px-4" onclick={(ev) => demander('allumer', ev)} disabled={attente || enCours || c.lecture_seule}>Allumer</Button>
        {#if c.maj}<Button class="h-10 px-4" variant="outline" onclick={(ev) => demander('allumer-et-mettre-a-jour', ev)} disabled={attente || enCours || c.lecture_seule}>Allumer et mettre à jour</Button>{/if}
      {:else}
        <Button class="h-10 px-4" variant="outline" onclick={(ev) => demander('eteindre', ev)} disabled={attente || enCours || c.lecture_seule || c.statut !== 'running'}>Éteindre</Button>
        {#if c.maj}<Button class="h-10 px-4" variant="outline" onclick={(ev) => demander('mettre-a-jour', ev)} disabled={attente || enCours || c.lecture_seule}>Mettre à jour</Button>{/if}
      {/if}
    </div>
    {#if !c.maj && c.maj_pourquoi}<p class="text-sm text-muted-foreground">{c.maj_pourquoi}</p>{/if}
    {#if message}<p class="text-sm text-destructive" role="alert">{message}</p>{/if}
    {#if c.redemarrage === 'always'}
      <p class="text-sm avert">Redémarrage « always » : éteint, il se rallumera au redémarrage du NAS.</p>
    {/if}
    <p class="text-xs text-muted-foreground">Un redéploiement de la stack le rallume. Mettre à jour demande à Watchtower la dernière image (sans relire la stack).</p>
  {/if}
  {#if c.erreur}<p class="text-xs text-muted-foreground">Portainer : {c.erreur}.</p>{/if}
</section>

{#if confirmer}
  <div class="voile">
    <div class="fenetre" role="dialog" aria-modal="true" aria-labelledby="titre-confirmer" aria-describedby="texte-confirmer">
      <h2 id="titre-confirmer" class="plume">{TEXTES[confirmer].titre(s.nom)}</h2>
      <div id="texte-confirmer" class="grid gap-2 text-sm">
        {#if confirmer === 'eteindre'}
          <p>Ses données restent sur le disque. Éteint, il n'est plus mis à jour la nuit.</p>
          {#if c.redemarrage === 'always'}<p class="avert">Il se rallumera au redémarrage du NAS (redémarrage « always »).</p>{/if}
          <p class="text-muted-foreground">Un redéploiement de la stack le rallume.</p>
        {:else}
          {#if confirmer === 'allumer-et-mettre-a-jour'}<p>Portainer l'allume d'abord (Watchtower ignore un conteneur éteint).</p>{/if}
          <p>Watchtower télécharge la dernière image et recrée le conteneur : quelques minutes (plus s'il est déjà en train de tout mettre à jour). Ses données restent sur le disque.</p>
          <p class="text-muted-foreground">Tout autre conteneur allumé de la même image est mis à jour aussi. La stack n'est pas redéployée : une variable changée dans la stack n'est pas prise.</p>
        {/if}
      </div>
      <div class="boutons">
        <Button class="h-11 px-5 text-base" bind:ref={boutonOui} onclick={() => lancer(confirmer)}>{TEXTES[confirmer].oui}</Button>
        <Button class="h-11 px-5 text-base" variant="outline" onclick={annuler}>Annuler</Button>
      </div>
    </div>
  </div>
{/if}
{/if}

<style>
  .conteneur { display: grid; gap: 0.5rem; width: 100%; max-width: 40rem; text-align: left; }
  .conteneur h2 { margin: 0; }
  .boutons { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .avert { color: var(--braise); }
  .tourne { display: inline-block; width: 0.8rem; height: 0.8rem; margin-right: 0.45rem; vertical-align: -0.1rem; border-radius: 50%;
            border: 2px solid color-mix(in srgb, var(--spectre) 30%, transparent); border-top-color: var(--spectre); animation: tourne 0.9s linear infinite; }
  @keyframes tourne { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .tourne { animation: none; } }
  .voile { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: max(1rem, env(safe-area-inset-top)) 1rem;
           background: rgb(10 8 6 / 0.72); }
  .fenetre { display: flex; flex-direction: column; align-items: flex-start; gap: 0.9rem; width: 100%; max-width: 28rem; max-height: 85dvh;
             overflow-y: auto; padding: 1.3rem 1.4rem; border: 1px solid color-mix(in srgb, var(--app) 45%, var(--border)); border-radius: 1.1rem;
             background: var(--card); box-shadow: 0 1rem 3rem rgb(0 0 0 / 0.5); text-align: left; }
  .plume { margin: 0; font-family: var(--plume); font-weight: 700; font-size: 2rem; line-height: 1.05; color: var(--app); overflow-wrap: anywhere; }
</style>
