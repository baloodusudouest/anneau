<script>
  // 0.19 : « Réglages » en un seul écran (choix de Julien du 26/11/2026). L'accueil montre cinq thèmes, chacun avec son
  // état, un chiffre et, s'il y a lieu, une pastille (rouge lave : en panne ; bleu : à faire ; or : à traiter) ;
  // un clic ouvre le thème (#/reglages/<thème>), avec le fil, la barre des cinq thèmes et « Revenir à l'anneau ».
  // Chaque chose n'est qu'à un seul endroit : l'ancienne page Réglages, Variables, Sauvegardes et la Carte y sont rangées.
  import { tick } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import { THEMES, theme as leTheme, resumer } from '$lib/reglages/themes.js'
  import IconeTheme from '$lib/reglages/IconeTheme.svelte'
  import Services from '$lib/reglages/Services.svelte'
  import Stack from '$lib/reglages/Stack.svelte'
  import Sauvegardes from '$lib/reglages/Sauvegardes.svelte'
  import Connexions from '$lib/reglages/Connexions.svelte'
  import Maison from '$lib/reglages/Maison.svelte'

  let { session, deconnecter, ondeconnecte, theme = '', section = '' } = $props()
  const t = $derived(leTheme(theme))

  // ---------------------------------------------------------------- l'accueil : ce que chaque thème a à dire
  let lu = $state({})
  let lecture = $state(false)
  async function lireAccueil() {
    lecture = true
    const demandes = {
      etat: '/api/etat', sauvegardes: '/api/sauvegardes', stack: '/api/stack', exports: '/api/variables-chiffrees',
      cle: '/api/cle-publique', connexions: '/api/maison/services', carte: '/api/carte', https: '/api/https',
    }
    const cles = Object.keys(demandes)
    const r = await Promise.allSettled(cles.map((k) => api.get(demandes[k])))
    if (r.some((x) => x.status === 'rejected' && x.reason?.statut === 401)) { ondeconnecte?.(); return }
    const sortie = {}
    cles.forEach((k, i) => { if (r[i].status === 'fulfilled') sortie[k] = r[i].value })
    if (sortie.exports) sortie.exports = sortie.exports.exports
    if (sortie.cle) sortie.cle = sortie.cle.cle_publique
    lu = sortie
    lecture = false
  }
  const resume = $derived(resumer(lu))
  $effect(() => { if (!theme) lireAccueil() })

  // sur téléphone, la barre défile : le thème ouvert y est toujours visible
  $effect(() => {
    if (!theme) return
    tick().then(() => document.querySelector('.barre [aria-current="page"]')?.scrollIntoView?.({ inline: 'center', block: 'nearest' }))
  })

  // ---------------------------------------------------------------- une section précise (#/reglages/stack/exports)
  $effect(() => {
    const id = theme && section ? 'section-' + section : ''
    if (!id) return
    let essais = 0
    const viser = async () => {
      await tick()
      const el = document.getElementById(id)
      if (el) { el.scrollIntoView({ block: 'start' }); el.focus?.({ preventScroll: true }); return }
      if (++essais < 40) setTimeout(viser, 50)     // la section arrive avec sa lecture (2 s au plus)
    }
    viser()
  })
</script>

<main class={['mx-auto px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8',
              theme === 'maison' ? 'max-w-6xl' : theme ? 'max-w-3xl' : 'max-w-5xl']}>
  {#if !t}
    <!-- ===================================================== l'accueil -->
    <header class="mb-6 flex items-end justify-between gap-3">
      <div><p class="etiquette">L'Anneau</p><h1 class="titre">Réglages</h1></div>
      <a class="text-sm underline underline-offset-4" href="#/">Revenir à l'anneau</a>
    </header>
    {#if lu.https?.lecture_seule}
      <p class="mb-4 rounded-2xl border p-4 text-sm" role="status" id="bandeau-lecture-seule">
        <strong>Lecture seule.</strong> L'Anneau n'envoie aucun ordre aux autres services (Portainer, Watchtower, Home Assistant).
        Ses propres fichiers restent modifiables ici.
      </p>
    {/if}
    <ul class="themes" aria-label="Thèmes des réglages" aria-busy={lecture}>
      {#each THEMES as x (x.id)}
        {@const r = resume[x.id]}
        <li>
          <a class="theme" href={'#/reglages/' + x.id} data-signal={r.signal?.niveau || ''} aria-describedby={'dit-' + x.id}>
            <span class="tete"><IconeTheme id={x.id} taille={22} /><span class="nom">{x.nom}</span></span>
            <span class="mesure"><span class="chiffre">{r.chiffre}</span>{#if r.unite}<span class="unite">{r.unite}</span>{/if}</span>
            <span class="phrase" id={'dit-' + x.id}>{r.phrase}</span>
            {#if r.signal}<span class="signal"><span class="point" aria-hidden="true"></span>{r.signal.texte}</span>{/if}
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <!-- ===================================================== un thème -->
    <header class="mb-3 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="etiquette" aria-label="Fil"><a class="hover:text-foreground" href="#/">L'Anneau</a> › <a class="hover:text-foreground" href="#/reglages">Réglages</a></nav>
        <h1 class="titre">{t.nom}</h1>
      </div>
      <a class="text-sm underline underline-offset-4" href="#/">Revenir à l'anneau</a>
    </header>
    <nav class="barre" aria-label="Thèmes">
      <a href="#/reglages" class="accueil-lien" aria-label="Tous les réglages">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>Réglages
      </a>
      {#each THEMES as x (x.id)}
        <a href={'#/reglages/' + x.id} aria-current={x.id === theme ? 'page' : undefined}><IconeTheme id={x.id} taille={17} />{x.nom}</a>
      {/each}
    </nav>
    <div class="mt-5">
      {#key theme}
        {#if theme === 'services'}<Services {ondeconnecte} />
        {:else if theme === 'stack'}<Stack {ondeconnecte} />
        {:else if theme === 'sauvegardes'}<Sauvegardes {ondeconnecte} />
        {:else if theme === 'connexions'}<Connexions {ondeconnecte} />
        {:else if theme === 'maison'}<Maison {ondeconnecte} />{/if}
      {/key}
    </div>
  {/if}

  <p class="mt-8 flex items-center justify-between gap-3 text-sm text-muted-foreground">
    <span>L'Anneau {session.version}</span>
    <Button variant="outline" onclick={deconnecter}>Se déconnecter</Button>
  </p>
</main>

<style>
  /* Accueil : cinq thèmes. Sur PC, deux larges puis trois (6 colonnes) ; sur téléphone, une colonne.
     Le nom du thème est écrit à la plume, comme l'inscription de l'anneau : c'est le seul ornement de l'écran. */
  .themes { display: grid; gap: 0.75rem; grid-template-columns: 1fr; list-style: none; margin: 0; padding: 0; }
  @media (min-width: 720px) {
    .themes { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .themes > li { grid-column: span 2; }
    .themes > li:nth-child(-n + 2) { grid-column: span 3; }
  }
  .theme { display: grid; gap: 0.35rem; align-content: start; height: 100%; min-height: 9.5rem; padding: 1rem 1.15rem 1.1rem;
           border: 1px solid var(--border); border-radius: 1.1rem; background: var(--card); color: var(--foreground); text-decoration: none; }
  .theme:hover { border-color: color-mix(in srgb, var(--foreground) 22%, var(--border)); }
  .theme:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
  .theme[data-signal='panne'] { border-color: color-mix(in srgb, var(--lave) 55%, var(--border)); }
  .theme[data-signal='action'] { border-color: color-mix(in srgb, var(--spectre) 45%, var(--border)); }
  .theme[data-signal='traiter'] { border-color: color-mix(in srgb, var(--app) 40%, var(--border)); }
  .tete { display: flex; align-items: center; gap: 0.55rem; color: var(--muted-foreground); }
  .nom { font-family: var(--plume); font-weight: 700; font-size: 2.05rem; line-height: 1; color: var(--app); }
  .mesure { display: flex; align-items: baseline; gap: 0.4rem; margin-top: 0.35rem; }
  .mesure .chiffre { font-size: 2.3rem; }
  .unite { font-size: 0.9rem; color: var(--muted-foreground); }
  .phrase { font-size: 0.875rem; color: var(--muted-foreground); max-width: 34ch; }
  .signal { display: inline-flex; align-items: center; gap: 0.45rem; margin-top: 0.25rem; font-size: 0.85rem; font-weight: 500; }
  .point { width: 0.55rem; height: 0.55rem; border-radius: 9999px; background: var(--muted-foreground); flex: none; }
  [data-signal='panne'] .signal { color: var(--lave); } [data-signal='panne'] .point { background: var(--lave); }
  [data-signal='action'] .signal { color: var(--spectre); } [data-signal='action'] .point { background: var(--spectre); }
  [data-signal='traiter'] .signal { color: var(--app); } [data-signal='traiter'] .point { background: var(--app); }

  /* Barre des thèmes : le thème ouvert en clair et souligné (jamais en or : l'or dit « à traiter »). */
  .barre { display: flex; gap: 0.25rem; overflow-x: auto; scrollbar-width: none; margin: 0 calc(-1 * max(1rem, env(safe-area-inset-left)));
           padding: 0 max(1rem, env(safe-area-inset-left)); border-bottom: 1px solid var(--border); }
  .barre::-webkit-scrollbar { display: none; }
  .barre a { display: inline-flex; align-items: center; gap: 0.4rem; flex: none; min-height: 2.75rem; padding: 0 0.7rem; font-size: 0.9rem;
             color: var(--muted-foreground); text-decoration: none; border-bottom: 2px solid transparent; margin-bottom: -1px; }
  .barre a:hover { color: var(--foreground); }
  .barre a[aria-current='page'] { color: var(--foreground); border-bottom-color: var(--foreground); font-weight: 600; }
  .barre .accueil-lien { padding-left: 0; padding-right: 0.9rem; margin-right: 0.25rem; border-right: 1px solid var(--border); }
  @media (min-width: 768px) { .barre { margin: 0; padding: 0; } }
</style>
