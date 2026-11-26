<script>
  // 0.19 : réveiller une machine (le PC de calcul) depuis sa fiche, ou depuis la fiche d'une appli qui en a besoin
  // (Millésime : « besoin: Pc de calcul »). L'ordre part vers un webhook de Home Assistant, qui envoie le signal
  // Wake-on-LAN. Confirmé dans une fenêtre ; le bouton disparaît pendant le suivi (3 min au plus) ; jamais en lecture seule.
  //  - cible : { cle, nom, reveil: { possible, raison, eteint, ordre } } (la tuile réveillable)
  //  - besoin : vrai quand on est dans la fiche d'une autre appli (on ne montre rien si la machine répond)
  import { tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { cible, besoin = false, appli = '', onfait } = $props()
  const r = $derived(cible?.reveil)
  const ordre = $derived(r?.ordre)
  const attente = $derived(ordre?.etat === 'attente')
  const montrer = $derived(!!r && (r.eteint || attente || (ordre && !besoin)))
  let confirmer = $state(false)
  let envoi = $state(false)
  let message = $state('')
  let boutonOui = $state(null)
  let declencheur = null

  async function demander(ev) {
    declencheur = ev?.currentTarget
    confirmer = true
    await tick()
    boutonOui?.focus()
  }
  function annuler() { confirmer = false; declencheur?.focus?.() }
  function clavier(ev) { if (confirmer && ev.key === 'Escape') annuler() }
  async function lancer() {
    confirmer = false
    envoi = true; message = ''
    try {
      await api.post(`/api/reveil/${encodeURIComponent(cible.cle)}`)
      await onfait?.()
    } catch (x) { message = x.message }
    envoi = false
    declencheur?.focus?.()
  }
</script>

<svelte:window onkeydown={clavier} />

{#if montrer}
<section class="reveil" aria-label={'Réveil de ' + cible.nom}>
  {#if besoin}
    <p class="text-sm">{appli || 'Cette appli'} a besoin de <strong>{cible.nom}</strong>, {attente ? 'qui se réveille.' : 'qui est éteint.'}</p>
  {/if}
  <p class="text-sm" role="status">
    {#if attente}<span class="tourne" aria-hidden="true"></span>{ordre.phrase}
    {:else if ordre}<span class:text-destructive={ordre.etat !== 'fini'}>{ordre.phrase}</span>
    {:else if !besoin}Éteint.{/if}
  </p>
  {#if !attente && r.eteint}
    <div class="boutons">
      <Button class="h-10 px-4" onclick={demander} disabled={envoi || !r.possible}>Réveiller {cible.nom}</Button>
    </div>
    {#if !r.possible && r.raison}<p class="text-sm text-muted-foreground">Pas de bouton : {r.raison}</p>{/if}
  {/if}
  {#if message}<p class="text-sm text-destructive" role="alert">{message}</p>{/if}
</section>

{#if confirmer}
  <div class="voile">
    <div class="fenetre" role="dialog" aria-modal="true" aria-labelledby="titre-reveil" aria-describedby="texte-reveil">
      <h2 id="titre-reveil" class="plume">Réveiller {cible.nom} ?</h2>
      <div id="texte-reveil" class="grid gap-2 text-sm">
        <p>Home Assistant envoie le signal de réveil par le réseau de la maison. Il répond d'habitude en une à deux minutes.</p>
        <p class="text-muted-foreground">L'Anneau suit son réveil pendant 3 minutes. Il ne l'éteint jamais.</p>
      </div>
      <div class="boutons">
        <Button class="h-11 px-5 text-base" bind:ref={boutonOui} onclick={lancer}>Réveiller</Button>
        <Button class="h-11 px-5 text-base" variant="outline" onclick={annuler}>Annuler</Button>
      </div>
    </div>
  </div>
{/if}
{/if}

<style>
  .reveil { display: grid; gap: 0.5rem; width: 100%; max-width: 40rem; text-align: left; }
  .boutons { display: flex; flex-wrap: wrap; gap: 0.5rem; }
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
