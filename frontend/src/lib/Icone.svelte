<script>
  // L'icône d'un service ou d'une famille : sa propre image si le fichier en donne l'adresse, sinon un pictogramme.
  import { estImage, trait } from '$lib/icones.js'
  let { icone = '', etat = '', taille = 18 } = $props()
  let casse = $state(false)
</script>

{#if estImage(icone) && !casse}
  <img src={icone} alt="" width={taille} height={taille} class="image" class:terne={etat === 'panne' || etat === 'inconnu'} onerror={() => (casse = true)} />
{:else}
  <svg viewBox="0 0 24 24" width={taille} height={taille} class="trait {etat}" aria-hidden="true">{@html trait(icone)}</svg>
{/if}

<style>
  .image { flex: none; border-radius: 22%; }
  .image.terne { opacity: 0.55; filter: grayscale(0.6); }
  .trait { flex: none; fill: none; stroke: var(--app); stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .trait.panne { stroke: var(--lave); }
  .trait.faire { stroke: var(--spectre); }
  .trait.inconnu, .trait.eteint { stroke: var(--or-sourd); }
  .trait.sourd { stroke: var(--or-sourd); }
  .trait.vif { stroke: var(--or-vif); }
  .trait.sombre { stroke: #1e1a16; }
</style>
