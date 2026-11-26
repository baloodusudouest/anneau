<script>
  // 0.19 — Réglages › Stack et variables (ancienne page Variables, 0.10). Le téléchargement de services.yaml est passé
  // dans Réglages › Services. Depuis la 0.19, le serveur refuse lui aussi d'écrire la clé publique ou un export en http
  // (403) ; lire et télécharger un export chiffré restent permis. La ligne « Vu par l'Anneau » dit par quel signal le
  // serveur sait que la page est sûre (étape zéro du conseil).
  // 0.10 : les variables de la stack et leur export chiffré, en un seul endroit (avant : Atlas › Fichiers).
  //  - la stack : homelab.yml importé dans l'Anneau (variables attendues), téléchargements de homelab.yml et services.yaml ;
  //  - la clé : paire age générée ici (la clé privée est montrée une fois, jamais gardée ni envoyée), clé publique et empreinte ;
  //  - chiffrer l'export de Portainer et le ranger ; ouvrir un export avec la clé privée ;
  //  - la liste des variables, avec les valeurs ouvertes (masquées), et la copie pour Portainer.
  // Règle (décision du 17/11/2026) : chiffrer et ouvrir seulement en contexte sûr (HTTPS). Le serveur ne reçoit
  // jamais que la clé publique et du texte déjà chiffré. Les valeurs ne vivent que dans cette page.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import { chiffrer, dechiffrer, genererPaire, publiqueDe, clePriveeValide, sur, empreinte } from '$lib/chiffre.js'
  import { comprendre, sensible, pourPortainer, lienNote } from '$lib/environnement.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { ondeconnecte } = $props()
  const securise = sur()
  let message = $state('')
  const dire = (t) => (message = t)
  const echec = (x) => { if (x?.statut === 401) ondeconnecte?.(); else dire(x?.message || String(x)) }

  // ---------------------------------------------------------------- la stack
  let pile = $state({ present: false, variables: [], services: [], coffre: 'Maison', adresse_https: '' })
  let coffre = $state('Maison')
  let champStack = $state(null)
  async function lireStack() { try { pile = await api.get('/api/stack'); coffre = pile.coffre } catch (x) { echec(x) } }
  async function importerStack(ev) {
    const f = ev.target.files?.[0]
    ev.target.value = ''
    if (!f) return
    if (f.size > 512 * 1024) { dire('Ce fichier est trop gros pour être homelab.yml.'); return }
    try { pile = await api.post('/api/stack', { texte: await f.text() }); dire(`homelab.yml importé : ${pile.services.length} service(s), ${pile.variables.length} variable(s).`) }
    catch (x) { echec(x) }
  }
  async function changerCoffre() {
    try { coffre = (await api.put('/api/reglages', { reglages: { coffre_obsidian: coffre } })).reglages.coffre_obsidian; dire(`Liens vers le coffre « ${coffre} ».`) } catch (x) { echec(x) }
  }

  // ---------------------------------------------------------------- la clé
  let cle = $state('')
  let cleSaisie = $state('')
  let paire = $state(null)            // { privee, publique } : la privée n'existe que dans cette variable
  let rangee = $state(false)
  let remplacer = $state(false)       // 0.11.2 (audit M7) : remplacer une clé déjà posée se confirme
  async function lireCle() { try { cle = (await api.get('/api/cle-publique')).cle_publique } catch (x) { echec(x) } }
  async function poserCle(v) {
    v = (v || '').trim()
    if (/^AGE-SECRET-KEY-/i.test(v)) { cleSaisie = ''; dire('C\'est une clé privée : elle ne doit jamais être donnée à l\'Anneau. Garde-la hors de la maison.'); return false }
    if (cle && v !== cle && !remplacer) { dire(`Une clé est déjà posée (empreinte ${empreinte(cle)}). Coche « Remplacer la clé actuelle » : les exports déjà rangés resteront lisibles seulement avec l'ancienne clé privée.`); return false }
    const corps = cle && v !== cle ? { cle_publique: v, actuelle: cle } : { cle_publique: v }
    try { cle = (await api.put('/api/cle-publique', corps)).cle_publique; remplacer = false; return true } catch (x) { echec(x); return false }
  }
  async function enregistrerSaisie() { if (await poserCle(cleSaisie)) { cleSaisie = ''; dire(cle ? 'Clé publique enregistrée.' : 'Clé publique retirée.') } }
  async function generer() { rangee = false; paire = await genererPaire(); dire('') }
  async function copier(texte, quoi) {
    try { await navigator.clipboard.writeText(texte); dire(`${quoi} copié${quoi.endsWith('e') ? 'e' : ''}.`) }
    catch { dire('Copie impossible ici : sélectionne le texte et copie-le à la main.') }
  }
  async function adopterPaire() {
    if (!rangee) { dire('Range d\'abord la clé privée dans le gestionnaire de mots de passe, puis coche la case.'); return }
    if (await poserCle(paire.publique)) { paire = null; rangee = false; dire('Nouvelle clé publique enregistrée. La clé privée a été effacée de la page.') }
  }

  // ---------------------------------------------------------------- chiffrer l'export de Portainer
  let colle = $state('')
  let champEnv = $state(null)
  async function choisirEnv(ev) {
    const f = ev.target.files?.[0]
    ev.target.value = ''
    if (f) colle = await f.text()
  }
  async function chiffrerEtRanger() {
    if (!securise) return
    const { valeurs } = comprendre(colle)
    if (!Object.keys(valeurs).length) { dire('Aucune ligne « NOM=valeur » dans ce texte : rien n\'a été chiffré.'); return }
    if (!cle) { dire('Pas encore de clé publique : génère une paire ou pose ta clé publique plus haut.'); return }
    try {
      const r = await api.postTexte('/api/variables-chiffrees', await chiffrer(colle, cle))
      colle = ''
      if (r.nom) choisi = r.nom                      // le nouvel export devient celui qu'« Ouvrir » visera
      await lireExports()
      dire(`Export chiffré et rangé : ${r.nom || 'fichier'} (${Object.keys(valeurs).length} variables). Le texte clair a été effacé de la page.`)
    } catch (x) { echec(x) }
  }
  function comparerSansRanger() {
    const { valeurs: v, ecartees } = comprendre(colle)
    if (!Object.keys(v).length) { dire('Aucune ligne « NOM=valeur » dans ce texte.'); return }
    ouvertes = { valeurs: v, source: 'texte collé (non rangé)' }; colle = ''; visibles = {}
    dire(`${Object.keys(v).length} valeur(s) lue(s) dans la page seulement` + (ecartees ? `, ${ecartees} ligne(s) non comprise(s).` : '.'))
  }

  // ---------------------------------------------------------------- exports chiffrés et ouverture
  let exports = $state([])
  let choisi = $state('')
  let privee = $state('')
  let ouvertes = $state(null)          // { valeurs, source } : seulement dans la mémoire de la page
  let visibles = $state({})
  async function lireExports() { try { exports = (await api.get('/api/variables-chiffrees')).exports; choisi = choisi || exports[0]?.nom || '' } catch (x) { echec(x) } }
  async function ouvrir() {
    if (!securise || !choisi) return
    if (!clePriveeValide(privee)) { dire('Clé privée mal formée : elle commence par AGE-SECRET-KEY-1 et fait 74 caractères.'); return }
    try {
      const r = await fetch('/api/variables-chiffrees/' + encodeURIComponent(choisi), { credentials: 'same-origin' })
      if (r.status === 401) { ondeconnecte?.(); return }
      if (!r.ok) throw new Error(`L'Anneau a répondu ${r.status}.`)
      const texte = await dechiffrer(new Uint8Array(await r.arrayBuffer()), privee)
      const { valeurs: v } = comprendre(texte)
      const proprio = cle && (await publiqueDe(privee)) !== cle
      ouvertes = { valeurs: v, source: choisi }; visibles = {}
      dire(`${choisi} ouvert : ${Object.keys(v).length} variable(s), dans cette page seulement.` + (proprio ? ' Attention : cette clé privée ne va pas avec la clé publique actuelle.' : ''))
    } catch (x) { dire(x.message || String(x)) }
    privee = ''
  }
  function oublier() { ouvertes = null; visibles = {}; privee = ''; colle = ''; voirTexte = false; dire('Valeurs oubliées : la page ne garde plus rien.') }

  // ---------------------------------------------------------------- la liste des variables
  let depliee = $state(false)
  let cherche = $state('')
  let voirTexte = $state(false)
  const plat = (t) => (t || '').toLowerCase().normalize('NFD').replace(/\p{Mn}/gu, '')
  const montree = $derived(depliee || !!cherche.trim())
  const liste = $derived(pile.variables.filter((v) => !cherche.trim() || plat(v.nom + ' ' + v.services.join(' ')).includes(plat(cherche.trim()))))
  const valeurs = $derived(ouvertes?.valeurs || null)
  const a = (nom) => valeurs && Object.prototype.hasOwnProperty.call(valeurs, nom)
  const connues = $derived(new Set(pile.variables.map((v) => v.nom)))
  const manquantes = $derived(valeurs ? pile.variables.filter((v) => v.defaut === null && !(a(v.nom) && valeurs[v.nom] !== '')) : [])
  const inconnues = $derived(valeurs && pile.present ? Object.keys(valeurs).filter((n) => !connues.has(n)).sort() : [])
  const portainer = $derived(valeurs ? pourPortainer(valeurs, pile.present ? pile.variables : null) : { texte: '', n: 0, vides: 0 })
  function telechargerEnv() {
    const url = URL.createObjectURL(new Blob([portainer.texte], { type: 'text/plain;charset=utf-8' }))
    const l = Object.assign(document.createElement('a'), { href: url, download: 'homelab.env' })
    document.body.appendChild(l); l.click(); l.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  }

  // 0.19 : ce que voit le serveur (https, par quel signal, garde coupée ou non)
  let vu = $state(null)
  async function lireHttps() { try { vu = await api.get('/api/https') } catch { vu = null } }
  const PAR = { direct: 'servie en https', relais: 'https par le relais Tailscale Serve', origine: 'https d\'après le navigateur', machine: 'ouverte sur la machine même' }

  onMount(() => { lireStack(); lireCle(); lireExports(); lireHttps() })
  const ko = (n) => n < 1024 ? `${n} o` : `${Math.round(n / 102.4) / 10} Ko`
  const ancien = $derived(exports[0] ? (Date.now() - new Date(exports[0].nom.slice(0, 10) + 'T12:00:00').getTime()) / 86400000 > 30 : false)
</script>

<div class="stack">

  {#if message}<p class="sticky top-2 z-10 mb-3 break-words rounded-xl border border-[var(--app)] bg-card px-4 py-2 text-sm" role="status" id="message-variables">{message}</p>{/if}

  {#if !securise}
    <p class="mb-3 rounded-2xl border border-[var(--lave)]/60 bg-card p-4 text-sm" role="alert" aria-label="Page non sûre">
      L'Anneau est ouvert en <strong>http</strong> : chiffrer et ouvrir un export sont désactivés, car une page servie en clair sur le réseau
      peut être modifiée en route et lire ce qu'on y colle.
      {#if pile.adresse_https}
        <!-- 0.10.1 : adresse tirée des tuiles https (Tailscale Serve) ; Tailscale doit être allumé sur l'appareil -->
        <a class="font-semibold underline" href="{pile.adresse_https}/#/reglages/stack" id="lien-https">Ouvrir cette page en https</a>
        (<code class="break-all">{pile.adresse_https}</code>, Tailscale allumé sur cet appareil),
      {:else}
        Ouvre l'Anneau par son adresse <strong>https</strong> (Tailscale, port 9094),
      {/if}
      ou déchiffre sur le PC avec <code>age -d -i cle.txt export.age</code> (fiche « L'Anneau ne démarre plus » du coffre).
    </p>
  {/if}

  {#if vu}
    <p class="mb-3 text-xs text-muted-foreground" id="vu-par-l-anneau">Vu par l'Anneau : page {vu.https ? PAR[vu.par] : 'en http'}{vu.garde ? '' : ' · garde https coupée (ANNEAU_GARDE_HTTPS=non)'}.</p>
  {/if}

  <!-- ===================================================== la stack -->
  <section class="rounded-2xl border bg-card p-5" aria-label="Fichiers de la stack" id="section-fichiers" tabindex="-1">
    <h2 class="text-lg font-semibold">Fichiers de la stack</h2>
    <p class="mt-1 text-sm">
      {#if pile.present}<code>homelab.yml</code> importé il y a {duree(pile.le)} : {pile.services.length} service(s), {pile.variables.length} variable(s).
      {:else}<code>homelab.yml</code> n'est pas encore importé : sans lui, la liste des variables attendues est vide.{/if}
    </p>
    <p class="mt-1 text-sm text-muted-foreground">Le coffre fait foi : exporte le bloc YAML de la note <em>homelab.yml</em> en fichier (sans les ```), puis importe-le ici. Il ne doit contenir que des références <code>${'{'}…{'}'}</code> : une valeur en clair fait tout refuser.</p>
    <input bind:this={champStack} class="sr-only" type="file" accept=".yml,.yaml,text/yaml,text/plain" aria-label="Choisir homelab.yml" onchange={importerStack} />
    <div class="mt-3 flex flex-wrap items-center gap-3">
      <Button onclick={() => champStack?.click()}>Importer homelab.yml</Button>
      {#if pile.present}<a class="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/api/stack/fichier" download="homelab.yml">Télécharger homelab.yml</a>{/if}
    </div>
  </section>

  <!-- ===================================================== la clé -->
  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Clé de chiffrement" id="section-cle" tabindex="-1">
    <h2 class="text-lg font-semibold">Clé de chiffrement</h2>
    <p class="mt-1 text-sm" aria-label="Clé publique">
      {#if cle}Clé publique : <code class="break-all">{cle}</code><br /><span class="text-muted-foreground">Empreinte à comparer avec la copie du coffre : <strong class="text-foreground">{empreinte(cle)}</strong></span>
      {:else}Pas encore de clé publique : rien ne peut être chiffré.{/if}
    </p>
    {#if cle}
      <label class="mt-2 inline-flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" bind:checked={remplacer} class="size-4 accent-[var(--app)]" /> Remplacer la clé actuelle (les exports déjà rangés resteront lisibles seulement avec l'ancienne clé privée)</label>
    {/if}
    {#if paire}
      <div class="mt-3 grid gap-2 rounded-xl border border-[var(--app)] p-3" role="group" aria-label="Nouvelle paire">
        <p class="text-sm"><strong>Clé privée, montrée une seule fois.</strong> Range-la dans le gestionnaire de mots de passe, hors du NAS. L'Anneau ne la garde pas : sans elle, les exports sont illisibles.</p>
        <label class="sr-only" for="cle-privee-neuve">Clé privée neuve</label>
        <textarea id="cle-privee-neuve" readonly rows="2" spellcheck="false" class="min-w-0 rounded-xl border bg-background p-2 font-mono text-sm break-all" value={paire.privee} onfocus={(ev) => ev.currentTarget.select()}></textarea>
        <div class="flex flex-wrap items-center gap-3">
          <Button variant="outline" onclick={() => copier(paire.privee, 'Clé privée')}>Copier la clé privée</Button>
          <label class="inline-flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" bind:checked={rangee} class="size-4 accent-[var(--app)]" /> Je l'ai rangée hors de la maison</label>
        </div>
        <p class="text-sm text-muted-foreground">Clé publique qui va avec : <code class="break-all">{paire.publique}</code> (empreinte {empreinte(paire.publique)})</p>
        <div class="flex flex-wrap gap-3">
          <Button onclick={adopterPaire}>Utiliser cette paire</Button>
          <Button variant="outline" onclick={() => { paire = null; rangee = false }}>Abandonner</Button>
        </div>
      </div>
    {:else}
      <div class="mt-3 flex flex-wrap items-end gap-3">
        <Button variant="outline" onclick={generer} disabled={!securise}>Générer une paire de clés</Button>
        <label class="grid min-w-0 flex-1 basis-60 gap-1 text-sm" for="cle-publique">Ou poser une clé publique (age1…)
          <input id="cle-publique" type="text" autocomplete="off" spellcheck="false" bind:value={cleSaisie} placeholder="age1…" class="h-11 min-w-0 rounded-xl border bg-background px-3 text-base" />
        </label>
        <Button variant="outline" onclick={enregistrerSaisie} disabled={!securise}>Enregistrer la clé</Button>
      </div>
    {/if}
  </section>

  <!-- ===================================================== chiffrer -->
  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Chiffrer l'export de Portainer" id="section-chiffrer" tabindex="-1">
    <h2 class="text-lg font-semibold">Chiffrer l'export de Portainer</h2>
    <p class="mt-1 text-sm text-muted-foreground">Dans Portainer › Stacks › homelab › Editor › Environment variables › <em>Advanced mode</em> : tout copier, coller ici. Le texte est chiffré dans la page avec la clé publique ; seul le texte chiffré part vers l'Anneau. À refaire après chaque changement de variable.</p>
    {#if ancien}<p class="mt-2 text-sm text-[var(--app)]">Le dernier export a plus de 30 jours.</p>{/if}
    <label class="sr-only" for="texte-portainer">Export de Portainer à chiffrer</label>
    <textarea id="texte-portainer" bind:value={colle} rows="5" spellcheck="false" autocomplete="off" disabled={!securise}
      placeholder={securise ? 'NOM=valeur, une par ligne' : 'Désactivé en http'} class="mt-3 w-full min-w-0 rounded-xl border bg-background p-3 font-mono text-sm"></textarea>
    <input bind:this={champEnv} class="sr-only" type="file" accept=".env,text/plain" aria-label="Choisir un fichier d'environnement" onchange={choisirEnv} />
    <div class="mt-2 flex flex-wrap gap-3">
      <Button onclick={chiffrerEtRanger} disabled={!securise || !colle.trim()}>Chiffrer et ranger</Button>
      <Button variant="outline" onclick={() => champEnv?.click()} disabled={!securise}>Choisir un fichier</Button>
      <Button variant="outline" onclick={comparerSansRanger} disabled={!securise || !colle.trim()}>Comparer avec la stack sans ranger</Button>
    </div>
  </section>

  <!-- ===================================================== exports -->
  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Exports chiffrés" id="section-exports" tabindex="-1">
    <h2 class="text-lg font-semibold">Exports chiffrés</h2>
    {#if exports.length}
      <ul class="mt-2 divide-y text-sm" aria-label="Liste des exports">
        {#each exports as x (x.nom)}
          <li class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-1.5">
            <label class="inline-flex min-h-10 min-w-0 items-center gap-2 break-all"><input type="radio" name="export" value={x.nom} bind:group={choisi} class="accent-[var(--app)]" /> {x.nom} · {ko(x.taille)}</label>
            <a class="underline underline-offset-4" href={`/api/variables-chiffrees/${x.nom}`} download={x.nom}>Télécharger</a>
          </li>
        {/each}
      </ul>
      <div class="mt-3 flex flex-wrap items-end gap-3">
        <label class="grid min-w-0 flex-1 basis-60 gap-1 text-sm" for="cle-privee">Clé privée (jamais gardée ni envoyée)
          <input id="cle-privee" type="password" autocomplete="off" spellcheck="false" bind:value={privee} disabled={!securise} placeholder="AGE-SECRET-KEY-1…" class="h-11 min-w-0 rounded-xl border bg-background px-3 font-mono text-base" />
        </label>
        <Button onclick={ouvrir} disabled={!securise || !choisi || !privee}>Ouvrir</Button>
      </div>
    {:else}
      <p class="mt-1 text-sm text-muted-foreground">Aucun export chiffré rangé.</p>
    {/if}
  </section>

  <!-- ===================================================== variables -->
  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Variables de la stack" id="section-variables" tabindex="-1">
    <h2 class="text-lg font-semibold">Variables de la stack</h2>
    {#if valeurs}
      <div class="mt-2 grid gap-2 rounded-xl border p-3 text-sm" role="group" aria-label="Valeurs ouvertes">
        <p>Valeurs ouvertes depuis <strong class="break-all">{ouvertes.source}</strong>, dans cette page seulement.
          {#if pile.present}{manquantes.length ? `${manquantes.length} variable(s) à remplir absente(s) ou vide(s).` : 'Toutes les variables à remplir ont une valeur.'}{/if}</p>
        {#if manquantes.length}<p class="break-words text-[var(--app)]">À remplir : {manquantes.map((v) => v.nom).join(', ')}</p>{/if}
        {#if inconnues.length}<p class="break-words text-muted-foreground">Que la stack n'utilise plus (laissées de côté dans la copie) : {inconnues.join(', ')}</p>{/if}
        <div class="flex flex-wrap gap-3">
          <Button onclick={() => copier(portainer.texte, 'Texte pour Portainer')}>Copier toutes les variables (avec valeurs)</Button>
          <Button variant="outline" onclick={telechargerEnv}>Télécharger homelab.env</Button>
          <Button variant="outline" aria-expanded={voirTexte} onclick={() => (voirTexte = !voirTexte)}>{voirTexte ? 'Masquer le texte' : 'Voir le texte'}</Button>
          <Button variant="outline" onclick={oublier}>Oublier les valeurs</Button>
        </div>
        <p class="text-muted-foreground">{portainer.n} ligne(s) pour Portainer › <em>Advanced mode</em> (tout remplacer). Les facultatives absentes ne sont pas écrites : leur défaut est gardé.</p>
        {#if voirTexte}
          <p class="text-[var(--app)]">Attention : mots de passe et jetons en clair dans cette zone.</p>
          <label class="sr-only" for="texte-recoller">Texte à recoller dans Portainer</label>
          <textarea id="texte-recoller" readonly rows="8" spellcheck="false" value={portainer.texte} onfocus={(ev) => ev.currentTarget.select()} class="w-full min-w-0 rounded-xl border bg-background p-3 font-mono text-sm"></textarea>
        {/if}
      </div>
    {/if}
    <div class="mt-3 flex flex-wrap items-center gap-3">
      <Button variant="outline" aria-expanded={depliee} aria-controls="liste-variables" onclick={() => (depliee = !depliee)}>{depliee ? 'Plier la liste' : `Déplier la liste (${pile.variables.length})`}</Button>
      <label class="sr-only" for="cherche-variable">Chercher une variable</label>
      <input id="cherche-variable" type="search" bind:value={cherche} placeholder="Chercher : variable ou service" class="h-11 min-w-0 flex-1 basis-48 rounded-xl border bg-background px-3 text-base" />
    </div>
    {#if !pile.present}<p class="mt-2 text-sm text-muted-foreground">Importe homelab.yml plus haut pour voir la liste.</p>
    {:else if !montree}<p class="mt-2 text-sm text-muted-foreground">Liste pliée : déplie-la, ou cherche une variable.</p>{/if}
    <ul id="liste-variables" class="mt-2 divide-y text-sm" aria-label="Liste des variables" hidden={!montree}>
      {#each liste as v (v.nom)}
        <li class="grid gap-1 py-2">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <code class="break-all font-medium">{v.nom}</code>
            {#if v.defaut === null}<span class="text-xs text-[var(--app)]">à remplir</span>{:else}<span class="text-xs text-muted-foreground">facultative{v.defaut ? ` (défaut : ${v.defaut})` : ''}</span>{/if}
            <a class="text-xs underline underline-offset-4" href={lienNote(coffre, v.nom)}>Note dans Obsidian</a>
          </div>
          <p class="break-words text-muted-foreground">{v.services.join(', ')}</p>
          {#if valeurs}
            <p class="break-all">
              {#if !a(v.nom)}<span class="text-muted-foreground">absente</span>
              {:else if sensible(v.nom) && !visibles[v.nom]}<span class="text-muted-foreground">••••••</span> <button type="button" class="underline underline-offset-4" aria-label={'Afficher la valeur de ' + v.nom} onclick={() => (visibles[v.nom] = true)}>Afficher</button>
              {:else}<span class="select-all">{valeurs[v.nom] || '(vide)'}</span>{#if sensible(v.nom)} <button type="button" class="underline underline-offset-4" aria-label={'Masquer la valeur de ' + v.nom} onclick={() => (visibles[v.nom] = false)}>Masquer</button>{/if}{/if}
            </p>
          {/if}
        </li>
      {:else}
        {#if pile.present}<li class="py-2 text-muted-foreground">Aucune variable ne correspond.</li>{/if}
      {/each}
    </ul>
    <div class="mt-4 flex flex-wrap items-end gap-3">
      <label class="grid gap-1 text-sm" for="nom-coffre">Nom du coffre Obsidian (liens des notes)
        <input id="nom-coffre" type="text" bind:value={coffre} class="h-11 rounded-xl border bg-background px-3 text-base" />
      </label>
      <Button variant="outline" onclick={changerCoffre}>Enregistrer le nom</Button>
    </div>
  </section>
</div>

<style>
  section:focus { outline: none; }
</style>
