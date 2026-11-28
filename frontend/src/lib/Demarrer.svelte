<script>
  // 0.22 : un clic sur une tuile grise « en veille » ouvre cette fenêtre. « Démarrer » sort l'appli de la veille
  // (compagnons d'abord, puis l'appli) ; la tuile tourne ensuite jusqu'au vert. Le serveur vérifie tout (session, origine,
  // liste blanche, interdits, lecture seule) : on n'envoie que la clé de la tuile.
  import { onMount, tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { s, onfait, onferme, onfiche } = $props()
  let attente = $state(false)
  let message = $state('')
  let boutonOui = $state(null)
  const declencheur = typeof document !== 'undefined' ? document.activeElement : null

  onMount(async () => { await tick(); boutonOui?.focus() })

  function fermer() { onferme?.(); declencheur?.focus?.() }
  async function demarrer() {
    attente = true; message = ''
    try {
      await api.post(`/api/veille/${encodeURIComponent(s.cle)}`, { veille: false })
      await onfait?.()
      fermer()
    } catch (x) { message = x.message }
    attente = false
  }
  function clavier(ev) { if (ev.key === 'Escape' && !attente) fermer() }
</script>

<svelte:window onkeydown={clavier} />

<div class="voile">
  <div class="fenetre" role="dialog" aria-modal="true" aria-labelledby="titre-demarrer" aria-describedby="texte-demarrer">
    <h2 id="titre-demarrer" class="plume">Démarrer {s.nom} ?</h2>
    <div id="texte-demarrer" class="grid gap-2 text-sm">
      <p>{s.nom} est en veille. Démarrée, elle sort de la veille et tourne jusqu'à ce que tu la remettes en veille.</p>
      {#if s.conteneur?.compagnons?.length}<p class="text-muted-foreground">Ses compagnons ({s.conteneur.compagnons.join(', ')}) démarrent d'abord.</p>{/if}
      {#if s.conteneur?.lecture_seule}<p class="text-muted-foreground">Lecture seule : l'Anneau ne donne aucun ordre à Portainer.</p>{/if}
      {#if message}<p class="text-destructive" role="alert">{message}</p>{/if}
    </div>
    <div class="boutons">
      <Button class="h-11 px-5 text-base" bind:ref={boutonOui} onclick={demarrer} disabled={attente || s.conteneur?.lecture_seule}>{attente ? 'Démarrage…' : 'Démarrer'}</Button>
      <Button class="h-11 px-5 text-base" variant="outline" onclick={fermer} disabled={attente}>Annuler</Button>
    </div>
    <button type="button" class="lien" onclick={() => { onfiche?.(); onferme?.() }}>Voir sa fiche</button>
  </div>
</div>

<style>
  .voile { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: max(1rem, env(safe-area-inset-top)) 1rem;
           background: rgb(10 8 6 / 0.72); }
  .fenetre { display: flex; flex-direction: column; align-items: flex-start; gap: 0.9rem; width: 100%; max-width: 28rem; max-height: 85dvh;
             overflow-y: auto; padding: 1.3rem 1.4rem; border: 1px solid color-mix(in srgb, var(--app) 45%, var(--border)); border-radius: 1.1rem;
             background: var(--card); box-shadow: 0 1rem 3rem rgb(0 0 0 / 0.5); text-align: left; }
  .plume { margin: 0; font-family: var(--plume); font-weight: 700; font-size: 2rem; line-height: 1.05; color: var(--app); overflow-wrap: anywhere; }
  .boutons { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .lien { background: none; border: 0; padding: 0; color: var(--muted-foreground); text-decoration: underline; font-size: 0.85rem; cursor: pointer; }
</style>
