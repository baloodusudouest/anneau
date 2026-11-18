<script>
  // Une bulle de la carte : nom, port, famille (barre de couleur pour les applis maison), voyant de sa tuile.
  import { Handle, Position } from '@xyflow/svelte'
  import { couleur, VOYANTS } from './modele.js'
  let { data } = $props()
  const s = $derived(data.s)
  const v = $derived(VOYANTS[s.voyant] ?? VOYANTS.inconnu)
  const sous = $derived(s.port ? ':' + s.port : s.etat === 'pause' ? 'en pause' : s.incertain ? 'à vérifier' : '')
</script>

<div class="noeud {s.famille}" class:estompe={data.estompe} class:choisi={data.choisi} class:pause={s.etat === 'pause'} class:panne={s.voyant === 'panne'}
     style="--c: {couleur(s)}" title={s.role}>
  <Handle type="target" position={Position.Left} isConnectable={false} />
  <span class="voyant" style="background:{v.couleur}" title={v.nom} aria-label={v.nom}></span>
  <span class="txt">
    <span class="nom">{s.nom}</span>
    <span class="sous">{sous}</span>
  </span>
  <Handle type="source" position={Position.Right} isConnectable={false} />
</div>

<style>
  .noeud { display: flex; align-items: center; gap: 0.55rem; width: 190px; min-height: 52px; padding: 0.4rem 0.7rem; border-radius: 0.8rem;
    background: var(--card); border: 1px solid var(--border); color: var(--foreground); font-size: 0.82rem; line-height: 1.2;
    transition: opacity 0.2s, border-color 0.2s; cursor: pointer; }
  .maison { box-shadow: inset 4px 0 0 var(--c); border-color: color-mix(in srgb, var(--c) 45%, transparent); }
  .stockage { background: #1b1917; border-color: #3a352f; }
  .tiers { border-color: color-mix(in srgb, #7f93ab 40%, transparent); }
  .voyant { width: 0.7rem; height: 0.7rem; border-radius: 999px; flex: none; border: 1px solid color-mix(in srgb, var(--c) 50%, transparent); }
  .panne { border-color: var(--lave); }
  .txt { display: grid; min-width: 0; }
  .nom { font-weight: 600; overflow-wrap: anywhere; }
  .sous { color: var(--muted-foreground); font-size: 0.72rem; font-variant-numeric: tabular-nums; }
  .estompe { opacity: 0.16; }
  .pause { opacity: 0.5; border-style: dashed; }
  .estompe.pause { opacity: 0.12; }
  .choisi { border-color: var(--foreground); }
  .noeud :global(.svelte-flow__handle) { opacity: 0; width: 6px; height: 6px; border: 0; }
</style>
