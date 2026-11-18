<script>
  // La zone d'un quartier sur la carte (Photos, Proches…), derrière ses bulles.
  let { data } = $props()
</script>

<div class="quartier" class:estompe={data.estompe} style="width:{data.largeur}px;height:{data.hauteur}px">
  <span class="nom">{data.nom}</span>
</div>

<style>
  .quartier { box-sizing: border-box; border: 1px solid #3a342e; border-radius: 1.4rem; background: rgb(255 248 236 / 0.025); pointer-events: none; transition: opacity 0.2s; }
  .nom { position: absolute; top: 0.75rem; left: 1.1rem; font-size: 1.05rem; font-weight: 300; letter-spacing: 0.02em; color: #a89e91; text-transform: uppercase; }
  .estompe { opacity: 0.35; }
</style>
