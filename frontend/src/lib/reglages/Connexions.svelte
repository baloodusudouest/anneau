<script>
  // 0.19 — Réglages › Connexions : les services que l'Anneau joint lui-même (fiches communes, contrat 3 : Portainer,
  // Watchtower, GitHub, Home Assistant), puis ce que Home Assistant envoie. « Vérifier » ne teste que ce service et
  // ne donne jamais d'ordre (la fiche Home Assistant n'appelle jamais le webhook de réveil).
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import FicheService from '$lib/services/FicheService.svelte'

  let { ondeconnecte } = $props()
  let connexions = $state(null)
  let e = $state(null)
  let enCours = $state({})
  let messages = $state({})
  let annonces = $state({})
  async function lire() {
    try { connexions = await api.get('/api/maison/services') } catch (x) { if (x.statut === 401) return ondeconnecte?.(); connexions = { services: [], erreur: x.message } }
    try { e = await api.get('/api/etat') } catch { e = null }
  }
  async function verifier(f) {
    enCours = { ...enCours, [f.id]: 'verifier' }; messages = { ...messages, [f.id]: '' }
    try {
      const n = await api.post(`/api/maison/services/${encodeURIComponent(f.id)}/verifier`)
      connexions = { ...connexions, services: connexions.services.map((x) => (x.id === n.id ? n : x)) }
      annonces = { ...annonces, [f.id]: `${n.nom} : ${n.etat === 'repond' ? 'répond' : n.etat === 'ne_repond_pas' ? 'ne répond pas' : n.etat}.` }
    } catch (x) { messages = { ...messages, [f.id]: x.message } }
    enCours = { ...enCours, [f.id]: '' }
  }
  onMount(lire)
</script>

<section class="rounded-2xl border bg-card p-5" aria-label="Connexion" id="section-services" tabindex="-1">
  <h2 class="text-lg font-semibold">Services joints par l'Anneau</h2>
  <p class="mt-1 text-sm text-muted-foreground">Ce que l'Anneau lit et écrit chez chacun. Les applis maison ont leurs fiches dans leur fiche « État », sur l'anneau.</p>
  {#if !connexions}<p class="mt-2 text-sm text-muted-foreground">Lecture…</p>
  {:else if connexions.erreur}<p class="mt-2 text-sm text-destructive" role="alert">{connexions.erreur}</p>
  {:else}
    <ul class="mt-3 grid gap-3" aria-label="Services de l'Anneau">
      {#each connexions.services as f (f.id)}
        <li><FicheService service={f} simule={connexions.simule} titreNiveau={3} enCours={enCours[f.id] || ''} message={messages[f.id] || ''}
                          annonce={annonces[f.id] || ''} onverifier={verifier} /></li>
      {/each}
    </ul>
  {/if}
</section>

<section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Home Assistant" id="section-home-assistant" tabindex="-1">
  <h2 class="text-lg font-semibold">Ce que Home Assistant envoie</h2>
  {#if e}
    <p class="mt-1 text-sm">
      {#if !e.fraicheur.ha_attendu}Pas encore branché. L'Anneau attend que Home Assistant lui envoie l'état des machines ; il ne détient aucun jeton de Home Assistant.
      {:else if e.fraicheur.ha_recu_le}Dernier envoi de l'état des machines reçu il y a {duree(e.fraicheur.ha_recu_le)}.
      {:else}<span class="text-[var(--lave)]">Aucun envoi reçu depuis le démarrage.</span>{/if}
    </p>
  {:else}<p class="mt-1 text-sm text-muted-foreground">Lecture…</p>{/if}
  <p class="mt-2 text-sm text-muted-foreground">Home Assistant pousse l'état des machines (disques, NAS) avec le secret <code>ANNEAU_SECRET_HA</code>. Dans l'autre sens, l'Anneau n'appelle Home Assistant que pour réveiller le PC de calcul (webhook).</p>
</section>

<style>
  section:focus { outline: none; }
</style>
