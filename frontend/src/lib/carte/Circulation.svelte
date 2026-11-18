<script>
  // Pour un service : ce qui le nourrit, ce qu'il écrit, ce qu'il échange, puis les accès et mises à jour.
  // `ouvrir(id)` : clic sur un service voisin.
  import { circulation } from './modele.js'
  let { carte, parId, id, ouvrir } = $props()
  const c = $derived(circulation(carte, id))
  const vide = $derived(!c.nourrit.length && !c.ecrit.length && !c.echange.length && !c.autres.length)
</script>

{#snippet nomDe(a)}<button class="lien" onclick={() => ouvrir(a)}>{parId[a]?.nom ?? a}</button>{/snippet}
{#snippet suite(f)}
  {#if f.moyen}<span class="moyen">{f.moyen}</span>{/if}
  {#if f.etat === 'pause'}<span class="pastille">en pause</span>{/if}{#if f.incertain}<span class="pastille">à vérifier</span>{/if}
{/snippet}

{#if vide}<p class="text-sm text-muted-foreground">Aucun flux connu.</p>{/if}
{#if c.nourrit.length}
  <h3><span class="sens" aria-hidden="true">↘</span> Ce qui le nourrit</h3>
  <ul class="circ">{#each c.nourrit as e}<li>{@render nomDe(e.avec)} <span class="infos">{e.infos.join(' · ')}</span>{@render suite(e.f)}</li>{/each}</ul>
{/if}
{#if c.ecrit.length}
  <h3><span class="sens" aria-hidden="true">↗</span> Ce qu'il écrit ou fournit</h3>
  <ul class="circ">{#each c.ecrit as e}<li>{@render nomDe(e.avec)} <span class="infos">{e.infos.join(' · ')}</span>{@render suite(e.f)}</li>{/each}</ul>
{/if}
{#if c.echange.length}
  <h3><span class="sens" aria-hidden="true">⇄</span> Ce qu'il échange</h3>
  <ul class="circ">
    {#each c.echange as e}
      <li>{@render nomDe(e.avec)}
        <span class="infos"><span class="text-muted-foreground">reçoit</span> {e.recoit.join(' · ')}</span>
        <span class="infos"><span class="text-muted-foreground">envoie</span> {e.envoie.join(' · ')}</span>{@render suite(e.f)}</li>
    {/each}
  </ul>
{/if}
{#if c.autres.length}
  <h3>Accès, connexion, mises à jour</h3>
  <ul class="circ">{#each c.autres as e}<li>{@render nomDe(e.avec)} <span class="infos">{e.sens === 'vers' ? 'vers lui : ' : 'depuis lui : '}{e.f.infos.join(' · ')}</span>{@render suite(e.f)}</li>{/each}</ul>
{/if}

<style>
  h3 { display: flex; align-items: center; gap: 0.4rem; margin: 1rem 0 0.35rem; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted-foreground); font-weight: 600; }
  .sens { color: var(--app); font-size: 1rem; text-transform: none; }
  .circ { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.55rem; font-size: 0.9rem; }
  .circ li { display: grid; gap: 0.1rem; padding-left: 0.7rem; border-left: 2px solid var(--border); }
  .infos { color: #d8d0c4; overflow-wrap: anywhere; }
  .moyen { font-size: 0.78rem; overflow-wrap: anywhere; color: var(--muted-foreground); }
  .lien { border: 0; background: none; padding: 0; color: var(--app); cursor: pointer; text-align: left; font: inherit; font-weight: 600; justify-self: start; min-height: 1.75rem; }
  .pastille { justify-self: start; font-size: 0.72rem; border: 1px solid var(--border); border-radius: 999px; padding: 0 0.5rem; color: var(--muted-foreground); }
</style>
