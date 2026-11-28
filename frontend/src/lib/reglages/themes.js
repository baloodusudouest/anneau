// 0.19 : les réglages de l'Anneau en cinq thèmes (choix de Julien du 26/11/2026 : « unifier les réglages »).
// Avant : quatre pages qui se renvoyaient l'une à l'autre (Réglages, Variables, Sauvegardes, Carte).
// Ce fichier ne lit rien : il dit quels thèmes existent, où mènent les anciennes adresses, et résume l'état de chaque
// thème pour l'accueil (`resumer`, fonction pure, à partir de ce que l'écran a déjà lu).

export const THEMES = [
  { id: 'services', nom: 'Services', icone: 'services', dit: 'Le fichier des tuiles, les applis en veille, les versions, le bac à sable.' },
  { id: 'stack', nom: 'Stack et variables', icone: 'stack', dit: 'homelab.yml, la clé de chiffrement, les exports chiffrés.' },
  { id: 'sauvegardes', nom: 'Sauvegardes', icone: 'sauvegardes', dit: 'La collecte de nuit, ce qui a changé, restaurer.' },
  { id: 'connexions', nom: 'Connexions', icone: 'connexions', dit: 'Portainer, Watchtower, GitHub, Home Assistant.' },
  { id: 'maison', nom: 'Maison', icone: 'maison', dit: 'La carte, les disques, les dernières pannes.' },
]
export const theme = (id) => THEMES.find((t) => t.id === id) || null

// Anciennes adresses (favoris, liens « À traiter », lien https d'avant) → le bon thème, la bonne section.
export const REDIRECTIONS = {
  '#/variables': '#/reglages/stack',
  '#/sauvegardes': '#/reglages/sauvegardes/liste',
  '#/carte': '#/reglages/maison',
}

/** Lit l'adresse : { page: 'anneau' | 'reglages', theme, section } (theme et section vides si absents). */
export function lireAdresse(hash) {
  const h = REDIRECTIONS[hash] || hash || ''
  const m = h.match(/^#\/reglages(?:\/([a-z]+))?(?:\/([a-z-]+))?\/?$/)
  if (!m) return { page: 'anneau', theme: '', section: '', adresse: h }
  const t = theme(m[1] || '') ? m[1] : ''
  return { page: 'reglages', theme: t, section: t ? m[2] || '' : '', adresse: t ? `#/reglages/${t}${m[2] ? '/' + m[2] : ''}` : '#/reglages' }
}

// Niveaux de signal, comme sur l'anneau : panne (rouge lave), action (bleu : quelque chose à faire),
// traiter (or : à traiter quand tu veux). Une pastille porte toujours un texte : jamais la couleur seule.
const ORDRE = { panne: 3, action: 2, traiter: 1 }
const pire = (...s) => s.filter(Boolean).sort((a, b) => ORDRE[b.niveau] - ORDRE[a.niveau])[0] || null
const pluriel = (n, un, plusieurs) => `${n} ${n > 1 ? plusieurs : un}`
const jour = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : '')

/** Âge en jours d'un export « AAAA-MM-JJ-….age » (null si illisible). */
export function ageExport(nom, maintenant = Date.now()) {
  const d = new Date(String(nom || '').slice(0, 10) + 'T12:00:00')
  return Number.isNaN(d.getTime()) ? null : (maintenant - d.getTime()) / 86400000
}

/**
 * Résumé de chaque thème pour l'accueil : { chiffre, unite, phrase, signal: { niveau, texte } | null }.
 * Chaque entrée de `lu` peut manquer (lecture ratée) : le thème dit alors « — » plutôt que d'inventer.
 *   etat (/api/etat), sauvegardes (/api/sauvegardes), stack (/api/stack), exports (liste), cle (clé publique),
 *   connexions (/api/maison/services), carte (/api/carte), https (/api/https)
 */
export function resumer(lu = {}, maintenant = Date.now()) {
  const { etat, sauvegardes, stack, exports, cle, connexions, carte, https } = lu
  const sortie = {}

  // ---- Services
  if (etat) {
    const tuiles = (etat.familles || []).flatMap((f) => f.services || [])
    const ecartees = etat.fraicheur?.erreurs?.length || 0
    const retard = tuiles.filter((s) => s.a_jour === false).length
    sortie.services = {
      chiffre: tuiles.length, unite: tuiles.length > 1 ? 'services' : 'service',
      phrase: etat.fraicheur?.exemple ? 'Exemple inventé : importe ton fichier.' : `Rangés en ${pluriel((etat.familles || []).length, 'famille', 'familles')}.`,
      signal: pire(
        ecartees && { niveau: 'panne', texte: pluriel(ecartees, 'ligne écartée', 'lignes écartées') },
        etat.fraicheur?.exemple && { niveau: 'traiter', texte: 'Fichier absent' },
        retard && { niveau: 'action', texte: pluriel(retard, 'version à installer', 'versions à installer') }),
    }
  } else sortie.services = vide()

  // ---- Stack et variables
  if (stack) {
    const dernier = exports?.[0]?.nom
    const age = dernier ? ageExport(dernier, maintenant) : null
    sortie.stack = {
      chiffre: stack.present ? stack.variables.length : '—', unite: stack.present ? 'variables' : '',
      phrase: stack.present ? `Lues dans homelab.yml (${pluriel(stack.services.length, 'service', 'services')}).` : 'homelab.yml pas encore importé.',
      signal: pire(
        !stack.present && { niveau: 'traiter', texte: 'homelab.yml à importer' },
        https && !https.https && https.garde && { niveau: 'action', texte: 'https requis pour chiffrer' },
        cle && !dernier && { niveau: 'traiter', texte: 'Aucun export chiffré' },
        age != null && age > 30 && { niveau: 'traiter', texte: 'Export de plus de 30 jours' }),
    }
  } else sortie.stack = vide()

  // ---- Sauvegardes
  if (sauvegardes) {
    const d = sauvegardes.derniere
    const ratees = d ? Object.keys(d.ratees || {}).length : 0
    sortie.sauvegardes = {
      chiffre: d ? d.applis.length : '—', unite: !d ? '' : d.applis.length <= 1 ? 'appli lue' : 'applis lues',
      phrase: d ? `Dernière collecte le ${jour(d.le)}, ${d.automatique ? 'de nuit' : 'à la demande'}.` : `Première collecte à ${sauvegardes.heure}.`,
      signal: pire(
        d?.erreur && { niveau: 'panne', texte: 'Fichier non écrit' },
        !d && { niveau: 'traiter', texte: 'Aucune collecte' },
        ratees && { niveau: 'traiter', texte: pluriel(ratees, 'appli non lue', 'applis non lues') }),
    }
  } else sortie.sauvegardes = vide()

  // ---- Connexions (Home Assistant compris)
  if (connexions || etat) {
    const fiches = connexions?.services || []
    const reglees = fiches.filter((f) => f.etat !== 'pas_relie')
    const muettes = fiches.filter((f) => f.etat === 'ne_repond_pas')
    const haAttendu = !!etat?.fraicheur?.ha_attendu
    const haMuet = haAttendu && !etat.fraicheur.ha_recu_le
    sortie.connexions = {
      chiffre: connexions ? `${reglees.length}/${fiches.length}` : '—', unite: connexions ? 'reliées' : '',
      phrase: haAttendu ? (etat.fraicheur.ha_recu_le ? 'Home Assistant envoie bien l\'état des machines.' : 'Home Assistant n\'a rien envoyé depuis le démarrage.')
        : 'Home Assistant n\'envoie pas encore l\'état des machines.',
      signal: pire(
        muettes.length && { niveau: 'panne', texte: muettes.length === 1 ? `${muettes[0].nom} ne répond pas` : `${muettes.length} ne répondent pas` },
        haMuet && { niveau: 'panne', texte: 'Home Assistant muet' }),
    }
  } else sortie.connexions = vide()

  // ---- Maison
  if (etat || carte) {
    const vols = (etat?.volumes || []).filter((v) => v.pourcentage != null)
    const plein = vols.sort((a, b) => b.pourcentage - a.pourcentage)[0]
    const pleins = (etat?.volumes || []).filter((v) => v.etat === 'panne').length
    sortie.maison = {
      chiffre: plein ? String(Math.round(plein.pourcentage * 10) / 10).replace('.', ',') : '—', unite: plein ? '% plein' : '',
      phrase: plein ? `${plein.nom}${plein.machine ? ' sur ' + plein.machine : ''}, le volume le plus plein.` : 'Aucun volume reçu de Home Assistant.',
      signal: pire(
        pleins && { niveau: 'panne', texte: pluriel(pleins, 'volume plein', 'volumes pleins') },
        carte?.etat?.erreur && { niveau: 'traiter', texte: 'Carte pas relue' }),
    }
  } else sortie.maison = vide()

  return sortie
}

function vide() {
  return { chiffre: '—', unite: '', phrase: 'Pas lu : rouvre la page.', signal: null }
}
