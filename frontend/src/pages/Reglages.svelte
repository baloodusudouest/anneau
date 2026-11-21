<script>
  // « Réglages » : le fichier des services, la carte de la maison (0.11, ex-Atlas), la sauvegarde (0.8 ; listes et clés dans
  // les pages Sauvegardes et Variables depuis la 0.10), le seuil des disques,
  // ce que Home Assistant a envoyé, puis la version et la déconnexion.
  // 0.13 : section « Versions » (en service, dernière publiée, mise à jour le), sans couleur pour un retard.
  // 0.17 : section « Connexion » (fiches communes, contrat 3) : Portainer (ce que l'Anneau y lit et y écrit) et GitHub ;
  // 0.17.1 : et Watchtower (« Mettre à jour ») ;
  //    la dernière collecte dit les applis éteintes (« éteinte, pas sauvegardée cette nuit »).
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import FicheService from '$lib/services/FicheService.svelte'

  let { session, deconnecter, ondeconnecte } = $props()
  let e = $state(null)
  let message = $state('')
  let attente = $state(false)

  async function lire() { try { e = await api.get('/api/etat') } catch (x) { if (x.statut === 401) ondeconnecte?.(); else message = x.message } }
  onMount(lire)
  async function recharger() {
    attente = true; message = ''
    try {
      const r = await api.post('/api/recharger')
      await lire()
      message = `Fichier relu : ${r.services} service(s)` + (r.erreurs.length ? `, ${r.erreurs.length} ligne(s) écartée(s).` : '.')
    } catch (x) { message = x.message }
    attente = false
  }
  // 0.6 : importer services.yaml au lieu de le poser dans le dossier de données. Le fichier choisi est lu ici,
  // montré par son nom, et n'est envoyé qu'après « Remplacer » ; le serveur le vérifie avant d'écrire.
  let choisi = $state(null)
  let champ = $state(null)
  async function choisir(ev) {
    const f = ev.target.files?.[0]
    ev.target.value = ''
    if (!f) return
    message = ''
    if (f.size > 512 * 1024) { message = 'Ce fichier est trop gros pour être un fichier de services.'; return }
    choisi = { nom: f.name, texte: await f.text() }
  }
  async function importer() {
    attente = true; message = ''
    try {
      const r = await api.post('/api/services/importer', { texte: choisi.texte })
      await lire()
      message = `Fichier importé : ${r.services} service(s)` + (r.erreurs.length ? `, ${r.erreurs.length} ligne(s) écartée(s).` : '.')
        + (r.precedent ? ` L'ancien est gardé sous le nom ${r.precedent}.` : '')
      choisi = null
    } catch (x) { message = x.message }
    attente = false
  }
  // 0.15 : le Bac à sable (les applis maison sur une fausse maison). Adresse de sa tuile si elle existe, sinon
  // le même hôte que l'Anneau, port 8104, en http (le Bac à sable n'a pas de https).
  const tuileBac = $derived(e?.familles?.flatMap((f) => f.services).find((x) => x.cle === 'bac-a-sable') || null)
  const adresseBac = $derived(tuileBac?.adresse || `http://${location.hostname}:8104/`)
  // 0.11 : la carte de la maison (ex-Atlas), fabriquée par le coffre et relue toutes les heures
  let carte = $state(null)
  let msgCarte = $state('')
  let attenteCarte = $state(false)
  async function lireCarte() { try { carte = await api.get('/api/carte') } catch (x) { msgCarte = x.message } }
  onMount(lireCarte)
  async function relireCarte() {
    attenteCarte = true; msgCarte = ''
    try { carte = await api.post('/api/carte/relire'); msgCarte = carte.etat.erreur ? '' : 'Carte relue.' } catch (x) { msgCarte = x.message }
    attenteCarte = false
  }
  // 0.17 : fiches « Connexion » de l'Anneau lui-même (Portainer, GitHub) ; « Vérifier » ne teste que ce service
  let connexions = $state(null)
  let enCoursCx = $state({})
  let messagesCx = $state({})
  let annoncesCx = $state({})
  async function lireConnexions() { try { connexions = await api.get('/api/maison/services') } catch (x) { connexions = { services: [], erreur: x.message } } }
  onMount(lireConnexions)
  async function verifierCx(f) {
    enCoursCx = { ...enCoursCx, [f.id]: 'verifier' }; messagesCx = { ...messagesCx, [f.id]: '' }
    try {
      const n = await api.post(`/api/maison/services/${encodeURIComponent(f.id)}/verifier`)
      connexions = { ...connexions, services: connexions.services.map((x) => (x.id === n.id ? n : x)) }
      annoncesCx = { ...annoncesCx, [f.id]: `${n.nom} : ${n.etat === 'repond' ? 'répond' : n.etat === 'ne_repond_pas' ? 'ne répond pas' : n.etat}.` }
    } catch (x) { messagesCx = { ...messagesCx, [f.id]: x.message } }
    enCoursCx = { ...enCoursCx, [f.id]: '' }
  }
  // 0.13 : versions des tuiles (en service lue par la veille, dernière publiée lue chaque heure sur GitHub)
  let vers = $state(null)
  async function lireVersions() { try { vers = await api.get('/api/versions') } catch { vers = { tuiles: [] } } }
  onMount(lireVersions)
  // 0.8 : sauvegarde des réglages des applis maison, clé publique de l'export chiffré, restauration de l'Anneau
  let sv = $state(null)
  let heure = $state('03:30')
  let msgSv = $state('')
  let attenteSv = $state(false)
  let exports = $state([])
  async function lireSv() {
    try {
      sv = await api.get('/api/sauvegardes')
      heure = sv.heure
      exports = (await api.get('/api/variables-chiffrees')).exports
    } catch (x) { msgSv = x.message }
  }
  onMount(lireSv)
  async function changerHeure() {
    attenteSv = true; msgSv = ''
    try { heure = (await api.put('/api/reglages', { reglages: { heure_sauvegarde: heure } })).reglages.heure_sauvegarde; msgSv = `Collecte chaque jour à ${heure}.` } catch (x) { msgSv = x.message }
    attenteSv = false
  }
  async function sauvegarder() {
    attenteSv = true; msgSv = ''
    try {
      const d = (await api.post('/api/sauvegardes')).derniere
      await lireSv()
      await lireDates()
      const n = Object.keys(d.ratees).length
      msgSv = d.erreur ? `Fichier non écrit : ${d.erreur}` : `Sauvegarde faite : ${d.applis.length} appli(s) lue(s)` + (n ? `, ${n} ratée(s).` : '.')
    } catch (x) { msgSv = x.message }
    attenteSv = false
  }
  let dates = $state([])
  let choix = $state('')
  let diff = $state(null)
  let msgRest = $state('')
  async function lireDates() {
    msgRest = ''; diff = null
    try { dates = (await api.get('/api/restaurer')).dates; choix = dates[0] || '' } catch (x) { dates = []; msgRest = x.message }
  }
  onMount(lireDates)
  async function voir() {
    msgRest = ''
    try { diff = await api.get('/api/restaurer?le=' + encodeURIComponent(choix)) } catch (x) { msgRest = x.message }
  }
  async function restaurer() {
    try {
      const r = await api.post('/api/restaurer', { le: choix })
      heure = r.reglages.heure_sauvegarde; diff = null
      msgRest = r.restaures.length ? `Réglages du ${choix} restaurés.` : 'Rien à changer.'
    } catch (x) { msgRest = x.message }
  }
  const quand = (iso) => iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : ''
  const ko = (n) => n < 1024 ? `${n} o` : `${Math.round(n / 102.4) / 10} Ko`
  const nbServices = $derived((e?.familles || []).reduce((n, f) => n + f.services.length, 0))
  const virgule = (n) => String(n).replace('.', ',')
</script>

<main class="mx-auto max-w-3xl px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8">
  <header class="mb-5 flex items-end justify-between gap-3">
    <div><p class="etiquette">L'Anneau</p><h1 class="titre">Réglages</h1></div>
    <a class="text-sm underline underline-offset-4" href="#/">Revenir à l'anneau</a>
  </header>

  {#if !e}
    <p class="text-sm text-muted-foreground" role="status">{message || 'Lecture…'}</p>
  {:else}
    <section class="rounded-2xl border bg-card p-5" aria-label="Fichier des services">
      <h2 class="text-lg font-semibold">Fichier des services</h2>
      <p class="mt-1 text-sm">
        {#if e.fraicheur.exemple}Absent : l'Anneau montre un exemple inventé. Importe ton fichier <code>services.yaml</code> ci-dessous.
        {:else}{nbServices} service(s) dans {e.familles.length} famille(s). Modifié il y a {duree(e.fraicheur.fichier_modifie_le)}, relu il y a {duree(e.fraicheur.fichier_lu_le)}.{/if}
      </p>
      {#if e.fraicheur.erreurs.length}
        <ul class="mt-2 list-disc pl-5 text-sm" aria-label="Lignes écartées">{#each e.fraicheur.erreurs as l}<li>{l}</li>{/each}</ul>
      {/if}
      <p class="mt-2 text-sm text-muted-foreground">Importe le <code>services.yaml</code> exporté de la note <em>Tuiles de l'Anneau</em> du coffre : il est vérifié, puis remplace l'actuel, gardé en secours. Il peut aussi se poser à la main dans le dossier de données, puis « Recharger ». L'actuel se télécharge depuis <a class="underline underline-offset-4" href="#/variables">Variables</a>.</p>
      <input bind:this={champ} id="fichier-services" class="sr-only" type="file" accept=".yaml,.yml,text/yaml,text/plain" aria-label="Choisir un fichier services.yaml" onchange={choisir} />
      {#if choisi}
        <div class="mt-3 flex flex-wrap items-center gap-3 rounded-xl border p-3" role="group" aria-label="Import à confirmer">
          <span class="min-w-0 flex-1 basis-48 break-words text-sm">Remplacer le fichier des services par <strong>{choisi.nom}</strong> ?</span>
          <Button onclick={importer} disabled={attente}>{attente ? 'Import…' : 'Remplacer'}</Button>
          <Button variant="outline" onclick={() => (choisi = null)} disabled={attente}>Annuler</Button>
        </div>
      {:else}
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <Button onclick={() => champ?.click()} disabled={attente}>Importer un fichier</Button>
          <Button variant="outline" onclick={recharger} disabled={attente}>{attente ? 'Lecture…' : 'Recharger le fichier'}</Button>
        </div>
      {/if}
      {#if message}<p class="mt-3 text-sm" role="status" id="message">{message}</p>{/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Carte de la maison">
      <h2 class="text-lg font-semibold">Carte de la maison</h2>
      {#if !carte}<p class="mt-1 text-sm text-muted-foreground">Lecture…</p>
      {:else if !carte.etat.regle && !carte.carte}
        <p class="mt-1 text-sm">Pas réglée : ajoute <code>ANNEAU_ATLAS_DEPOT</code> et <code>ANNEAU_GITHUB_JETON</code> dans la stack, puis redéploie.</p>
      {:else}
        <p class="mt-1 text-sm">
          {#if carte.carte}Machines, services et flux de la maison, avec le voyant de chaque tuile : {carte.carte.services.length} services, {carte.carte.flux.length} flux{carte.carte.genere_le ? `, fabriquée par le coffre il y a ${duree(carte.carte.genere_le)}` : ''}.
          {:else}Pas encore reçue.{/if}
          {#if carte.etat.essaye_le} Relue il y a {duree(carte.etat.essaye_le)}.{/if}
        </p>
        {#if carte.etat.erreur}<p class="mt-1 text-sm text-destructive" role="alert">{carte.etat.erreur}</p>{/if}
        <p class="mt-2 text-sm text-muted-foreground">Fabriquée depuis le coffre Obsidian à chaque envoi, relue ici toutes les heures ; GitHub injoignable, la dernière carte reste.</p>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <Button href="#/carte">Ouvrir la carte</Button>
          <Button variant="outline" onclick={relireCarte} disabled={attenteCarte}>{attenteCarte ? 'Lecture…' : 'Relire la carte'}</Button>
          {#if msgCarte}<span class="text-sm" role="status">{msgCarte}</span>{/if}
        </div>
      {/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Connexion">
      <h2 class="text-lg font-semibold">Connexion</h2>
      <p class="mt-1 text-sm text-muted-foreground">Les services que l'Anneau joint lui-même : ce qu'il y lit et y écrit. Les applis maison ont leurs fiches dans leur fiche « État ».</p>
      {#if !connexions}<p class="mt-2 text-sm text-muted-foreground">Lecture…</p>
      {:else if connexions.erreur}<p class="mt-2 text-sm text-destructive" role="alert">{connexions.erreur}</p>
      {:else}
        <ul class="mt-3 grid gap-3" aria-label="Services de l'Anneau">
          {#each connexions.services as f (f.id)}
            <li><FicheService service={f} simule={connexions.simule} titreNiveau={3} enCours={enCoursCx[f.id] || ''} message={messagesCx[f.id] || ''}
                              annonce={annoncesCx[f.id] || ''} onverifier={verifierCx} /></li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Bac à sable">
      <h2 class="text-lg font-semibold">Bac à sable</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        Les applis maison lancées sur une fausse maison, avec des personnes inventées ou copiées de carnet, pour les
        essayer sans rien écrire chez les vrais services.
      </p>
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <Button href={adresseBac} target="_blank" rel="noopener">Ouvrir le bac à sable</Button>
        {#if !tuileBac}<span class="text-xs text-muted-foreground">Pas de tuile « Bac à sable » : adresse par défaut, port 8104.</span>{/if}
      </div>
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Versions">
      <h2 class="text-lg font-semibold">Versions</h2>
      <p class="mt-1 text-sm text-muted-foreground">Version en service (lue par la veille) et dernière publiée (étiquettes GitHub du dépôt <code>depot:</code> de la tuile, relues chaque heure){vers?.publiees_lues_le ? `, relues il y a ${duree(vers.publiees_lues_le)}` : ''}. Watchtower met à jour chaque nuit à 05:00.</p>
      {#if !vers}<p class="mt-2 text-sm text-muted-foreground">Lecture…</p>
      {:else if !vers.tuiles.length}
        <p class="mt-2 text-sm">Aucune version connue pour l'instant : ajoute <code>depot:</code> (ou <code>version_url:</code> pour une tuile tierce) dans le fichier des services.</p>
      {:else}
        <div class="mt-2 overflow-x-auto">
          <table class="versions w-full text-left text-sm">
            <thead><tr><th scope="col">Tuile</th><th scope="col">En service</th><th scope="col">Dernière publiée</th><th scope="col">Mise à jour le</th></tr></thead>
            <tbody>
              {#each vers.tuiles as t (t.cle)}
                <tr>
                  <th scope="row">{t.nom}</th>
                  <td>{t.version || '—'}</td>
                  <td>{t.publiee || '—'}{#if t.a_jour === false}<small>pas encore en service</small>{:else if t.a_jour}<small>à jour</small>{/if}</td>
                  <td>{t.mise_a_jour_le ? quand(t.mise_a_jour_le) : '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Sauvegarde" id="sauvegarde">
      <h2 class="text-lg font-semibold">Sauvegarde</h2>
      <p class="mt-1 text-sm text-muted-foreground">Chaque jour, l'Anneau demande leurs réglages aux applis maison du fichier des services et les range dans son dossier (emporté par Hyper Backup). Jamais de secret : une réponse qui en porte un est refusée.</p>
      <div class="mt-3 flex flex-wrap items-end gap-3">
        <label class="grid gap-1 text-sm" for="heure-sauvegarde">Heure de la collecte
          <input id="heure-sauvegarde" type="time" step="60" bind:value={heure} class="h-11 rounded-xl border bg-background px-3 text-base" />
        </label>
        <Button variant="outline" onclick={changerHeure} disabled={attenteSv}>Enregistrer l'heure</Button>
        <Button onclick={sauvegarder} disabled={attenteSv}>{attenteSv ? 'Collecte…' : 'Sauvegarder maintenant'}</Button>
      </div>
      {#if msgSv}<p class="mt-3 text-sm" role="status" id="message-sauvegarde">{msgSv}</p>{/if}
      {#if sv}
        <div class="mt-4" aria-label="Dernière collecte" role="group">
          <h3 class="text-sm font-semibold">Dernière collecte</h3>
          {#if !sv.derniere}<p class="mt-1 text-sm text-muted-foreground">Aucune pour l'instant.</p>
          {:else}
            <p class="mt-1 text-sm">{quand(sv.derniere.le)} ({sv.derniere.automatique ? 'automatique' : 'à la demande'}) : {sv.derniere.applis.length} appli(s) lue(s){sv.derniere.applis.length ? ' — ' + sv.derniere.applis.join(', ') : ''}.</p>
            {#if sv.derniere.erreur}<p class="mt-1 text-sm text-destructive" role="alert">Fichier non écrit : {sv.derniere.erreur}</p>{/if}
            {#if Object.keys(sv.derniere.eteintes || {}).length}
              <ul class="mt-1 list-disc pl-5 text-sm text-muted-foreground" aria-label="Applis éteintes">
                {#each Object.entries(sv.derniere.eteintes) as [nom, raison]}<li class="break-words">{nom} : {raison}</li>{/each}
              </ul>
            {/if}
            {#if Object.keys(sv.derniere.ratees).length}
              <ul class="mt-1 list-disc pl-5 text-sm" aria-label="Applis non lues">
                {#each Object.entries(sv.derniere.ratees) as [nom, raison]}<li class="break-words"><span class="text-[var(--app)]">{nom}</span> : {raison}</li>{/each}
              </ul>
            {/if}
          {/if}
        </div>
        <p class="mt-3 text-sm">{sv.fichiers.length} sauvegarde(s) gardée(s). <a class="underline underline-offset-4" href="#/sauvegardes">Voir les sauvegardes</a> : réglages de chaque appli et ce qui a changé.</p>
      {/if}

      <h3 class="mt-5 text-sm font-semibold">Export chiffré des variables</h3>
      <p class="mt-1 text-sm">{exports.length ? `${exports.length} export(s) chiffré(s) rangé(s).` : 'Aucun export chiffré rangé.'} Clé, chiffrement, ouverture et copie pour Portainer : <a class="underline underline-offset-4" href="#/variables">Variables</a>.</p>
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Restaurer">
      <h2 class="text-lg font-semibold">Restaurer les réglages</h2>
      <p class="mt-1 text-sm text-muted-foreground">Les réglages de l'Anneau lui-même (l'heure de la collecte), depuis une sauvegarde. Chaque appli maison a son propre bouton dans ses Réglages.</p>
      {#if dates.length}
        <div class="mt-3 flex flex-wrap items-end gap-3">
          <label class="grid gap-1 text-sm" for="date-restaurer">Sauvegarde du
            <select id="date-restaurer" bind:value={choix} class="h-11 rounded-xl border bg-background px-3 text-base">
              {#each dates as d}<option value={d}>{d}</option>{/each}
            </select>
          </label>
          <Button variant="outline" onclick={voir}>Voir les différences</Button>
        </div>
        {#if diff}
          {#if diff.differences.length}
            <ul class="mt-3 divide-y text-sm" aria-label="Différences">
              {#each diff.differences as d}<li class="flex flex-wrap justify-between gap-x-4 py-1.5"><code>{d.cle}</code><span>{d.actuel} → {d.sauve}</span></li>{/each}
            </ul>
            <Button class="mt-3" onclick={restaurer}>Restaurer</Button>
          {:else}
            <p class="mt-3 text-sm">Aucune différence avec les réglages actuels.</p>
          {/if}
        {/if}
      {:else}
        <Button class="mt-3" variant="outline" onclick={lireDates}>Chercher les sauvegardes</Button>
      {/if}
      {#if msgRest}<p class="mt-3 text-sm" role="status" id="message-restaurer">{msgRest}</p>{/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Disques">
      <h2 class="text-lg font-semibold">Disques</h2>
      <p class="mt-1 text-sm">Un volume est « en panne » à partir de {virgule(e.fraicheur.seuil_disque)} % d'occupation (réglage <code>seuil_disque</code> du fichier).</p>
      {#if e.volumes.length}
        <ul class="mt-2 divide-y text-sm" aria-label="Volumes">
          {#each e.volumes as v}
            <li class="flex flex-wrap justify-between gap-x-4 py-1.5"><span>{v.nom}{v.machine ? ' · ' + v.machine : ''}</span>
              <span class="text-muted-foreground">{v.pourcentage == null ? 'inconnu' : virgule(v.pourcentage) + ' %'}{v.etat ? ' · ' + v.etat : ''}</span></li>
          {/each}
        </ul>
      {:else}
        <p class="mt-2 text-sm text-muted-foreground">{e.fraicheur.ha_attendu ? 'Home Assistant n\'a encore rien envoyé.' : 'Home Assistant n\'est pas encore branché : aucun volume n\'est surveillé.'}</p>
      {/if}
    </section>

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Home Assistant">
      <h2 class="text-lg font-semibold">Home Assistant</h2>
      <p class="mt-1 text-sm">
        {#if !e.fraicheur.ha_attendu}Pas encore branché. L'Anneau attend que Home Assistant lui envoie l'état des machines ; il ne détient aucun jeton de Home Assistant.
        {:else if e.fraicheur.ha_recu_le}Dernier envoi reçu il y a {duree(e.fraicheur.ha_recu_le)}.
        {:else}Aucun envoi reçu depuis le démarrage.{/if}
      </p>
    </section>

    {#if e.closes.length}
      <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Dernières pannes closes">
        <h2 class="text-lg font-semibold">Dernières pannes closes</h2>
        <ul class="mt-2 divide-y text-sm">
          {#each e.closes as p}<li class="flex flex-wrap justify-between gap-x-4 py-1.5"><span>{p.phrase}</span><span class="text-muted-foreground">close il y a {duree(p.close_le)}</span></li>{/each}
        </ul>
      </section>
    {/if}
  {/if}

  <p class="mt-6 flex items-center justify-between gap-3 text-sm text-muted-foreground">
    <span>L'Anneau {session.version}</span>
    <Button variant="outline" onclick={deconnecter}>Se déconnecter</Button>
  </p>
</main>

<style>
  .versions th, .versions td { padding: 0.45rem 0.5rem 0.45rem 0; border-top: 1px solid var(--border); vertical-align: top; white-space: nowrap; }
  .versions thead th { border-top: 0; font-size: 0.74rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted-foreground); }
  .versions tbody th { font-weight: 600; white-space: normal; }
  .versions small { display: block; color: var(--muted-foreground); font-size: 0.78rem; }
</style>
