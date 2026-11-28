<script>
  // 0.22 : section « Applis en veille » (Veille.svelte), juste après le fichier des services.
  // 0.19 — Réglages › Services : le fichier des services (importer, relire, télécharger : tout ici), les versions des
  // tuiles, le bac à sable. Repris de l'ancienne page Réglages (0.6, 0.13, 0.15) ; le téléchargement de services.yaml
  // vient de l'ancienne page Variables.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import Veille from '$lib/reglages/Veille.svelte'

  let { ondeconnecte } = $props()
  let e = $state(null)
  let message = $state('')
  let attente = $state(false)
  const echec = (x) => { if (x?.statut === 401) ondeconnecte?.(); else message = x?.message || String(x) }

  async function lire() { try { e = await api.get('/api/etat') } catch (x) { echec(x) } }
  async function recharger() {
    attente = true; message = ''
    try {
      const r = await api.post('/api/recharger')
      await lire()
      message = `Fichier relu : ${r.services} service(s)` + (r.erreurs.length ? `, ${r.erreurs.length} ligne(s) écartée(s).` : '.')
    } catch (x) { echec(x) }
    attente = false
  }
  // 0.6 : le fichier choisi est lu ici, montré par son nom, et n'est envoyé qu'après « Remplacer » ; le serveur le
  // vérifie avant d'écrire et garde l'ancien en secours.
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
    } catch (x) { echec(x) }
    attente = false
  }
  // 0.13 : versions des tuiles (en service lue par la veille, dernière publiée lue chaque heure sur GitHub)
  let vers = $state(null)
  async function lireVersions() { try { vers = await api.get('/api/versions') } catch { vers = { tuiles: [] } } }
  // 0.15 : le Bac à sable (les applis maison sur une fausse maison). Adresse de sa tuile si elle existe, sinon le même
  // hôte que l'Anneau, port 8104, en http (le Bac à sable n'a pas de https).
  const tuileBac = $derived(e?.familles?.flatMap((f) => f.services).find((x) => x.cle === 'bac-a-sable') || null)
  const adresseBac = $derived(tuileBac?.adresse || `http://${location.hostname}:8104/`)

  onMount(() => { lire(); lireVersions() })
  const quand = (iso) => iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : ''
  const nbServices = $derived((e?.familles || []).reduce((n, f) => n + f.services.length, 0))
</script>

{#if !e}
  <p class="text-sm text-muted-foreground" role="status">{message || 'Lecture…'}</p>
{:else}
  <section class="rounded-2xl border bg-card p-5" aria-label="Fichier des services" id="section-fichier" tabindex="-1">
    <h2 class="text-lg font-semibold">Fichier des services</h2>
    <p class="mt-1 text-sm">
      {#if e.fraicheur.exemple}Absent : l'Anneau montre un exemple inventé. Importe ton fichier <code>services.yaml</code> ci-dessous.
      {:else}{nbServices} service(s) dans {e.familles.length} famille(s). Modifié il y a {duree(e.fraicheur.fichier_modifie_le)}, relu il y a {duree(e.fraicheur.fichier_lu_le)}.{/if}
    </p>
    {#if e.fraicheur.erreurs.length}
      <ul class="mt-2 list-disc pl-5 text-sm text-[var(--lave)]" aria-label="Lignes écartées">{#each e.fraicheur.erreurs as l}<li>{l}</li>{/each}</ul>
    {/if}
    <p class="mt-2 text-sm text-muted-foreground">Importe le <code>services.yaml</code> exporté de la note <em>Tuiles de l'Anneau</em> du coffre : il est vérifié, puis remplace l'actuel, gardé en secours. Il peut aussi se poser à la main dans le dossier de données, puis « Relire le fichier ».</p>
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
        <Button variant="outline" onclick={recharger} disabled={attente}>{attente ? 'Lecture…' : 'Relire le fichier'}</Button>
        {#if !e.fraicheur.exemple}<a class="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/api/services/fichier" download="services.yaml">Télécharger services.yaml</a>{/if}
      </div>
    {/if}
    {#if message}<p class="mt-3 text-sm" role="status" id="message">{message}</p>{/if}
  </section>

  <Veille {ondeconnecte} />

  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Versions" id="section-versions" tabindex="-1">
    <h2 class="text-lg font-semibold">Versions</h2>
    <p class="mt-1 text-sm text-muted-foreground">Version en service (lue par la veille) et dernière publiée (étiquettes GitHub du dépôt <code>depot:</code> de la tuile, relues chaque heure){vers?.publiees_lues_le ? `, lues il y a ${duree(vers.publiees_lues_le)}` : ''}. Watchtower installe chaque nuit à 05:00.</p>
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

  <section class="mt-3 rounded-2xl border bg-card p-5" aria-label="Bac à sable" id="section-bac" tabindex="-1">
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
{/if}

<style>
  .versions th, .versions td { padding: 0.45rem 0.5rem 0.45rem 0; border-top: 1px solid var(--border); vertical-align: top; white-space: nowrap; }
  .versions thead th { border-top: 0; font-size: 0.74rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted-foreground); }
  .versions tbody th { font-weight: 600; white-space: normal; }
  .versions small { display: block; color: var(--muted-foreground); font-size: 0.78rem; }
  section:focus { outline: none; }
</style>
