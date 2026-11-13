<script>
  // L'anneau : les familles écrites à la plume le long du cercle, en texte seul.
  // Toucher une famille la déplie : ses services montent de l'anneau et se rangent au-dessus du mot.
  // Or : tout répond. Rouge lave : en panne. Bleu spectral : quelque chose à faire.
  import { onMount } from 'svelte'

  let { familles = [], etats = {}, ouverte = null, etroit = false, centre = null, onfamille, onservice, onmilieu } = $props()

  const C = 400, R = 200, CORPS = 66, CORPS_SERVICE = 38
  const POLICE = '"Tangerine", "Snell Roundhand", cursive'
  let pret = $state(0)          // change quand la police est arrivée : les largeurs sont à remesurer
  let leve = $state(null)       // la famille dont les services viennent de monter (pour l'animation)

  onMount(() => { document.fonts?.ready.then(() => pret++) })

  let toile
  function largeur(texte, corps) {
    toile ??= document.createElement('canvas').getContext('2d')
    toile.font = `700 ${corps}px ${POLICE}`
    return toile.measureText(texte).width
  }
  const pt = (a, r) => [C + r * Math.sin(a * Math.PI / 180), C - r * Math.cos(a * Math.PI / 180)]

  // Chaque famille a son arc ; la moitié basse est retournée pour se lire à l'endroit.
  const arcs = $derived.by(() => {
    pret
    const pas = 360 / Math.max(familles.length, 1), demi = Math.min(pas / 2 - 1.5, 44)
    return familles.map((f, i) => {
      const a = i * pas, bas = a > 90 && a < 270
      const place = (R * 2 * demi * Math.PI) / 180
      const corps = Math.min(CORPS, (CORPS * place * 0.94) / Math.max(largeur(f.nom, CORPS), 1))
      const r = bas ? R + corps * 0.32 : R - corps * 0.28
      const [x1, y1] = pt(bas ? a + demi : a - demi, r), [x2, y2] = pt(bas ? a - demi : a + demi, r)
      return { f, a, bas, corps, d: `M ${x1} ${y1} A ${r} ${r} 0 0 ${bas ? 0 : 1} ${x2} ${y2}` }
    })
  })

  // Les services de la famille ouverte, rangés en arcs d'au plus 96 degrés au-dessus du mot.
  const montes = $derived.by(() => {
    pret
    const arc = arcs.find((x) => x.f.cle === ouverte)
    if (!arc || etroit) return []
    const rayon = (n) => 262 + n * (CORPS_SERVICE * 1.05 + 6)
    const rangees = []
    let rang = 0, somme = 0
    for (const s of arc.f.services) {
      const l = largeur(s.nom, CORPS_SERVICE) + 30
      let deg = (l / rayon(rang)) * 180 / Math.PI
      if (somme + deg > 96 && somme > 0) { rang++; somme = 0; deg = (l / rayon(rang)) * 180 / Math.PI }
      ;(rangees[rang] ||= []).push({ s, deg })
      somme += deg
    }
    return rangees.flatMap((liste, n) => {
      let curseur = -liste.reduce((t, x) => t + x.deg, 0) / 2
      return liste.map(({ s, deg }, j) => {
        const pos = curseur + deg / 2
        curseur += deg
        return { s, r: rayon(n), angle: arc.bas ? arc.a - pos : arc.a + pos, bas: arc.bas, rangDansFile: n * liste.length + j }
      })
    })
  })

  // L'animation : les noms partent de l'anneau, puis gagnent leur place.
  $effect(() => {
    const o = ouverte
    leve = null
    if (o) { const m = requestAnimationFrame(() => (leve = o)); return () => cancelAnimationFrame(m) }
  })
  const touche = (e, faire) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); faire() } }
</script>

<svg viewBox={etroit ? '150 150 500 500' : '0 0 800 800'} class="anneau" class:deplie={!!ouverte} role="group" aria-label="L'anneau des familles de services">
  <defs>
    <linearGradient id="or" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6e6b4" /><stop offset=".5" stop-color="#d9bd78" /><stop offset="1" stop-color="#b8975a" /></linearGradient>
    <linearGradient id="lave" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd27a" /><stop offset=".45" stop-color="#ff7a2a" /><stop offset="1" stop-color="#e02a0c" /></linearGradient>
    <linearGradient id="spectre" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9fbff" /><stop offset=".5" stop-color="#8fdcff" /><stop offset="1" stop-color="#3fa9f5" /></linearGradient>
  </defs>
  <circle cx={C} cy={C} r="232" fill="none" stroke="url(#or)" stroke-width="1.5" />
  <circle cx={C} cy={C} r="168" fill="none" stroke="url(#or)" stroke-width="1.5" />

  {#each arcs as arc, i (arc.f.cle)}
    <path id={'arc-' + i} d={arc.d} fill="none" />
    <text class="famille {etats[arc.f.cle] || ''}" class:active={ouverte === arc.f.cle} font-size={arc.corps} tabindex="0" role="button"
          aria-expanded={ouverte === arc.f.cle} aria-label={arc.f.nom + (etats[arc.f.cle] === 'panne' ? ', en panne' : etats[arc.f.cle] === 'faire' ? ', quelque chose à faire' : '')}
          onclick={() => onfamille?.(arc.f.cle)} onkeydown={(e) => touche(e, () => onfamille?.(arc.f.cle))}>
      <textPath href={'#arc-' + i} startOffset="50%" text-anchor="middle">{arc.f.nom}</textPath>
    </text>
  {/each}

  {#each montes as m (m.s.cle)}
    <g transform="translate({C} {C}) rotate({m.angle})">
      <g class="monte" class:la={leve === ouverte} style:transform="translateY(-{leve === ouverte ? m.r : R}px)" style:transition-delay="{m.rangDansFile * 22}ms">
        <text class="service {m.s.etat}" text-anchor="middle" font-size={CORPS_SERVICE} tabindex="0" role="link"
              transform="{m.bas ? 'rotate(180) ' : ''}translate(0 {CORPS_SERVICE * 0.3})"
              aria-label={m.s.nom + (m.s.etat === 'panne' ? ', en panne' : '')}
              onclick={() => onservice?.(m.s)} onmousedown={(e) => e.button === 1 && e.preventDefault()}
              onauxclick={(e) => { if (e.button === 1) { e.preventDefault(); onmilieu?.(m.s) } }} onkeydown={(e) => touche(e, () => onservice?.(m.s))}>{m.s.nom}</text>
      </g>
    </g>
  {/each}

  {#if centre}
    <text x={C} y={C - 6} text-anchor="middle" class="centre-grand {centre.rang}" font-size={etroit ? 66 : 58}>{centre.grand}</text>
    {#if centre.petit}<text x={C} y={C + (etroit ? 34 : 30)} text-anchor="middle" class="centre-petit" font-size={etroit ? 19 : 15}>{centre.petit}</text>{/if}
  {/if}
</svg>

<style>
  .anneau { display: block; width: 100%; height: auto; overflow: visible; }
  text { font-family: var(--plume); font-weight: 700; }
  text:focus:not(:focus-visible) { outline: none; }
  .famille { cursor: pointer; fill: url(#or); transition: opacity 0.25s; }
  .famille:hover, .famille.active { fill: var(--or-vif); }
  .famille.inconnu { fill: var(--or-sourd); }
  .deplie .famille:not(.active):not(.panne):not(.faire) { opacity: 0.38; }
  .service { cursor: pointer; fill: var(--app); }
  .service:hover { fill: var(--or-vif); }
  .service.inconnu, .service.eteint { fill: var(--or-sourd); }
  .famille.panne, .famille.panne.active, .service.panne, .centre-grand.panne {
    fill: url(#lave); filter: drop-shadow(0 0 5px rgb(255 80 20 / 0.85)) drop-shadow(0 0 14px rgb(255 60 0 / 0.45)); animation: braise 2.6s ease-in-out infinite; }
  .famille.faire, .famille.faire.active { fill: url(#spectre); filter: drop-shadow(0 0 5px rgb(90 200 255 / 0.85)) drop-shadow(0 0 14px rgb(60 170 255 / 0.45)); }
  .centre-grand { fill: url(#or); }
  .centre-grand.faire { fill: url(#spectre); }
  .centre-petit { font-family: var(--font-sans); font-weight: 400; fill: #9adfff; }
  .monte { opacity: 0; transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.25s ease; }
  .monte.la { opacity: 1; }
  @keyframes braise { 50% { filter: drop-shadow(0 0 8px rgb(255 110 30)) drop-shadow(0 0 22px rgb(255 60 0 / 0.6)); } }
  @media (prefers-reduced-motion: reduce) { .famille.panne, .service.panne, .centre-grand.panne { animation: none; } .monte { transition: none; } }
</style>
