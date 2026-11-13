<script>
  // L'écran de l'Anneau. Deux vues :
  //  - l'anneau des familles, avec ce qui est en panne et ce qui est à faire ;
  //  - la vue réduite, quand un service est ouvert : l'anneau d'or en haut à gauche (retour),
  //    une colonne d'icônes (une par famille), les services de la famille en pastilles, et le service.
  //    Le cadre laisse passer l'appareil photo (numérisation), le plein écran et la copie.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree } from '$lib/temps.js'
  import Cercle from '$lib/Cercle.svelte'
  import Icone from '$lib/Icone.svelte'
  import { Button } from '$lib/components/ui/button/index.js'

  let { ondeconnecte, onreglages } = $props()
  let e = $state(null)               // l'état rendu par l'Anneau
  let erreur = $state('')
  let ouverte = $state(null)         // clé de la famille dépliée
  let service = $state(null)         // { famille, cle } du service ouvert (vue réduite)
  let etroit = $state(false)
  let tic = $state(Date.now())       // pour que « il y a 40 s » avance tout seul

  async function lire() {
    try { e = await api.get('/api/etat'); erreur = '' } catch (x) { if (x.statut === 401) ondeconnecte?.(); else erreur = x.message }
  }
  onMount(() => {
    const mq = matchMedia('(max-width: 899px)')
    const suivre = () => (etroit = mq.matches)
    suivre(); mq.addEventListener('change', suivre)
    lire()
    const a = setInterval(lire, 20000), b = setInterval(() => (tic = Date.now()), 5000)
    return () => { clearInterval(a); clearInterval(b); mq.removeEventListener('change', suivre) }
  })

  const familles = $derived(e?.familles || [])
  const pannes = $derived(e?.pannes || [])
  const aFaire = $derived(e?.a_faire || [])
  // l'état écrit sur l'anneau : la panne passe devant ce qui est à faire
  const etats = $derived(Object.fromEntries(familles.map((f) => [f.cle, f.etat === 'panne' ? 'panne' : aFaire.some((x) => x.famille === f.nom) ? 'faire' : f.etat === 'inconnu' ? 'inconnu' : ''])))
  const centre = $derived(!e ? null
    : pannes.length ? { rang: 'panne', grand: `${pannes.length} en panne`, petit: aFaire.length ? `${aFaire.length} chose${aFaire.length > 1 ? 's' : ''} à faire` : '' }
    : { rang: aFaire.length ? 'faire' : '', grand: 'Tout va bien', petit: aFaire.length ? `${aFaire.length} chose${aFaire.length > 1 ? 's' : ''} à faire quand tu veux` : '' })
  const familleOuverte = $derived(familles.find((f) => f.cle === ouverte))
  const familleDuService = $derived(service ? familles.find((f) => f.cle === service.famille) : null)
  const leService = $derived(familleDuService?.services.find((s) => s.cle === service.cle) || null)

  const PHRASES = { ok: 'répond', panne: 'ne répond plus', eteint: 'est éteint (arrêt attendu)', inconnu: 'pas encore vérifié' }
  const deplier = (cle) => (ouverte = ouverte === cle ? null : cle)
  const ouvrir = (f, s) => { service = { famille: f.cle, cle: s.cle }; ouverte = f.cle }
  const fermer = () => (service = null)
  // « Ouvrir » réutilise toujours la même fenêtre pour un service : les onglets ne se multiplient pas.
  const dehors = (s) => window.open(s.adresse, 'anneau-' + s.cle)
  // Le bouton du milieu ouvre le service dans un nouvel onglet, sans quitter l'anneau.
  const onglet = (s) => window.open(s.adresse, '_blank', 'noopener')
  const milieu = (s) => ({
    onmousedown: (ev) => { if (ev.button === 1) ev.preventDefault() },   // pas de défilement automatique
    onauxclick: (ev) => { if (ev.button === 1) { ev.preventDefault(); onglet(s) } },
  })
  async function vue(p) { try { await api.post('/api/pannes/vue', { cle: p.cle }); await lire() } catch (x) { erreur = x.message } }
</script>

{#if !e}
  <p class="p-8 text-sm text-muted-foreground" role="status">{erreur || 'Lecture…'}</p>
{:else if leService}
  <!-- ───────────── Vue réduite ───────────── -->
  <div class="reduit">
    <button type="button" class="retour" aria-label="Revenir à l'anneau" onclick={fermer}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <defs><linearGradient id="orBague" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff1b0" /><stop offset=".3" stop-color="#f2c14e" /><stop offset=".58" stop-color="#b9831c" /><stop offset=".8" stop-color="#e9b84a" /><stop offset="1" stop-color="#8a5a0c" /></linearGradient></defs>
        <circle cx="50" cy="50" r="33" fill="none" stroke="url(#orBague)" stroke-width="12" />
        <circle cx="50" cy="50" r="38.600" fill="none" stroke="#fff3c4" stroke-width="1" opacity=".55" />
        <circle cx="50" cy="50" r="27.400" fill="none" stroke="#5a3a08" stroke-width="1.200" opacity=".7" />
        <path d="M 24 37 A 29 29 0 0 1 41 22" fill="none" stroke="#fffbe6" stroke-width="2.600" stroke-linecap="round" opacity=".8" />
      </svg>
    </button>
    <nav class="colonne" aria-label="Familles">
      {#each familles as f (f.cle)}
        <button type="button" title={f.nom} aria-label={f.nom} aria-current={f.cle === service.famille ? 'true' : undefined}
                onclick={() => f.services.length && ouvrir(f, f.services[0])}>
          <Icone icone={f.icone} etat={etats[f.cle] || (f.cle === service.famille ? 'vif' : 'sourd')} taille={26} />
        </button>
      {/each}
    </nav>
    <div class="pastilles" aria-label={'Services de ' + familleDuService.nom}>
      {#each familleDuService.services as s (s.cle)}
        <button type="button" aria-current={s.cle === service.cle ? 'true' : undefined} onclick={() => ouvrir(familleDuService, s)} {...milieu(s)}>
          <Icone icone={s.icone} etat={s.cle === service.cle && s.etat === 'ok' ? 'sombre' : s.etat === 'ok' ? '' : s.etat} />{s.nom}</button>
      {/each}
    </div>
    <section class="contenu" aria-label={leService.nom}>
      {#if leService.cadre && leService.etat !== 'panne'}
        {#key leService.adresse}<iframe src={leService.adresse} title={leService.nom} allow="camera; fullscreen; clipboard-write"></iframe>{/key}
      {:else}
        <div class="fiche">
          <h1 class="plume" class:panne={leService.etat === 'panne'}>{leService.nom}</h1>
          <p role="status">{leService.nom} {PHRASES[leService.etat]}{leService.depuis ? ` depuis ${duree(leService.depuis, tic)}` : ''}{leService.etat === 'ok' && leService.delai != null ? ` · réponse en ${leService.delai} ms` : ''}.</p>
          {#if leService.machine_en_panne}<p class="text-sm text-muted-foreground">{leService.machine} ne répond plus : c'est lui qui est en panne.</p>{/if}
          <Button onclick={() => dehors(leService)}>Ouvrir {leService.nom}</Button>
          <p class="text-sm text-muted-foreground">{leService.cadre ? 'En panne : rien à afficher ici.' : 'Ce service ne s\'affiche pas dans l\'Anneau : il s\'ouvre à côté, toujours dans la même fenêtre.'}</p>
        </div>
      {/if}
    </section>
  </div>
{:else}
  <!-- ───────────── L'anneau ───────────── -->
  <div class="accueil">
    <button type="button" class="roue" aria-label="Réglages" onclick={onreglages}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M5 7.500h6M15 7.500h4M5 16.500h3M12 16.500h7" /><circle cx="13" cy="7.500" r="2" /><circle cx="10" cy="16.500" r="2" /></svg>
    </button>
    <div class="rond">
      <Cercle {familles} {etats} {ouverte} {etroit} {centre} onfamille={deplier} onservice={(s) => ouvrir(familleOuverte, s)} onmilieu={onglet} />
      {#if etroit && familleOuverte}
        <div class="dessous" aria-label={'Services de ' + familleOuverte.nom}>
          <h2 class="plume">{familleOuverte.nom}</h2>
          <div class="pastilles libres">
            {#each familleOuverte.services as s, i (s.cle)}
              <button type="button" style:animation-delay="{i * 28}ms" onclick={() => ouvrir(familleOuverte, s)} {...milieu(s)}><Icone icone={s.icone} etat={s.etat === 'ok' ? '' : s.etat} />{s.nom}</button>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <div class="listes">
      <p class="frais" role="status">
        {#if e.fraicheur.sonde}Dernière vérification il y a {duree(e.fraicheur.sonde, tic)}{:else}Première vérification en cours…{/if}{#if e.fraicheur.ha_attendu}
          · Home Assistant : {e.fraicheur.ha_recu_le ? 'il y a ' + duree(e.fraicheur.ha_recu_le, tic) : 'aucun envoi reçu'}{/if}
      </p>
      {#if erreur}<p class="text-sm" role="alert">L'Anneau ne répond plus : {erreur}. Ce qui est affiché date d'avant.</p>{/if}
      {#if e.fraicheur.exemple}<p class="avis">Le fichier des services est absent : l'Anneau montre un exemple inventé.</p>{/if}
      {#if e.fraicheur.erreurs.length}<p class="avis">Fichier des services : {e.fraicheur.erreurs.length} ligne(s) écartée(s). Détail dans Réglages.</p>{/if}

      {#if pannes.length}
        <section class="rang panne" aria-label="En panne">
          <h2><span>En panne</span><span>{pannes.length}</span></h2>
          <ul>
            {#each pannes as p (p.cle)}
              <li>
                <span>{p.phrase}<small>depuis {duree(p.ouverte_le, tic)}{p.famille ? ' · ' + p.famille : ''}{p.prise_en_compte_le ? ' · pris en compte' : ''}</small></span>
                {#if !p.prise_en_compte_le}<button type="button" class="lien" onclick={() => vue(p)} aria-label={'Pris en compte : ' + p.phrase}>Pris en compte</button>{/if}
              </li>
            {/each}
          </ul>
        </section>
      {/if}
      {#if aFaire.length}
        <section class="rang faire" aria-label="À faire quand tu veux">
          <h2><span>À faire quand tu veux</span><span>{aFaire.length}</span></h2>
          <ul>{#each aFaire as x (x.cle)}<li><span>{x.phrase}{#if x.famille}<small>{x.famille}</small>{/if}</span></li>{/each}</ul>
        </section>
      {/if}
      {#if !pannes.length && !aFaire.length && e.fraicheur.sonde}
        <p class="text-sm text-muted-foreground">Rien à signaler. Touche une famille pour voir ses services.</p>
      {/if}
    </div>
  </div>
{/if}

<style>
  .plume { font-family: var(--plume); font-weight: 700; color: var(--app); line-height: 1; }
  .plume.panne { color: var(--lave); text-shadow: 0 0 12px rgb(255 80 20 / 0.6); }

  /* ── l'anneau ── */
  .accueil { position: relative; display: grid; gap: 0.5rem 2rem; align-items: start; min-height: 100dvh;
             padding: calc(0.75rem + env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right)) calc(2rem + env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left)); }
  .rond { width: 100%; max-width: 46rem; margin: 0 auto; min-width: 0; }
  @media (max-width: 899px) { .rond { padding-top: 2.75rem; } .listes > p { text-align: center; } }
  .listes { display: grid; gap: 0.75rem; min-width: 0; width: 100%; max-width: 30rem; margin: 0 auto; }
  @media (min-width: 900px) {
    .accueil { grid-template-columns: minmax(0, 1fr) 21rem; align-items: center; padding-inline: 2rem; }
    .listes { margin: 0; }
  }
  .roue { position: absolute; top: calc(0.75rem + env(safe-area-inset-top)); right: max(1rem, env(safe-area-inset-right)); z-index: 2; display: grid; place-items: center;
          width: 2.75rem; height: 2.75rem; border-radius: 9999px; color: var(--muted-foreground); background: none; border: 1px solid var(--border); }
  .roue:hover { color: var(--foreground); }
  .frais { font-size: 0.8rem; color: var(--muted-foreground); text-align: center; }
  @media (min-width: 900px) { .frais { text-align: left; } }
  .avis { font-size: 0.85rem; border: 1px solid var(--border); border-radius: 0.9rem; padding: 0.6rem 0.9rem; color: var(--muted-foreground); }
  .rang { border: 1px solid var(--border); border-radius: 1rem; padding: 0.8rem 0.95rem; background: var(--card); }
  .rang h2 { display: flex; justify-content: space-between; margin: 0 0 0.55rem; font-size: 0.74rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }
  .rang.panne h2 { color: var(--lave); }
  .rang.faire h2 { color: var(--spectre); }
  .rang ul { display: grid; gap: 0.65rem; margin: 0; padding: 0; list-style: none; }
  .rang li { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; }
  .rang li span { min-width: 0; }
  .rang small { display: block; color: var(--muted-foreground); font-size: 0.82rem; }
  .lien { flex: none; font-size: 0.82rem; color: var(--muted-foreground); background: none; border: 0; text-decoration: underline; text-underline-offset: 3px; min-height: 2.75rem; padding: 0 0.25rem; }
  .lien:hover { color: var(--foreground); }
  .dessous { display: flex; flex-direction: column; align-items: center; gap: 0.6rem; margin: 0.25rem 0 1rem; }
  .dessous h2 { font-size: 2.2rem; margin: 0; }

  /* ── pastilles (services d'une famille) ── */
  .pastilles { display: flex; gap: 0.4rem; overflow-x: auto; scrollbar-width: none; min-width: 0; }
  .pastilles.libres { flex-wrap: wrap; justify-content: center; overflow: visible; }
  .pastilles button { display: inline-flex; align-items: center; gap: 0.45rem; flex: none; min-height: 2.5rem; padding: 0 0.85rem; border-radius: 9999px; white-space: nowrap;
                      font-size: 0.87rem; color: var(--muted-foreground); background: var(--card); border: 1px solid var(--border); }
  .pastilles button[aria-current='true'] { color: #1e1a16; background: var(--app); border-color: var(--app); font-weight: 600; }
  .pastilles.libres button { color: var(--foreground); animation: descend 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
  @keyframes descend { from { opacity: 0; transform: translateY(-10px); } }

  /* ── vue réduite ── */
  .reduit { display: grid; grid-template-columns: 4.5rem minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); gap: 0.6rem 0.5rem; height: 100dvh;
            padding: calc(0.6rem + env(safe-area-inset-top)) max(0.6rem, env(safe-area-inset-right)) calc(0.6rem + env(safe-area-inset-bottom)) max(0.4rem, env(safe-area-inset-left)); }
  @media (min-width: 900px) { .reduit { grid-template-columns: 5.5rem minmax(0, 1fr); gap: 0.75rem; padding: 0.75rem; } }
  .retour { grid-row: 1; grid-column: 1; align-self: center; justify-self: center; width: 100%; max-width: 4.6rem; padding: 0; background: none; border: 0; border-radius: 9999px;
            filter: drop-shadow(0 0 10px rgb(255 170 40 / 0.45)); animation: arrive 0.45s cubic-bezier(0.6, 0, 0.2, 1) both; }
  .retour svg { display: block; width: 100%; height: auto; }
  @keyframes arrive { from { transform: translate(35vw, 30vh) scale(4); opacity: 0.3; } }
  .reduit > .pastilles { grid-row: 1; grid-column: 2; align-self: center; }
  .colonne { grid-row: 2; grid-column: 1; display: flex; flex-direction: column; align-items: center; gap: 0.25rem; overflow-y: auto; scrollbar-width: none; }
  .colonne button { display: grid; place-items: center; width: 3.25rem; height: 3rem; border-radius: 0.7rem; background: none; border: 0; border-left: 2px solid transparent; }
  .colonne button[aria-current='true'] { background: var(--card); border-left-color: var(--app); }
  .contenu { grid-row: 2; grid-column: 2; min-height: 0; border: 1px solid var(--border); border-radius: 0.9rem; background: var(--card); overflow: hidden; }
  .contenu iframe { display: block; width: 100%; height: 100%; border: 0; background: var(--background); }
  .fiche { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.8rem; padding: 1.5rem; text-align: center; }
  .fiche h1 { font-size: 3.4rem; margin: 0; }
  .fiche p { max-width: 44ch; margin: 0; }
  @media (prefers-reduced-motion: reduce) { .retour, .pastilles.libres button { animation: none; } }
</style>
