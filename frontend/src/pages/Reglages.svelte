<script>
  // « Réglages » : le fichier des services, le seuil des disques, ce que Home Assistant a envoyé,
  // puis la version et la déconnexion.
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
