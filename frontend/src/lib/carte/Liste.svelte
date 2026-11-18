<script>
  // Sur téléphone, la carte se lit en liste : machine › services, avec le voyant de chaque tuile ; toucher un service
  // montre d'où vient ce qu'il reçoit et où va ce qu'il fournit (même contenu que le panneau de la carte).
  import Circulation from './Circulation.svelte'
  import { VOYANTS, couleur, indexer, lienNote } from './modele.js'
  let { carte } = $props()
  const idx = $derived(indexer(carte))
  let ouvert = $state('')
  let enPanne = $state(false)
  const groupes = $derived(carte.machines.map((m) => ({
    ...m, services: carte.services.filter((s) => s.machine === m.id && (!enPanne || s.voyant === 'panne'))
      .sort((a, b) => a.nom.localeCompare(b.nom, 'fr')),
  })).filter((g) => g.services.length))
  function ouvrir(id) {
    ouvert = id
    setTimeout(() => document.getElementById('service-' + id)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 30)
  }
</script>

<div class="mb-3 flex flex-wrap gap-2">
  <button class="choix" aria-pressed={enPanne} onclick={() => (enPanne = !enPanne)}>Seulement en panne</button>
</div>
{#each groupes as g (g.id)}
  <section class="mb-4" aria-label={g.nom}>
    <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{g.nom}</h2>
    <ul class="grid gap-2">
      {#each g.services as s (s.id)}
        <li id={'service-' + s.id} class="rounded-xl border bg-card">
          <button class="ligne" aria-expanded={ouvert === s.id} onclick={() => (ouvert = ouvert === s.id ? '' : s.id)} style="--c:{couleur(s)}">
            <span class="voyant" style="background:{(VOYANTS[s.voyant] ?? VOYANTS.inconnu).couleur}" aria-label={(VOYANTS[s.voyant] ?? VOYANTS.inconnu).nom}></span>
            <span class="min-w-0 flex-1 text-left">
              <span class="block font-semibold break-words">{s.nom}</span>
              <span class="block text-xs text-muted-foreground">{(VOYANTS[s.voyant] ?? VOYANTS.inconnu).nom}{s.port ? ' · port ' + s.port : ''}{s.etat === 'pause' ? ' · en pause' : ''}</span>
            </span>
          </button>
          {#if ouvert === s.id}
            <div class="px-4 pb-4">
              <p class="text-sm">{s.role}</p>
              {#if lienNote(s)}<p class="mt-2 text-sm"><a class="underline underline-offset-4" href={lienNote(s)}>Sa note dans le coffre</a></p>{/if}
              <Circulation {carte} parId={idx.parId} id={s.id} {ouvrir} />
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/each}

<style>
  .ligne { display: flex; align-items: center; gap: 0.75rem; width: 100%; min-height: 3.25rem; padding: 0.6rem 1rem; background: none; border: 0;
    color: inherit; cursor: pointer; border-radius: 0.75rem; box-shadow: inset 4px 0 0 var(--c); }
  .voyant { width: 0.75rem; height: 0.75rem; border-radius: 999px; flex: none; border: 1px solid var(--border); }
  .choix { min-height: 2.5rem; padding: 0 0.9rem; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--muted-foreground); }
  .choix[aria-pressed='true'] { background: var(--secondary); color: var(--foreground); }
</style>
