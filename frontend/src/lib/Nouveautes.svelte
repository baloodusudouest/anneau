<script>
  // 0.13 : « Mis à jour depuis votre dernière visite ». Lue une fois par ouverture de l'Anneau (après une connexion, ou au
  // premier chargement avec une session valide) : les changements de version vus par la veille depuis le dernier « Vu ».
  // Rien à dire : pas de fenêtre. « Vu » enregistre l'heure côté serveur (une pour l'Anneau, pas par navigateur).
  import { onMount, tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let changements = $state([])
  let erreur = $state('')
  let bouton = $state(null)

  onMount(async () => {
    try {
      changements = (await api.get('/api/versions/nouveautes')).changements || []
      if (changements.length) { await tick(); bouton?.focus() }
    } catch { changements = [] }          // l'Anneau répond mal : pas de fenêtre, l'écran dira le reste
  })

  async function vu() {
    erreur = ''
    try { await api.post('/api/versions/vues', { jusqu_a: changements[0]?.le }); changements = [] } catch (x) { erreur = x.message }
  }

  // « cette nuit, 05:04 », « aujourd'hui, 14:10 », « hier, 05:03 », « le 16/11, 05:02 »
  function quand(iso) {
    const d = new Date(iso), maintenant = new Date()
    const heure = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    const jour = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
    const ecart = Math.round((jour(maintenant) - jour(d)) / 86400000)
    if (ecart === 0) return (d.getHours() < 7 ? 'cette nuit, ' : "aujourd'hui, ") + heure
    if (ecart === 1) return (d.getHours() >= 22 && maintenant.getHours() < 12 ? 'cette nuit, ' : 'hier, ') + heure
    return 'le ' + d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) + ', ' + heure
  }
</script>

{#if changements.length}
  <div class="voile">
    <div class="fenetre" role="dialog" aria-modal="true" aria-labelledby="titre-nouveautes">
      <h2 id="titre-nouveautes" class="plume">Mis à jour depuis votre dernière visite</h2>
      <ul>
        {#each changements as c (c.cle + c.le)}
          <li><b>{c.tuile}</b>{#if c.machine} <small>· {c.machine}</small>{/if} {c.de} → {c.vers} <small>({quand(c.le)})</small></li>
        {/each}
      </ul>
      {#if erreur}<p class="text-sm" role="alert">{erreur}</p>{/if}
      <Button class="h-11 px-6 text-base" bind:ref={bouton} onclick={vu}>Vu</Button>
    </div>
  </div>
{/if}

<style>
  .voile { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: max(1rem, env(safe-area-inset-top)) 1rem;
           background: rgb(10 8 6 / 0.72); }
  .fenetre { display: flex; flex-direction: column; align-items: flex-start; gap: 0.9rem; width: 100%; max-width: 28rem; max-height: 85dvh;
             overflow-y: auto; padding: 1.3rem 1.4rem; border: 1px solid color-mix(in srgb, var(--app) 45%, var(--border)); border-radius: 1.1rem;
             background: var(--card); box-shadow: 0 1rem 3rem rgb(0 0 0 / 0.5); }
  .plume { margin: 0; font-family: var(--plume); font-weight: 700; font-size: 2rem; line-height: 1.05; color: var(--app); }
  ul { display: grid; gap: 0.5rem; margin: 0; padding: 0; list-style: none; font-size: 0.95rem; overflow-wrap: anywhere; }
  b { font-weight: 600; }
  small { color: var(--muted-foreground); font-size: 0.82rem; }
</style>
