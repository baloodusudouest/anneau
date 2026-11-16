<script>
  // « Réglages » : le fichier des services, Atlas, la sauvegarde (0.8), le seuil des disques,
  // ce que Home Assistant a envoyé, puis la version et la déconnexion.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import { Button } from '$lib/components/ui/button/index.js'

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
  // 0.5 : Atlas, la carte de la maison, relue chaque jour depuis sa publication GitHub
  let doc = $state(null)
  let msgAtlas = $state('')
  let attenteAtlas = $state(false)
  async function lireDocs() { try { doc = (await api.get('/api/documents')).atlas } catch (x) { msgAtlas = x.message } }
  onMount(lireDocs)
  async function relireAtlas() {
    attenteAtlas = true; msgAtlas = ''
    try { doc = (await api.post('/api/documents/atlas')).atlas; msgAtlas = doc.erreur ? '' : 'Atlas est à jour.' } catch (x) { msgAtlas = x.message }
    attenteAtlas = false
  }
  // 0.8 : sauvegarde des réglages des applis maison, clé publique de l'export chiffré, restauration de l'Anneau
  let sv = $state(null)
  let heure = $state('03:30')
  let msgSv = $state('')
  let attenteSv = $state(false)
  let cle = $state('')
  let cleSaisie = $state('')
  let exports = $state([])
  async function lireSv() {
    try {
      sv = await api.get('/api/sauvegardes')
      heure = sv.heure
      cle = (await api.get('/api/cle-publique')).cle_publique
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
  let msgCle = $state('')
  async function changerCle() {
    msgCle = ''
    const v = cleSaisie.trim()
    // une clé privée ne quitte jamais le navigateur : refusée ici, avant tout envoi
    if (/^AGE-SECRET-KEY-/i.test(v)) { msgCle = 'C\'est une clé privée : elle ne doit jamais être donnée à l\'Anneau. Garde-la hors de la maison.'; cleSaisie = ''; return }
    try { cle = (await api.put('/api/cle-publique', { cle_publique: v })).cle_publique; cleSaisie = ''; msgCle = cle ? 'Clé publique enregistrée.' : 'Clé publique retirée.' } catch (x) { msgCle = x.message }
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
      <p class="mt-2 text-sm text-muted-foreground">Importe le <code>services.yaml</code> téléchargé depuis Atlas (Fichiers) : il est vérifié, puis remplace l'actuel, gardé en secours. Il peut aussi se poser à la main dans le dossier de données, puis « Recharger ».</p>
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

    <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Atlas">
      <h2 class="text-lg font-semibold">Atlas</h2>
      {#if !doc}<p class="mt-1 text-sm text-muted-foreground">Lecture…</p>
      {:else if !doc.regle}
        <p class="mt-1 text-sm">Pas réglé : ajoute <code>ANNEAU_ATLAS_DEPOT</code> et <code>ANNEAU_GITHUB_JETON</code> dans la stack, puis redéploie.</p>
      {:else}
        <p class="mt-1 text-sm">
          {#if doc.present}La carte de la maison est là{doc.recu_le ? `, reçue il y a ${duree(doc.recu_le)}` : ''}. Ouvre-la par sa tuile, dans la famille Machines.
          {:else}Pas encore reçue.{/if}
          {#if doc.essaye_le} Dernier essai il y a {duree(doc.essaye_le)}.{/if}
        </p>
        {#if doc.note}<p class="mt-1 text-sm text-muted-foreground">{doc.note}</p>{/if}
        {#if doc.erreur}<p class="mt-1 text-sm text-destructive" role="alert">{doc.erreur}</p>{/if}
        <p class="mt-2 text-sm text-muted-foreground">Relue chaque jour depuis la publication « derniere » du dépôt d'Atlas ; un échec garde l'ancienne.</p>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="outline" onclick={relireAtlas} disabled={attenteAtlas}>{attenteAtlas ? 'Lecture…' : 'Relire Atlas maintenant'}</Button>
          {#if doc.present}<a class="text-sm underline underline-offset-4" href="/documents/atlas.html" target="_blank" rel="noopener">Ouvrir Atlas à côté</a>{/if}
          {#if msgAtlas}<span class="text-sm" role="status">{msgAtlas}</span>{/if}
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
            {#if Object.keys(sv.derniere.ratees).length}
              <ul class="mt-1 list-disc pl-5 text-sm" aria-label="Applis non lues">
                {#each Object.entries(sv.derniere.ratees) as [nom, raison]}<li class="break-words"><span class="text-[var(--app)]">{nom}</span> : {raison}</li>{/each}
              </ul>
            {/if}
          {/if}
        </div>
        {#if sv.fichiers.length}
          <h3 class="mt-4 text-sm font-semibold">Fichiers</h3>
          <ul class="mt-1 divide-y text-sm" aria-label="Fichiers de sauvegarde">
            {#each sv.fichiers as f (f.date)}
              <li class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-1.5">
                <span>{f.date} · {f.applis.length} appli(s){Object.keys(f.ratees).length ? ` · ${Object.keys(f.ratees).length} ratée(s)` : ''}</span>
                <a class="underline underline-offset-4" href={`/api/sauvegardes/${f.date}?telecharger=true`} download={`sauvegarde-${f.date}.json`}>Télécharger</a>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}

      <h3 class="mt-5 text-sm font-semibold">Export chiffré des variables</h3>
      <p class="mt-1 text-sm text-muted-foreground">Atlas chiffre le fichier des variables dans ton navigateur avec cette clé publique, puis l'envoie ici. L'Anneau ne garde que le fichier chiffré ; la clé privée reste hors de la maison.</p>
      <p class="mt-2 text-sm" aria-label="Clé publique">
        {#if cle}Clé publique : <code class="break-all">{cle}</code>{:else}Pas de clé publique : Atlas ne peut pas encore chiffrer.{/if}
      </p>
      <div class="mt-2 flex flex-wrap items-end gap-3">
        <label class="grid min-w-0 flex-1 basis-60 gap-1 text-sm" for="cle-publique">Nouvelle clé publique (age1…)
          <input id="cle-publique" type="text" autocomplete="off" spellcheck="false" bind:value={cleSaisie} placeholder="age1…" class="h-11 min-w-0 rounded-xl border bg-background px-3 text-base" />
        </label>
        <Button variant="outline" onclick={changerCle}>Enregistrer la clé</Button>
      </div>
      {#if msgCle}<p class="mt-2 text-sm" role="status" id="message-cle">{msgCle}</p>{/if}
      {#if exports.length}
        <ul class="mt-3 divide-y text-sm" aria-label="Exports chiffrés">
          {#each exports as x (x.nom)}
            <li class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-1.5"><span class="break-all">{x.nom} · {ko(x.taille)}</span>
              <a class="underline underline-offset-4" href={`/api/variables-chiffrees/${x.nom}`} download={x.nom}>Télécharger</a></li>
          {/each}
        </ul>
      {:else}
        <p class="mt-2 text-sm text-muted-foreground">Aucun export chiffré reçu.</p>
      {/if}
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
