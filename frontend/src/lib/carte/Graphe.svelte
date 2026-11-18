<script>
  // La carte (reprise d'Atlas 1.11) : une bulle par service, une flèche par flux, rangées en quartiers.
  // Chaque quartier est placé seul (dagre, de gauche à droite, ordre stable par identifiant), puis les quartiers en
  // grille. Les flèches qui changent de quartier sont pâles tant qu'on ne survole pas un de leurs bouts ; les fils de
  // fond (connexion commune, accès, mises à jour d'image) sont cachés par défaut. Le voyant de chaque bulle est celui
  // de sa tuile dans l'Anneau.
  import { SvelteFlow, Background, Controls, MarkerType, Panel, useSvelteFlow } from '@xyflow/svelte'
  import '@xyflow/svelte/dist/style.css'
  import dagre from '@dagrejs/dagre'
  import Noeud from './Noeud.svelte'
  import Quartier from './Quartier.svelte'
  import Circulation from './Circulation.svelte'
  import { NATURES, FOND, VOYANTS, nature, couleur, indexer, voisins, lienNote } from './modele.js'

  let { carte } = $props()
  const L = 190, H = 54
  const nodeTypes = { service: Noeud, quartier: Quartier }
  const MARGE = 36, TETE = 56, ECART = 90
  let largeurEcran = $state(typeof window !== 'undefined' ? window.innerWidth : 1600)
  const COLONNES = $derived(largeurEcran < 1200 ? 2 : 3)
  const { fitView } = useSvelteFlow()
  const court = (t, suite) => (t.length > 30 ? t.slice(0, 29).trimEnd() + '…' : t + (suite ? '…' : ''))
  $effect(() => { const f = () => (largeurEcran = window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f) })

  const idx = $derived(indexer(carte))
  let familles = $state({ maison: true, stockage: true, tiers: true })
  let machine = $state('')
  let autour = $state(null)
  let choisi = $state(null)
  let libelles = $state(false)
  let cherche = $state('')
  let fond = $state(false)
  let survol = $state(null)
  let enPanne = $state(false)

  function placerUn(services, flux) {
    const g = new dagre.graphlib.Graph()
    g.setGraph({ rankdir: 'LR', nodesep: 14, ranksep: 190, marginx: 0, marginy: 0 })
    g.setDefaultEdgeLabel(() => ({}))
    ;[...services].sort((a, b) => a.id.localeCompare(b.id)).forEach((s) => g.setNode(s.id, { width: L, height: H }))
    ;[...flux].sort((a, b) => (a.de + a.vers).localeCompare(b.de + b.vers)).forEach((f) => g.setEdge(f.de, f.vers))
    dagre.layout(g)
    const pos = Object.fromEntries(services.map((s) => { const n = g.node(s.id); return [s.id, { x: n.x - L / 2, y: n.y - H / 2 }] }))
    const xs = Object.values(pos)
    return { pos, largeur: Math.max(...xs.map((p) => p.x)) + L, hauteur: Math.max(...xs.map((p) => p.y)) + H }
  }

  function placer(services, flux) {
    const zones = []
    for (const q of carte.quartiers) {
      const dedans = services.filter((s) => s.quartier === q.id)
      if (!dedans.length) continue
      const ids_ = new Set(dedans.map((s) => s.id))
      const r = placerUn(dedans, flux.filter((f) => ids_.has(f.de) && ids_.has(f.vers) && !FOND.has(f.nature)))
      zones.push({ ...q, ...r, largeur: r.largeur + 2 * MARGE, hauteur: r.hauteur + TETE + MARGE })
    }
    const positions = {}, groupes = []
    let y = 0
    for (let k = 0; k < zones.length; k += COLONNES) {
      const rang = zones.slice(k, k + COLONNES)
      const haut = Math.max(...rang.map((z) => z.hauteur))
      let x = 0
      for (const z of rang) {
        groupes.push({ id: z.id, nom: z.nom, x, y, largeur: z.largeur, hauteur: haut })
        for (const [id, p] of Object.entries(z.pos)) positions[id] = { x: p.x + MARGE, y: p.y + TETE }
        x += z.largeur + ECART
      }
      y += haut + ECART
    }
    return { positions, groupes }
  }

  const visibles = $derived(carte.services.filter((s) => familles[s.famille] !== false && (!machine || s.machine === machine)
    && (!enPanne || s.voyant === 'panne')))
  const ids = $derived(new Set(visibles.map((s) => s.id)))
  const fluxVisibles = $derived(carte.flux.filter((f) => ids.has(f.de) && ids.has(f.vers) && (fond || !FOND.has(f.nature))))
  const plan = $derived(placer(visibles, carte.flux.filter((f) => ids.has(f.de) && ids.has(f.vers))))
  const quartierDe = $derived(Object.fromEntries(carte.services.map((x) => [x.id, x.quartier])))
  const proches = $derived(autour ? voisins(carte, autour) : null)

  let nodes = $state.raw([])
  let edges = $state.raw([])
  $effect(() => {
    nodes = [
      ...plan.groupes.map((g) => ({ id: 'q-' + g.id, type: 'quartier', position: { x: g.x, y: g.y }, draggable: false, selectable: false,
        zIndex: -1, data: { nom: g.nom, largeur: g.largeur, hauteur: g.hauteur, estompe: !!proches && ![...proches].some((v) => quartierDe[v] === g.id) } })),
      ...visibles.map((s) => ({ id: s.id, type: 'service', parentId: 'q-' + s.quartier, position: plan.positions[s.id], draggable: true,
        data: { s, estompe: !!proches && !proches.has(s.id), choisi: choisi === s.id } })),
    ]
  })
  $effect(() => {
    const actif = autour || survol
    edges = fluxVisibles.map((f, i) => {
      const n = NATURES[nature(f)] ?? NATURES.donnees
      const c = n.couleur
      const loin = !!proches && !(f.de === autour || f.vers === autour)
      const touche = !!actif && (f.de === actif || f.vers === actif)
      const traverse = quartierDe[f.de] !== quartierDe[f.vers]
      const pale = loin || f.etat === 'pause'
      const opacite = loin ? 0.05 : touche ? 1 : actif ? 0.08 : f.etat === 'pause' ? 0.3 : traverse ? 0.16 : 0.8
      const fleche = { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 }
      const premier = (f.infos && f.infos[0]) || ''
      return { id: `f${i}`, source: f.de, target: f.vers, type: traverse ? 'default' : 'smoothstep',
        label: premier && (libelles || touche || (proches && !loin)) ? court(premier, f.infos.length > 1) : undefined,
        style: `stroke:${c};stroke-width:${touche ? 2.2 : 1.5};stroke-dasharray:${n.trait || 'none'};opacity:${opacite}`,
        labelStyle: `background:#151311;color:#d8d0c4;font-size:11px;padding:1px 6px;border-radius:6px;border:1px solid #312c27;opacity:${pale ? 0.5 : 1}`,
        markerEnd: fleche, markerStart: f.echange ? fleche : undefined }
    })
  })

  async function centrer(id) {
    autour = id
    choisi = id
    await new Promise((r) => setTimeout(r, 30))
    fitView({ nodes: [...voisins(carte, id)].filter((v) => ids.has(v)).map((v) => ({ id: v })), duration: 400, padding: 0.25 })
  }
  function toutVoir() {
    autour = null
    setTimeout(() => fitView({ duration: 400, padding: 0.08 }), 30)
  }
  function chercher(e) {
    e.preventDefault()
    const t = cherche.trim().toLowerCase()
    const s = visibles.find((x) => x.nom.toLowerCase().includes(t) || x.id.includes(t))
    if (s) centrer(s.id)
  }
  const s = $derived(choisi ? idx.parId[choisi] : null)
  $effect(() => { visibles.length; const t = setTimeout(() => fitView({ padding: 0.06 }), 250); return () => clearTimeout(t) })
</script>

<div class="zone">
  <SvelteFlow bind:nodes bind:edges {nodeTypes} colorMode="dark" fitView minZoom={0.15} maxZoom={2} nodesConnectable={false}
              elementsSelectable={false} proOptions={{ hideAttribution: true }}
              onnodeclick={({ node }) => node.type === 'service' && (choisi = node.id)} onpaneclick={() => (choisi = null)}
              onnodepointerenter={({ node }) => node.type === 'service' && (survol = node.id)} onnodepointerleave={() => (survol = null)}>
    <Background gap={28} size={1} bgColor="#151311" patternColor="#2a2622" />
    <Controls showLock={false} position="bottom-right" />
    <Panel position="top-left">
      <div class="barre">
        <form class="cherche" onsubmit={chercher}>
          <label class="sr" for="cherche-carte">Chercher un service</label>
          <input id="cherche-carte" class="champ" type="search" bind:value={cherche} placeholder="Chercher un service" />
        </form>
        <div class="ligne" role="group" aria-label="Familles">
          {#each Object.entries(carte.familles || {}) as [cle, f]}
            <button class="choix" aria-pressed={familles[cle] !== false} onclick={() => (familles = { ...familles, [cle]: familles[cle] === false })}>
              <span class="puce" style="background:{cle === 'maison' ? 'var(--app)' : cle === 'stockage' ? '#8a8278' : '#7f93ab'}"></span>{f.nom}
            </button>
          {/each}
        </div>
        <div class="ligne">
          <label class="sr" for="machine">Machine</label>
          <select id="machine" class="champ machine" bind:value={machine}>
            <option value="">Toutes les machines</option>
            {#each carte.machines as m}<option value={m.id}>{m.nom}</option>{/each}
          </select>
          <button class="choix" aria-pressed={enPanne} onclick={() => (enPanne = !enPanne)}>En panne</button>
          <button class="choix" aria-pressed={libelles} onclick={() => (libelles = !libelles)}>Libellés</button>
          <button class="choix" aria-pressed={fond} onclick={() => (fond = !fond)} title="Connexion commune, accès, mises à jour d'image">Fils de fond</button>
          {#if autour}<button class="choix" aria-pressed="true" onclick={toutVoir}>Autour de {idx.parId[autour]?.nom} ✕</button>{/if}
        </div>
      </div>
    </Panel>
    <Panel position="bottom-left">
      <details class="legende">
        <summary>Légende</summary>
        <ul>
          {#each Object.entries(NATURES) as [cle, t]}
            <li><svg width="34" height="10" aria-hidden="true"><line x1="0" y1="5" x2="34" y2="5" stroke={t.couleur} stroke-width="2" stroke-dasharray={t.trait || 'none'} /></svg>{t.nom}</li>
          {/each}
          {#each ['ok', 'panne', 'inconnu'] as v}<li><span class="rond" style="background:{VOYANTS[v].couleur}"></span>Tuile {VOYANTS[v].nom}</li>{/each}
          <li><span class="rond vide"></span>Pas de tuile dans l'Anneau</li>
          <li class="text-muted-foreground">La flèche va de là où l'information naît vers là où elle arrive. Pointillés et estompé : en pause.</li>
        </ul>
      </details>
    </Panel>
  </SvelteFlow>

  {#if s}
    <aside class="panneau" aria-label={'Service ' + s.nom}>
      <div class="tete">
        <span class="puce" style="background:{couleur(s)}"></span>
        <h2>{s.nom}</h2>
        <button class="fermer" aria-label="Fermer" onclick={() => (choisi = null)}>✕</button>
      </div>
      <p class="text-sm text-muted-foreground">{carte.familles?.[s.famille]?.nom ?? s.famille} · {idx.machines[s.machine]?.nom ?? s.machine}{s.port ? ' · port ' + s.port : ''}
        · tuile {s.tuile ? VOYANTS[s.voyant]?.nom ?? s.voyant : 'absente'}{s.etat === 'pause' ? ' · en pause' : ''}{s.incertain ? ' · à vérifier' : ''}</p>
      <div class="gestes">
        <button class="bouton" onclick={() => centrer(s.id)}>Autour de lui</button>
        {#if lienNote(s)}<a class="bouton" href={lienNote(s)}>Sa note dans le coffre</a>{/if}
      </div>
      <p class="text-sm">{s.role}</p>
      <Circulation {carte} parId={idx.parId} id={s.id} ouvrir={(id) => (choisi = id)} />
    </aside>
  {/if}
</div>

<style>
  .zone { position: relative; width: 100%; height: calc(100dvh - 7.5rem); min-height: 28rem; border: 1px solid var(--border); border-radius: 1rem; overflow: hidden; }
  .zone :global(.svelte-flow__node-quartier) { pointer-events: none !important; }
  .zone :global(.svelte-flow__edge-label), .zone :global(.svelte-flow__edge-interaction) { pointer-events: none !important; }
  .zone :global(.svelte-flow__edge-label) { z-index: 2000 !important; }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .barre { display: grid; gap: 0.45rem; max-width: min(40rem, calc(100vw - 48px)); }
  .cherche { max-width: 20rem; }
  .champ { width: 100%; min-height: 2.5rem; border-radius: 0.7rem; border: 1px solid var(--border); background: rgb(21 19 17 / 0.92); color: var(--foreground); padding: 0 0.75rem; font-size: 0.9rem; }
  .ligne { display: flex; gap: 0.35rem; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
  .choix { display: inline-flex; align-items: center; gap: 0.4rem; min-height: 2.25rem; padding: 0 0.75rem; border-radius: 999px; border: 1px solid var(--border);
    background: rgb(21 19 17 / 0.92); color: var(--muted-foreground); white-space: nowrap; cursor: pointer; font-size: 0.85rem; }
  .choix[aria-pressed='true'] { background: var(--secondary); color: var(--foreground); border-color: var(--muted-foreground); }
  .machine { width: auto; flex: none; }
  .puce { width: 0.6rem; height: 0.6rem; border-radius: 999px; flex: none; display: inline-block; }
  .rond { width: 0.7rem; height: 0.7rem; border-radius: 999px; display: inline-block; flex: none; margin: 0 12px 0 11px; }
  .rond.vide { border: 1px solid var(--muted-foreground); }
  .legende { background: rgb(21 19 17 / 0.92); border: 1px solid var(--border); border-radius: 0.7rem; padding: 0.4rem 0.7rem; font-size: 0.8rem; max-width: 22rem; }
  .legende summary { cursor: pointer; min-height: 1.8rem; display: flex; align-items: center; }
  .legende ul { list-style: none; margin: 0.3rem 0 0; padding: 0; display: grid; gap: 0.2rem; }
  .legende li { display: flex; align-items: center; gap: 0.5rem; }
  .panneau { position: absolute; z-index: 20; top: 0; right: 0; bottom: 0; width: 24rem; max-width: 100%; overflow-y: auto;
    background: var(--card); border-left: 1px solid var(--border); padding: 1.25rem; }
  .tete { display: flex; align-items: center; gap: 0.6rem; }
  .tete h2 { margin: 0; font-size: 1.25rem; font-weight: 600; flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .fermer { display: grid; place-items: center; width: 2.75rem; height: 2.75rem; border: 0; background: transparent; cursor: pointer; color: var(--muted-foreground); font-size: 1.1rem; }
  .gestes { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.6rem 0 0.6rem; }
  .bouton { display: inline-flex; align-items: center; min-height: 2.5rem; padding: 0 0.9rem; border-radius: 0.65rem; border: 1px solid var(--border);
    background: transparent; color: var(--foreground); cursor: pointer; text-decoration: none; font-size: 0.88rem; }
  .zone :global(.svelte-flow__controls button) { background: var(--card); color: var(--foreground); border-color: var(--border); width: 2.2rem; height: 2.2rem; }
  .zone :global(.svelte-flow__controls button svg) { fill: currentColor; }
</style>
