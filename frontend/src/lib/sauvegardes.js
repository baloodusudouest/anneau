// 0.10 (repris d'Atlas 1.10) : lecture des sauvegardes des réglages (contrat 1) et différences d'une sauvegarde à l'autre.

export function normaliserRatees(r) {
  if (Array.isArray(r)) return Object.fromEntries(r.map((x) => (typeof x === 'string' ? [x, ''] : [String(x?.appli ?? x?.id ?? '?'), String(x?.raison ?? '')])))
  if (r && typeof r === 'object') return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v)]))
  return {}
}

// Fichier de l'Anneau : {"contrat":1,"le","applis":{id:{appli,version,le,reglages}},"ratees":{}}.
export function normaliser(j, id = '') {
  if (!j || typeof j !== 'object' || Array.isArray(j)) throw new Error('Sauvegarde illisible.')
  const applis = {}
  for (const [k, a] of Object.entries(j.applis || {})) {
    if (!a || typeof a !== 'object') continue
    applis[k] = {
      version: a.version == null ? '' : String(a.version), le: String(a.le ?? ''),
      reglages: a.reglages && typeof a.reglages === 'object' && !Array.isArray(a.reglages) ? a.reglages : {},
    }
  }
  return {
    id, le: String(j.le ?? ''), applis, ratees: normaliserRatees(j.ratees),
    avertissement: j.contrat !== undefined && j.contrat !== 1 ? `Contrat de sauvegarde ${j.contrat} : l'affichage peut être incomplet.` : '',
  }
}

const egal = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// Réglages ajoutés, retirés, changés ; changement de version. Sans précédente : « nouvelle ».
export function differences(actuelle, precedente) {
  if (!precedente) return { nouvelle: true, version: null, lignes: [] }
  const lignes = []
  const a = actuelle?.reglages || {}, p = precedente.reglages || {}
  for (const k of [...new Set([...Object.keys(p), ...Object.keys(a)])].sort()) {
    if (!(k in p)) lignes.push({ cle: k, sorte: 'ajoute', apres: a[k] })
    else if (!(k in a)) lignes.push({ cle: k, sorte: 'retire', avant: p[k] })
    else if (!egal(a[k], p[k])) lignes.push({ cle: k, sorte: 'change', avant: p[k], apres: a[k] })
  }
  const version = (actuelle?.version || '') !== (precedente.version || '') ? { avant: precedente.version, apres: actuelle?.version } : null
  return { nouvelle: false, version, lignes }
}

// « 2026-11-16 » ou « 2026-11-16-143000-manuelle » → libellé lisible.
export function libelle(id) {
  const m = String(id).match(/^(\d{4})-(\d{2})-(\d{2})(?:-(\d{2})(\d{2})\d{2}(?:-\d+)?-manuelle)?$/)
  if (!m) return id
  const jour = new Date(`${m[1]}-${m[2]}-${m[3]}T12:00:00`).toLocaleDateString('fr-FR', { dateStyle: 'long' })
  return m[4] ? `${jour}, ${m[4]} h ${m[5]} (à la demande)` : jour
}
