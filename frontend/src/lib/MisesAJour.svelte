<script>
  // 0.18 : les applis de la stack homelab à mettre à jour, dans « À faire quand tu veux ».
  // Une ligne repliée « N applis à mettre à jour » ; dépliée, une ligne par appli avec son bouton « Mettre à jour »
  // (confirmation sur la ligne ; double confirmation pour un conteneur protégé ou une base de données, raison écrite).
  // Une version figée dans la stack (Immich…) n'a pas de bouton : la phrase dit quelle variable changer.
  // Le serveur vérifie tout (session, origine, ligne connue, étiquette de la stack, conteneur allumé, lecture seule) :
  // on n'envoie que l'identifiant de la ligne, et « protege: true » après la seconde confirmation.
  import { tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'

  let { m, tic, onfait } = $props()
  let ouvert = $state(false)
  let etape = $state({})              // id → 1 (première confirmation) ou 2 (seconde, conteneur protégé)
  let messages = $state({})           // id → message d'erreur du serveur
  let attente = $state('')            // id en cours d'envoi
  let verif = $state(false)
  let erreurVerif = $state('')

  const lignes = $derived(m?.lignes || [])
  const aFaire = $derived(lignes.filter((x) => x.sorte === 'maj' || x.sorte === 'figee'))
  const titre = $derived(m.nombre === 1 ? '1 appli à mettre à jour' : `${m.nombre} applis à mettre à jour`)

  async function focaliser(sel) { await tick(); document.querySelector(sel)?.focus() }
  function demander(x) { etape = { ...etape, [x.id]: 1 }; messages = { ...messages, [x.id]: '' }; focaliser(`[data-oui="${x.id}"]`) }
  function annuler(x) { const { [x.id]: _, ...reste } = etape; etape = reste; focaliser(`[data-maj="${x.id}"]`) }
  async function oui(x) {
    if (x.protege && etape[x.id] === 1) { etape = { ...etape, [x.id]: 2 }; return focaliser(`[data-oui="${x.id}"]`) }
    attente = x.id
    try {
      await api.post(`/api/majs/${encodeURIComponent(x.id)}/mettre-a-jour`, { protege: !!x.protege && etape[x.id] === 2 })
      annuler(x)
      await onfait?.()
    } catch (err) { messages = { ...messages, [x.id]: err.message } }
    attente = ''
  }
  async function verifier() {
    verif = true; erreurVerif = ''
    try { await api.post('/api/majs/verifier'); await onfait?.() } catch (err) { erreurVerif = err.message }
    verif = false
  }
</script>

<li class="majs">
  <div class="tete">
    <button type="button" class="deplier" aria-expanded={ouvert} onclick={() => (ouvert = !ouvert)}>
      <span class="fleche" class:ouverte={ouvert} aria-hidden="true">›</span>{titre}
    </button>
  </div>
  {#if ouvert}
    <ul class="detail" aria-label="Applis à mettre à jour">
      {#each lignes as x (x.id)}
        <li>
          <div class="ligne">
            <span>
              <b>{x.nom}</b>{#if x.phrase} <span class="phrase">{x.phrase}</span>{/if}
              {#if x.protege}<small class="protege">{x.protege.charAt(0).toUpperCase() + x.protege.slice(1)}</small>{/if}
              {#if x.ordre}
                <small class:echec={x.ordre.etat !== 'fini' && x.ordre.etat !== 'en_cours'} role="status">
                  {#if x.ordre.etat === 'en_cours'}<span class="tourne" aria-hidden="true"></span>{/if}{x.ordre.phrase}{x.ordre.detail ? ` (${x.ordre.detail})` : ''}
                </small>
              {:else if x.sorte === 'maj' && !x.bouton && x.pourquoi}
                <small>Pas de bouton : {x.pourquoi}.</small>
              {/if}
              {#if messages[x.id]}<small class="echec" role="alert">{messages[x.id]}</small>{/if}
            </span>
            {#if x.bouton && x.ordre?.etat !== 'en_cours' && !etape[x.id]}
              <button type="button" class="action" data-maj={x.id} onclick={() => demander(x)} aria-label={'Mettre à jour ' + x.nom}>Mettre à jour</button>
            {/if}
          </div>
          {#if etape[x.id]}
            <div class="confirmer" role="group" aria-label={'Confirmer la mise à jour de ' + x.nom}>
              <span>{etape[x.id] === 2 ? `Vraiment ? ${x.protege}.` : `Mettre à jour ${x.nom} maintenant ?`}</span>
              <span class="boutons">
                <button type="button" class="action" data-oui={x.id} disabled={attente === x.id} onclick={() => oui(x)}>
                  {etape[x.id] === 2 ? 'Oui, je confirme' : x.protege ? 'Continuer' : 'Mettre à jour'}
                </button>
                <button type="button" class="lien" onclick={() => annuler(x)}>Annuler</button>
              </span>
            </div>
          {/if}
        </li>
      {/each}
      {#if !aFaire.length}<li><span class="text-muted-foreground">Tout est à jour.</span></li>{/if}
    </ul>
    <p class="pied">
      {m.lu_le ? `Vérifié il y a ${duree(m.lu_le, tic)}` : 'Pas encore vérifié'}{m.non_verifiees?.length ? ` · ${m.non_verifiees.length} image${m.non_verifiees.length > 1 ? 's' : ''} non vérifiée${m.non_verifiees.length > 1 ? 's' : ''}` : ''}
      · <button type="button" class="lien" disabled={verif || m.en_verification} onclick={verifier}>{verif || m.en_verification ? 'Vérification…' : 'Vérifier maintenant'}</button>
    </p>
    {#if m.non_verifiees?.length}
      <details class="pied"><summary>Images non vérifiées</summary>
        <ul>{#each m.non_verifiees as n (n.nom)}<li>{n.nom} : {n.raison}</li>{/each}</ul>
      </details>
    {/if}
    {#if m.erreur || erreurVerif}<p class="pied echec" role="alert">{erreurVerif || m.erreur}</p>{/if}
  {/if}
</li>

<style>
  .majs { display: grid !important; gap: 0.5rem; }
  .tete { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; }
  .deplier { display: inline-flex; align-items: center; gap: 0.4rem; background: none; border: 0; padding: 0; color: inherit;
             font: inherit; text-align: left; cursor: pointer; min-height: 2rem; }
  .fleche { display: inline-block; transition: transform 0.15s; color: var(--spectre); font-size: 1.1rem; line-height: 1; }
  .fleche.ouverte { transform: rotate(90deg); }
  @media (prefers-reduced-motion: reduce) { .fleche { transition: none; } }
  .detail { display: grid; gap: 0.7rem; margin: 0; padding: 0 0 0 1.1rem; list-style: none; border-left: 1px solid var(--border); }
  .detail > li { display: grid; gap: 0.4rem; }
  .ligne { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; }
  .ligne > span { min-width: 0; }
  .ligne b { font-weight: 600; }
  .phrase { display: block; color: var(--muted-foreground); font-size: 0.88rem; font-variant-numeric: tabular-nums; }
  small { display: block; color: var(--muted-foreground); font-size: 0.82rem; }
  .protege { color: var(--braise); }
  .echec { color: var(--lave); }
  .action { flex: none; border: 1px solid var(--border); border-radius: 9999px; padding: 0.3rem 0.75rem; font-size: 0.82rem;
            background: var(--secondary, transparent); color: var(--foreground); cursor: pointer; min-height: 2rem; }
  .action:hover:not(:disabled) { border-color: var(--spectre); }
  .action:disabled { opacity: 0.6; cursor: default; }
  .confirmer { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.5rem;
               border: 1px solid color-mix(in srgb, var(--spectre) 45%, var(--border)); border-radius: 0.7rem; padding: 0.5rem 0.65rem;
               font-size: 0.85rem; }
  .boutons { display: inline-flex; gap: 0.6rem; align-items: center; }
  .lien { font-size: 0.82rem; color: var(--muted-foreground); background: none; border: 0; text-decoration: underline;
          text-underline-offset: 3px; min-height: 2rem; padding: 0 0.25rem; cursor: pointer; }
  .lien:hover:not(:disabled) { color: var(--foreground); }
  .pied { font-size: 0.8rem; color: var(--muted-foreground); margin: 0; }
  .pied ul { margin: 0.3rem 0 0; padding-left: 1rem; }
  .tourne { display: inline-block; width: 0.7rem; height: 0.7rem; margin-right: 0.35rem; border-radius: 9999px; vertical-align: -1px;
            border: 2px solid var(--muted-foreground); border-top-color: transparent; animation: tour 0.9s linear infinite; }
  @keyframes tour { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .tourne { animation: none; } }
</style>
