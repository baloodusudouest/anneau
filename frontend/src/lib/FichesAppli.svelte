<script>
  // 0.16 : les fiches « Connexion » d'une appli maison, dans sa fiche « État » (contrat 3, socle 0.11.0).
  // Lues une fois à l'ouverture (jamais en boucle) par /api/applis/<clé>/services : l'Anneau les demande à l'appli
  // avec ANNEAU_CLE, côté serveur. « Vérifier » est relayé ; aucun geste qui écrit (ils restent dans l'appli).
  // Même règle que dans les applis : de 1 à 3 services, fiches dépliées ; à partir de 4, tuiles puis la fiche.
  import { onMount, tick } from 'svelte'
  import { api } from '$lib/api.js'
  import FicheService from '$lib/services/FicheService.svelte'

  let { cle, nom } = $props()
  let r = $state(null)             // { etat, phrase, simule, services }
  let erreur = $state('')
  let ouvert = $state(null)
  let enCours = $state({})
  let messages = $state({})
  let annonces = $state({})
  let ficheOuverte = $state(null)

  const services = $derived(r?.services ?? [])
  const enTuiles = $derived(services.length > 3)
  const choisi = $derived(services.find((s) => s.id === ouvert) ?? null)
  const MOTS = { repond: 'Répond', ne_repond_pas: 'Ne répond pas', relie: 'Relié', pas_relie: 'Pas relié' }
  const voyant = (etat) =>
    etat === 'repond' ? 'bg-primary' : etat === 'ne_repond_pas' ? 'bg-destructive' : etat === 'relie' ? 'bg-muted-foreground' : 'border-2 border-muted-foreground'

  async function lire() {
    try { r = await api.get(`/api/applis/${encodeURIComponent(cle)}/services`); erreur = '' } catch (x) { erreur = x.message }
  }

  async function verifier(s) {
    enCours = { ...enCours, [s.id]: 'verifier' }
    messages = { ...messages, [s.id]: '' }
    annonces = { ...annonces, [s.id]: '' }
    try {
      const f = await api.post(`/api/applis/${encodeURIComponent(cle)}/services/${encodeURIComponent(s.id)}/verifier`)
      r = { ...r, services: r.services.map((x) => (x.id === f.id ? f : x)) }
      annonces = { ...annonces, [s.id]: `${f.nom} : ${(MOTS[f.etat] ?? f.etat).toLowerCase()}.` }
    } catch (x) {
      messages = { ...messages, [s.id]: x.message }
    }
    enCours = { ...enCours, [s.id]: '' }
  }

  async function basculer(id) {
    ouvert = ouvert === id ? null : id
    if (ouvert) {
      await tick()
      ficheOuverte?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      ficheOuverte?.focus({ preventScroll: true })
    }
  }

  onMount(lire)
</script>

<section class="fiches-appli" aria-label={'Connexion de ' + nom}>
  <h2 class="etiquette">Connexion</h2>
  {#if erreur}
    <p class="text-sm text-destructive" role="alert">{erreur}</p>
  {:else if !r}
    <p class="text-sm text-muted-foreground" role="status">Lecture des fiches de {nom}…</p>
  {:else if r.etat !== 'ok'}
    <p class="text-sm text-muted-foreground" role="status">{r.phrase}</p>
  {:else if !services.length}
    <p class="text-sm text-muted-foreground">{nom} ne dépend d'aucun service extérieur.</p>
  {:else if !enTuiles}
    <ul class="grid gap-3" aria-label={'Services de ' + nom}>
      {#each services as s (s.id)}
        <li><FicheService service={s} simule={r.simule} titreNiveau={3} enCours={enCours[s.id] || ''} message={messages[s.id] || ''}
                          annonce={annonces[s.id] || ''} onverifier={verifier} /></li>
      {/each}
    </ul>
  {:else}
    <ul class="grid grid-cols-2 gap-3" aria-label={'Services de ' + nom}>
      {#each services as s (s.id)}
        <li>
          <button type="button" aria-expanded={ouvert === s.id} onclick={() => basculer(s.id)}
                  class="flex min-h-20 w-full flex-col gap-1.5 rounded-2xl border bg-card p-4 text-left transition-colors hover:border-primary aria-expanded:border-primary">
            <span class="flex items-center gap-2">
              <span aria-hidden="true" class="size-2.5 shrink-0 rounded-full {voyant(s.etat)}"></span>
              <span class="font-medium leading-tight">{s.nom}</span>
            </span>
            <span class="text-sm {s.etat === 'ne_repond_pas' ? 'text-destructive' : 'text-muted-foreground'}">{MOTS[s.etat] ?? s.etat}</span>
          </button>
        </li>
      {/each}
    </ul>
    {#if choisi}
      <div class="mt-3 outline-none" tabindex="-1" bind:this={ficheOuverte}>
        <FicheService service={choisi} simule={r.simule} titreNiveau={3} enCours={enCours[choisi.id] || ''}
                      message={messages[choisi.id] || ''} annonce={annonces[choisi.id] || ''} onverifier={verifier} />
      </div>
    {/if}
  {/if}
  <p class="mt-2 text-xs text-muted-foreground">Synchroniser et les autres gestes qui écrivent se font dans {nom}.</p>
</section>

<style>
  .fiches-appli { width: 100%; max-width: 40rem; text-align: left; }
  .fiches-appli h2 { margin: 0 0 0.5rem; }
</style>
