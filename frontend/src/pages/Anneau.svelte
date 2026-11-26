<script>
  // L'écran de l'Anneau. Deux vues :
  //  - l'anneau des familles, avec ce qui est en panne et ce qui est à faire ;
  //  - la vue réduite, quand un service est ouvert : l'anneau d'or en haut à gauche (retour),
  //    une colonne d'icônes (une par famille ; en ligne sur téléphone), les services de la famille en pastilles, et le service.
  //    Le cadre laisse passer l'appareil photo (numérisation), le plein écran et la copie.
  // 0.12 : une tuile « à surveiller » (orange braise) porte sa phrase écrite (tâche de fond en retard, copie vieille) ;
  //    sa fiche (« État ») détaille les tâches, la dernière copie, la version du socle, avec le bouton « Vu ».
  //    Bandeau orange en haut si la veille de l'Anneau ne tourne plus depuis 10 min.
  // 0.13 : la fiche dit aussi la version en service et la dernière publiée, en mots (jamais d'orange pour un retard).
  // 0.16 : la fiche d'une appli maison montre aussi ses fiches « Connexion » (lues à l'ouverture, Vérifier relayé).
  // 0.17 : une tuile marquée « conteneur: » s'allume, s'éteint et se met à jour depuis sa fiche (Portainer) : éteinte, elle
  //    est grise et « Ouvrir » laisse la place à « Allumer » ; affichée dans le cadre, le bouton « État » mène aux boutons.
  //    Pendant un ordre, la phrase est écrite sur la tuile et l'écran se relit toutes les 2,5 s.
  // 0.18 : « À faire quand tu veux » montre aussi les applis de la stack à mettre à jour (une ligne repliée, un bouton par
  //    appli : MisesAJour.svelte) ; pendant une mise à jour, l'écran se relit toutes les 2,5 s.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { duree, secondes } from '$lib/temps.js'
  import Cercle from '$lib/Cercle.svelte'
  import Icone from '$lib/Icone.svelte'
  import FichesAppli from '$lib/FichesAppli.svelte'
  import Conteneur from '$lib/Conteneur.svelte'
  import Reveil from '$lib/Reveil.svelte'
  import MisesAJour from '$lib/MisesAJour.svelte'
  import { Button } from '$lib/components/ui/button/index.js'

  let { ondeconnecte, onreglages } = $props()
  let e = $state(null)               // l'état rendu par l'Anneau
  let erreur = $state('')
  let ouverte = $state(null)         // clé de la famille dépliée
  let service = $state(null)         // { famille, cle } du service ouvert (vue réduite)
  let etroit = $state(false)
  let tic = $state(Date.now())       // pour que « il y a 40 s » avance tout seul
  let etatOuvert = $state(false)     // 0.12 : la fiche « État » du service ouvert (à la place du cadre)

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
  // 0.17 : un ordre en cours chez Portainer : relire toutes les 2,5 s jusqu'à sa fin ; 0.19 : un réveil en cours aussi
  const ordreEnCours = $derived((e?.familles || []).some((f) => f.services.some((s) => s.conteneur?.ordre?.etat === 'en_cours' || s.reveil?.ordre?.etat === 'attente')) || !!e?.majs?.en_cours)
  $effect(() => {
    if (!ordreEnCours) return
    const t = setInterval(lire, 2500)
    return () => clearInterval(t)
  })

  const familles = $derived(e?.familles || [])
  const pannes = $derived(e?.pannes || [])
  const aFaire = $derived(e?.a_faire || [])
  const majs = $derived(e?.majs?.actif && (e.majs.nombre || e.majs.lignes.some((x) => x.ordre)) ? e.majs : null)   // 0.18
  const nbFaire = $derived(aFaire.length + (majs ? 1 : 0))
  const aTraiter = $derived(e?.a_traiter || [])   // 0.8 : « Sauvegarde ratée » (rien vers Home Assistant)
  const surveiller = $derived(e?.surveiller || [])  // 0.12 : tuiles orange (jamais comptées en panne)
  // 0.12 : la veille de l'Anneau est-elle arrêtée ? Le serveur le dit ; si l'API ne répond plus, le navigateur le calcule
  // à partir de la dernière boucle connue (pas avant : l'horloge du navigateur peut différer de celle du serveur).
  const veilleArretee = $derived(!!e?.veille && (e.veille.arretee || (!!erreur && tic - new Date(e.veille.derniere).getTime() > 600000)))
  const nbChoses = $derived(nbFaire + aTraiter.length)
  // l'état écrit sur l'anneau : la panne passe devant ce qui est à faire
  const etats = $derived(Object.fromEntries(familles.map((f) => [f.cle, f.etat === 'panne' ? 'panne' : aFaire.some((x) => x.famille === f.nom) ? 'faire' : f.etat === 'inconnu' ? 'inconnu' : ''])))
  const centre = $derived(!e ? null
    : pannes.length ? { rang: 'panne', grand: `${pannes.length} en panne`, petit: nbChoses ? `${nbChoses} chose${nbChoses > 1 ? 's' : ''} à faire` : '' }
    : { rang: nbFaire ? 'faire' : '', grand: 'Tout va bien', petit: nbChoses ? `${nbChoses} chose${nbChoses > 1 ? 's' : ''} à faire quand tu veux` : '' })
  const familleOuverte = $derived(familles.find((f) => f.cle === ouverte))
  const familleDuService = $derived(service ? familles.find((f) => f.cle === service.famille) : null)
  const leService = $derived(familleDuService?.services.find((s) => s.cle === service.cle) || null)

  const PHRASES = { ok: 'répond', panne: 'ne répond plus', eteint: 'est éteint (arrêt attendu)', inconnu: 'pas encore vérifié' }
  const phraseEtat = (s) => (s.etat === 'eteint' && s.conteneur?.statut === 'exited' ? 'est éteint (conteneur arrêté)' : PHRASES[s.etat])
  const ETATS_TACHE = { ok: 'ok', en_retard: 'en retard', bloquee: 'bloquée', jamais: 'pas encore passée', erreur: 'dernier essai en erreur' }
  const octets = (n) => (n == null ? '' : n < 1048576 ? `${Math.max(1, Math.round(n / 1024))} Ko` : `${(n / 1048576).toFixed(1).replace('.', ',')} Mo`)
  const periode = (n) => (!n ? '' : n % 86400 === 0 ? (n === 86400 ? 'chaque jour' : `tous les ${n / 86400} j`) : n % 3600 === 0 ? (n === 3600 ? 'chaque heure' : `toutes les ${n / 3600} h`) : n >= 60 ? `toutes les ${Math.round(n / 60)} min` : `toutes les ${n} s`)
  const aFiche = (s) => !!s && (!!s.sante || !!s.version_phrase || !!s.fiches || !!s.conteneur || !!s.besoin)   // 0.13 : santé ou version ; 0.16 : fiches ; 0.17 : conteneur ; 0.19 : besoin d'une machine à réveiller
  const phraseConteneur = (s) => s.conteneur?.phrase || ''
  const tourne = (s) => s.conteneur?.ordre?.etat === 'en_cours'
  const allumable = (s) => !!s.conteneur?.gerable && s.conteneur.statut === 'exited'
  const etatIcone = (s, ouvert = false) => (s.etat !== 'ok' ? s.etat : s.surveiller ? 'surveiller' : ouvert ? 'sombre' : '')
  const deplier = (cle) => (ouverte = ouverte === cle ? null : cle)
  // Les services déjà ouverts dans le cadre restent chargés quand on passe à un autre ou qu'on revient à l'anneau :
  // on les retrouve où on les avait laissés. Huit au plus, le plus ancien cède sa place.
  const GARDES = 8
  let gardes = $state([])            // [{ cle, adresse, nom, tour }], du plus ancien au plus récent
  const affichable = (s) => !!s && s.cadre && s.etat !== 'panne' && s.etat !== 'eteint'
  function garder(s, recharger = false) {
    if (!affichable(s)) return
    const deja = gardes.find((g) => g.cle === s.cle)
    const tour = (deja?.tour || 0) + (recharger || (deja && deja.adresse !== s.adresse) ? 1 : 0)
    gardes = [...gardes.filter((g) => g.cle !== s.cle), { cle: s.cle, adresse: s.adresse, nom: s.nom, tour }].slice(-GARDES)
  }
  // Toucher le service déjà affiché le recharge.
  const ouvrir = (f, s) => { garder(s, service?.cle === s.cle); service = { famille: f.cle, cle: s.cle }; ouverte = f.cle; etatOuvert = false }
  const fermer = () => { service = null; etatOuvert = false }
  // 0.12 : « Voir » d'une tuile orange ouvre le service sur sa fiche « État »
  function voirEtat(x) {
    const f = familles.find((g) => g.cle === x.famille_cle), s = f?.services.find((t) => t.cle === x.cle)
    if (f && s) { ouvrir(f, s); etatOuvert = true }
  }
  async function marquerVu(s) { try { await api.post('/api/sante/vu', { cle: s.cle }); await lire() } catch (x) { erreur = x.message } }
  // « Ouvrir » réutilise toujours la même fenêtre pour un service : les onglets ne se multiplient pas.
  // « Ouvrir » : toujours la même fenêtre par service (nom « anneau-<clé> »). 0.16.2 : si cet onglet existe déjà, le
  // navigateur le rechargeait au fond sans le montrer (« rien ne se passe ») : on le ferme et on en ouvre un neuf, qui
  // passe devant. Un onglet neuf s'ouvre vide (« about:blank », lisible) ; un onglet déjà chargé est d'un autre site
  // (lire son adresse lève une erreur) ou montre une page d'erreur.
  function dehors(s) {
    const nom = 'anneau-' + s.cle
    const w = window.open('', nom)
    if (!w) { window.open(s.adresse, '_blank', 'noopener'); return }   // fenêtre refusée : un onglet à part
    let neuf = false
    try { neuf = w.location.href === 'about:blank' } catch { neuf = false }
    if (neuf) { w.location.href = s.adresse; return }
    try { w.close() } catch { /* fermeture refusée : l'ouverture suivante le remplace quand même */ }
    window.open(s.adresse, nom)
  }
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
{:else}
  {#if veilleArretee}
    <p class="bandeau" role="alert">La veille de l'Anneau est arrêtée depuis {e.veille.arretee && !erreur ? secondes(e.veille.age) : duree(e.veille.derniere, tic)} : les états affichés ne sont plus vérifiés.</p>
  {/if}
  <!-- ───────────── Vue réduite ─────────────
       Elle reste en place, cachée, quand on revient à l'anneau : ses cadres gardent leur page. -->
  {#if leService || gardes.length}
  <div class="reduit" class:absente={!leService}>
    {#if leService}
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
      <!-- 0.5.1 : les réglages restent à portée quand un service est ouvert, tout en bas de la colonne -->
      <button type="button" class="reglages" title="Réglages" aria-label="Réglages" onclick={onreglages}>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M5 7.500h6M15 7.500h4M5 16.500h3M12 16.500h7" /><circle cx="13" cy="7.500" r="2" /><circle cx="10" cy="16.500" r="2" /></svg>
      </button>
    </nav>
    <div class="pastilles" class:avec-etat={aFiche(leService)} aria-label={'Services de ' + familleDuService.nom}>
      {#each familleDuService.services as s (s.cle)}
        <button type="button" aria-current={s.cle === service.cle ? 'true' : undefined} onclick={() => ouvrir(familleDuService, s)} {...milieu(s)}>
          <Icone icone={s.icone} etat={etatIcone(s, s.cle === service.cle)} />{s.nom}{#if phraseConteneur(s)}<span class="phrase-conteneur">{#if tourne(s)}<span class="tourne" aria-hidden="true"></span>{/if}{phraseConteneur(s)}</span>{/if}{#if s.surveiller}<span class="phrase-tuile">{s.phrase}</span>{:else if s.vu}<span class="vu" title="Vu : redevient orange au prochain changement">vu</span>{/if}{#if s.cle !== service.cle && gardes.some((g) => g.cle === s.cle)}<span class="garde" title="Resté ouvert"><span class="sr-only"> (resté ouvert)</span></span>{/if}</button>
      {/each}
      {#if aFiche(leService) || affichable(leService)}
        <span class="actions-service">
          <!-- 0.14 : un service affiché dans le cadre s'ouvre aussi en grand (sa propre fenêtre, toujours la même) -->
          {#if affichable(leService) && !etatOuvert}
            <button type="button" class="bouton-grand" title="Ouvrir en grand" aria-label="Ouvrir en grand" onclick={() => dehors(leService)}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7" /></svg>
            </button>
          {/if}
          {#if aFiche(leService)}
            <button type="button" class="bouton-etat" class:surveiller={leService.surveiller} aria-pressed={etatOuvert} onclick={() => (etatOuvert = !etatOuvert)}>État</button>
          {/if}
        </span>
      {/if}
    </div>
    {/if}
    <section class="contenu" aria-label={leService?.nom || 'Services ouverts'}>
      {#each gardes as g (g.cle + '#' + g.tour)}
        <iframe src={g.adresse} title={g.nom} class:absente={!(leService && g.cle === leService.cle && affichable(leService) && !etatOuvert)} allow="camera; fullscreen; clipboard-write"></iframe>
      {/each}
      {#if leService && etatOuvert && aFiche(leService)}
        {@const sa = leService.sante}
        <div class="fiche fiche-etat" aria-label={'État de ' + leService.nom}>
          <h1 class="plume">{leService.nom}</h1>
          {#if leService.version_phrase}<p class="version-tuile text-sm">{leService.version_phrase}</p>{/if}
          {#if leService.surveiller}
            <ul class="defauts">{#each leService.defauts as d (d.cle)}<li>{d.phrase}</li>{/each}</ul>
            <Button onclick={() => marquerVu(leService)}>Vu</Button>
            <p class="text-sm text-muted-foreground">« Vu » : la tuile redevient normale jusqu'au prochain changement.</p>
          {:else if leService.vu}
            <ul class="defauts vus">{#each leService.defauts as d (d.cle)}<li>{d.phrase}</li>{/each}</ul>
            <p class="text-sm text-muted-foreground">Vu : la tuile redeviendra orange si autre chose casse.</p>
          {/if}
          {#if leService.conteneur}
            {#key leService.cle}<Conteneur s={leService} onfait={lire} />{/key}
          {/if}
          <!-- 0.19 : réveiller la machine (tuile « reveil: true ») ou celle dont l'appli a besoin (« besoin: ») -->
          {#if leService.reveil}<Reveil cible={leService} onfait={lire} />{/if}
          {#if leService.besoin}<Reveil cible={leService.besoin} besoin appli={leService.nom} onfait={lire} />{/if}
          {#if leService.fiches}
            {#key leService.cle}<FichesAppli cle={leService.cle} nom={leService.nom} />{/key}
          {/if}
          {#if sa}
          <table class="taches">
            <caption class="etiquette">Tâches de fond</caption>
            <tbody>
              {#each sa.taches as t (t.nom)}
                <tr class:defaut={t.type === 'reguliere' && (t.etat === 'en_retard' || t.etat === 'bloquee')}>
                  <th scope="row">{t.nom}<small>{t.type === 'demande' ? 'à la demande' : periode(t.periode_s)}</small></th>
                  <td>{ETATS_TACHE[t.etat] || t.etat}
                    <small>{t.derniere_reussite ? 'réussie il y a ' + duree(t.derniere_reussite, tic) : 'pas encore réussie'}{t.derniere_erreur ? ' · dernière erreur il y a ' + duree(t.derniere_erreur, tic) : ''}</small>
                    {#if t.message}<small class="message">{t.message}</small>{/if}
                  </td>
                </tr>
              {:else}
                <tr><td colspan="2">Aucune tâche déclarée.</td></tr>
              {/each}
            </tbody>
          </table>
          <p class="text-sm">Copie des bases :
            {#if !sa.copie_base}aucune base à copier{:else if !sa.copie_base.le}pas encore faite{:else}{sa.copie_base.ok ? 'faite' : 'ratée'} il y a {duree(sa.copie_base.le, tic)}{sa.copie_base.bases.length ? ' · ' + sa.copie_base.bases.join(', ') : ''}{sa.copie_base.taille ? ' · ' + octets(sa.copie_base.taille) : ''}{/if}
          </p>
          <p class="text-sm text-muted-foreground">Socle {sa.version_socle || 'inconnu'} · lu il y a {duree(sa.lu_le, tic)}</p>
          {/if}
        </div>
      {:else if leService && !affichable(leService)}
        <div class="fiche">
          <h1 class="plume" class:panne={leService.etat === 'panne'}>{leService.nom}</h1>
          {#if leService.version_phrase}<p class="version-tuile text-sm">{leService.version_phrase}</p>{/if}
          <p role="status">{leService.nom} {phraseEtat(leService)}{leService.depuis ? ` depuis ${duree(leService.depuis, tic)}` : ''}{leService.etat === 'ok' && leService.delai != null ? ` · réponse en ${leService.delai} ms` : ''}.</p>
          {#if leService.machine_en_panne}<p class="text-sm text-muted-foreground">{leService.machine} ne répond plus : c'est lui qui est en panne.</p>{/if}
          <!-- 0.17 : conteneur arrêté : « Allumer » et « Allumer et mettre à jour » à la place de « Ouvrir » -->
          {#if !allumable(leService)}<Button onclick={() => dehors(leService)}>Ouvrir {leService.nom}</Button>{/if}
          {#if leService.conteneur}{#key leService.cle}<Conteneur s={leService} onfait={lire} />{/key}{/if}
          {#if leService.reveil}<Reveil cible={leService} onfait={lire} />{/if}
          {#if leService.besoin}<Reveil cible={leService.besoin} besoin appli={leService.nom} onfait={lire} />{/if}
          {#if !allumable(leService)}<p class="text-sm text-muted-foreground">{leService.cadre ? (leService.etat === 'eteint' ? 'Éteint : rien à afficher ici.' : 'En panne : rien à afficher ici.') : `${leService.nom} s'ouvre à côté, toujours dans la même fenêtre : ${leService.hors_cadre}.`}</p>{/if}
        </div>
      {/if}
    </section>
  </div>
  {/if}
  {#if !leService}
  <!-- ───────────── L'anneau ───────────── -->
  <div class="accueil">
    <!-- 0.19 : raccourci vers Réglages › Maison (carte, disques, pannes closes), à côté de la roue -->
    <a class="roue maison" href="#/reglages/maison" aria-label="Maison : carte, disques et pannes" title="Maison">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 11.5 12 5l8 6.5"/><path d="M6.5 10v9h11v-9"/><path d="M10.5 19v-5h3v5"/></svg>
    </a>
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
              <button type="button" style:animation-delay="{i * 28}ms" class:surveiller={s.surveiller} class:avec-phrase={!!phraseConteneur(s)} onclick={() => ouvrir(familleOuverte, s)} {...milieu(s)}><Icone icone={s.icone} etat={etatIcone(s)} />{s.nom}{#if phraseConteneur(s)}<span class="phrase-conteneur">{#if tourne(s)}<span class="tourne" aria-hidden="true"></span>{/if}{phraseConteneur(s)}</span>{/if}{#if s.surveiller}<span class="phrase-tuile">{s.phrase}</span>{:else if s.vu}<span class="vu" title="Vu : redevient orange au prochain changement">vu</span>{/if}</button>
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
      {#if surveiller.length}
        <section class="rang surveiller" aria-label="À surveiller">
          <h2><span>À surveiller</span><span>{surveiller.length}</span></h2>
          <ul>
            {#each surveiller as x (x.cle)}
              <li>
                <span><b>{x.nom}</b> : {x.phrase}<small>{x.famille}</small></span>
                <button type="button" class="lien" onclick={() => voirEtat(x)} aria-label={'Voir : ' + x.nom}>Voir</button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
      {#if nbFaire}
        <section class="rang faire" aria-label="À faire quand tu veux">
          <h2><span>À faire quand tu veux</span><span>{nbFaire}</span></h2>
          <ul>
            {#each aFaire as x (x.cle)}<li><span>{x.phrase}{#if x.famille}<small>{x.famille}</small>{/if}</span></li>{/each}
            {#if majs}<MisesAJour m={majs} {tic} onfait={lire} />{/if}
          </ul>
        </section>
      {/if}
      {#if aTraiter.length}
        <section class="rang traiter" aria-label="À traiter">
          <h2><span>À traiter</span><span>{aTraiter.length}</span></h2>
          <ul>
            {#each aTraiter as x (x.cle)}
              <li>
                <span>{x.phrase}{#if x.detail}<small>{x.detail}</small>{/if}</span>
                <button type="button" class="lien" onclick={() => (location.hash = x.cle === 'export-variables' ? '#/reglages/stack/exports' : '#/reglages/sauvegardes')} aria-label={'Voir : ' + x.phrase}>Voir</button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
      {#if !pannes.length && !surveiller.length && !nbFaire && !aTraiter.length && e.fraicheur.sonde}
        <p class="text-sm text-muted-foreground">Rien à signaler. Touche une famille pour voir ses services.</p>
      {/if}
    </div>
  </div>
{/if}
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
  .roue.maison { right: calc(max(1rem, env(safe-area-inset-right)) + 3.25rem); }
  .frais { font-size: 0.8rem; color: var(--muted-foreground); text-align: center; }
  @media (min-width: 900px) { .frais { text-align: left; } }
  .avis { font-size: 0.85rem; border: 1px solid var(--border); border-radius: 0.9rem; padding: 0.6rem 0.9rem; color: var(--muted-foreground); }
  .rang { border: 1px solid var(--border); border-radius: 1rem; padding: 0.8rem 0.95rem; background: var(--card); }
  .rang h2 { display: flex; justify-content: space-between; margin: 0 0 0.55rem; font-size: 0.74rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }
  .rang.panne h2 { color: var(--lave); }
  .rang.faire h2 { color: var(--spectre); }
  .rang.surveiller { border-color: color-mix(in srgb, var(--braise) 50%, var(--border)); }
  .rang.surveiller h2 { color: var(--braise); }
  .rang.surveiller b { font-weight: 600; }
  .bandeau { position: sticky; top: 0; z-index: 5; margin: 0; padding: calc(0.55rem + env(safe-area-inset-top)) 1rem 0.55rem; text-align: center; font-size: 0.9rem;
             font-weight: 600; color: #1e1a16; background: var(--braise); }
  .phrase-tuile { font-size: 0.78rem; color: var(--braise); white-space: normal; text-align: left; }
  .pastilles.libres .phrase-tuile { flex-basis: 100%; }
  .pastilles.libres button.surveiller { flex-wrap: wrap; justify-content: center; max-width: 100%; padding-block: 0.35rem; border-color: color-mix(in srgb, var(--braise) 55%, var(--border)); }
  .pastilles button[aria-current='true'] .phrase-tuile { color: #6b3a00; }
  .phrase-conteneur { display: inline-flex; align-items: center; font-size: 0.78rem; color: var(--muted-foreground); white-space: nowrap; }
  .pastilles button[aria-current='true'] .phrase-conteneur { color: #3a2f1c; }
  .pastilles.libres button.avec-phrase { flex-wrap: wrap; justify-content: center; max-width: 100%; padding-block: 0.35rem; }
  .pastilles.libres .phrase-conteneur { flex-basis: 100%; justify-content: center; }
  .tourne { display: inline-block; flex: none; width: 0.7rem; height: 0.7rem; margin-right: 0.35rem; border-radius: 50%;
            border: 2px solid color-mix(in srgb, var(--spectre) 30%, transparent); border-top-color: var(--spectre); animation: tourne 0.9s linear infinite; }
  @keyframes tourne { to { transform: rotate(360deg); } }
  .vu { font-size: 0.7rem; color: var(--muted-foreground); border: 1px solid var(--border); border-radius: 9999px; padding: 0 0.35rem; }
  /* toujours visibles, même quand la rangée défile */
  .actions-service { margin-left: auto; position: sticky; right: 0; display: flex; gap: 0.4rem; flex: none;
                     background: var(--background); box-shadow: -0.6rem 0 0.6rem var(--background); }
  .bouton-grand { padding-inline: 0.7rem !important; }
  .bouton-etat.surveiller { color: var(--braise) !important; border-color: color-mix(in srgb, var(--braise) 60%, var(--border)) !important; }
  .bouton-etat[aria-pressed='true'] { color: #1e1a16 !important; background: var(--braise) !important; }
  .fiche-etat { justify-content: flex-start; overflow-y: auto; }
  .fiche-etat h1 { font-size: 2.6rem; }
  .defauts { margin: 0; padding: 0; list-style: none; color: var(--braise); font-weight: 600; }
  .defauts.vus { color: var(--muted-foreground); font-weight: 400; }
  .taches { width: 100%; max-width: 34rem; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
  .taches caption { text-align: left; padding-bottom: 0.3rem; }
  .taches th, .taches td { padding: 0.45rem 0.4rem; border-top: 1px solid var(--border); vertical-align: top; }
  .taches th { font-weight: 600; }
  .taches small { display: block; font-weight: 400; color: var(--muted-foreground); font-size: 0.8rem; }
  .taches small.message { color: var(--foreground); overflow-wrap: anywhere; }
  .taches tr.defaut td { color: var(--braise); }
  .rang.traiter { border-color: color-mix(in srgb, var(--app) 45%, var(--border)); }
  .rang.traiter h2 { color: var(--app); }
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
  /* 0.17 : position relative : le texte « (resté ouvert) » des lecteurs d'écran (sr-only, absolu) restait hors de la rangée
     qui défile et élargissait la page sur téléphone quand une tuile gardée était au-delà du bord */
  .pastilles button { position: relative; display: inline-flex; align-items: center; gap: 0.45rem; flex: none; min-height: 2.5rem; padding: 0 0.85rem; border-radius: 9999px; white-space: nowrap;
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
  .colonne .reglages { margin-top: auto; flex: none; color: var(--muted-foreground); }
  .colonne .reglages:hover { color: var(--foreground); }
  .contenu { grid-row: 2; grid-column: 2; min-height: 0; border: 1px solid var(--border); border-radius: 0.9rem; background: var(--card); overflow: hidden; }
  .absente { display: none !important; }
  .garde { width: 0.4rem; height: 0.4rem; margin-left: 0.1rem; border-radius: 50%; background: var(--app); }
  .contenu iframe { display: block; width: 100%; height: 100%; border: 0; background: var(--background); }
  /* Sur téléphone, le service prend toute la largeur : les familles passent en ligne à côté de l'anneau, les services
     dessous. À côté d'une colonne d'icônes, le cadre n'avait que les trois quarts de l'écran et les applis y débordaient. */
  @media (max-width: 899px) {
    .reduit { grid-template-columns: 3rem minmax(0, 1fr); grid-template-rows: auto auto minmax(0, 1fr); gap: 0.45rem 0.5rem;
              padding: calc(0.4rem + env(safe-area-inset-top)) max(0.35rem, env(safe-area-inset-right)) 0 max(0.35rem, env(safe-area-inset-left)); }
    .retour { max-width: 3rem; }
    .colonne { grid-row: 1; grid-column: 2; flex-direction: row; justify-content: space-between; overflow-x: auto; overflow-y: hidden; }
    .colonne button { flex: none; width: 2.75rem; height: 2.75rem; border-left: 0; border-bottom: 2px solid transparent; }
    .colonne button[aria-current='true'] { border-bottom-color: var(--app); }
    .colonne .reglages { margin-top: 0; }
    .reduit > .pastilles { grid-row: 2; grid-column: 1 / -1; }
    /* 0.17.3 : le cadre descend jusqu'au bord bas ; la barre d'onglets de l'appli (collée en bas, socle 0.12.1) se pose
       juste au-dessus de la barre d'accueil de l'iPhone, sans bande ni bordure dessous */
    .contenu { grid-row: 3; grid-column: 1 / -1; border-radius: 0.7rem 0.7rem 0 0; border-bottom: 0;
               padding-bottom: env(safe-area-inset-bottom); }
  }
  .fiche { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.8rem; padding: 1.5rem; text-align: center; }
  .fiche h1 { font-size: 3.4rem; margin: 0; }
  .fiche p { max-width: 44ch; margin: 0; }
  .fiche :global(.conteneur) { max-width: 30rem; }
  @media (prefers-reduced-motion: reduce) { .retour, .pastilles.libres button, .tourne { animation: none; } }
</style>
