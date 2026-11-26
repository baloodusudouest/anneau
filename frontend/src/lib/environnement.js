// 0.10 (repris d'Atlas) : lecture d'un fichier d'environnement « NOM=valeur » (l'export de Portainer, Advanced mode).
// Les valeurs ne vivent que dans la mémoire de la page : ni mémoire locale, ni envoi. « Oublier » ou quitter la page les efface.

// Même règle qu'Atlas : un nom qui dit mot de passe, secret, jeton, clé, code, hash ou identifiant de compte est masqué.
const SENSIBLE = /PASSWORD|PASSWD|SECRET|TOKEN|JETON|(?:^|_)KEY(?:_|$)|(?:^|_)CLE(?:_|$)|ENCRYPTION|PRIVATE|HASH|(?:^|_)CODE(?:_|$)|CLIENT_ID|API_ID|ICLOUD_USER|(?:^|_)EMAIL(?:_|$)/

export const sensible = (nom) => SENSIBLE.test(nom)

// « NOM=valeur », une par ligne ; lignes vides et commentaires ignorés ; « export » et guillemets retirés.
export function comprendre(texte) {
  const valeurs = {}
  let ecartees = 0
  for (const brute of String(texte || '').replace(/^﻿/, '').split(/\r?\n/)) {
    const ligne = brute.trim()
    if (!ligne || ligne.startsWith('#')) continue
    const m = ligne.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/)
    if (!m) { ecartees++; continue }
    let v = m[2]
    const g = v.match(/^(["'])(.*)\1\s*(?:#.*)?$/)
    if (g) v = g[2]
    else v = v.replace(/\s+#.*$/, '').trim()
    valeurs[m[1]] = v
  }
  return { valeurs, ecartees }
}

// Le texte à recoller dans Portainer (Advanced mode) : une ligne NOM=valeur par variable de la stack.
// Une variable à remplir absente reste « NOM= » ; une facultative absente n'est pas écrite (son défaut est gardé) ;
// une variable que la stack n'utilise plus est laissée de côté. Sans liste de la stack : toutes les valeurs, triées.
export function pourPortainer(valeurs, variables) {
  const lignes = []
  let vides = 0
  if (!variables?.length) {
    for (const nom of Object.keys(valeurs).sort()) lignes.push(`${nom}=${valeurs[nom]}`)
    return { texte: lignes.join('\n') + (lignes.length ? '\n' : ''), n: lignes.length, vides: 0 }
  }
  for (const v of variables) {
    const a = Object.prototype.hasOwnProperty.call(valeurs, v.nom)
    if (a) { lignes.push(`${v.nom}=${valeurs[v.nom]}`); if (valeurs[v.nom] === '' && v.defaut === null) vides++ }
    else if (v.defaut === null) { lignes.push(`${v.nom}=`); vides++ }
  }
  return { texte: lignes.join('\n') + (lignes.length ? '\n' : ''), n: lignes.length, vides }
}

// Le lien qui ouvre la note d'une variable dans Obsidian.
export const lienNote = (coffre, nom) =>
  `obsidian://open?vault=${encodeURIComponent(coffre || 'Maison')}&file=${encodeURIComponent(`3 Infrastructure et stack/Stack/Variables/Variable — ${nom}`)}`

// 0.20 : retire les lignes de bloc Markdown (```yaml, ```) d'un homelab collé depuis la note du coffre
// (le serveur refuse le balisage Markdown). Rien d'autre n'est touché.
export function sansBlocMarkdown(texte) {
  return String(texte || '').split(/\r?\n/).filter((l) => !/^\s*```[\w-]*\s*$/.test(l)).join('\n')
}

// 0.20 : le homelab avec ses valeurs. Mêmes règles que Docker Compose, dans la page seulement :
//   ${VAR}          → valeur ; absente → laissée telle quelle (« non remplie »)
//   ${VAR:-défaut}  → valeur si présente et non vide, sinon le défaut
//   ${VAR-défaut}   → valeur si présente (même vide), sinon le défaut
//   $$              → laissé tel quel (échappement de Compose)
// Les commentaires ne sont jamais touchés (ligne qui commence par #, ou partie après « # » hors guillemets,
// précédée d'un espace) : aucun secret n'est recopié dans un commentaire.
// Rend { texte, remplacees: [noms], manquantes: [noms] } (noms uniques, dans l'ordre d'apparition).
const REF = /\$\$|\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:?-)([^}]*))?\}/g

function coupeCommentaire(ligne) {
  if (/^\s*#/.test(ligne)) return [ligne.indexOf("#"), ligne.length]
  let simple = false, double = false
  for (let i = 0; i < ligne.length; i++) {
    const c = ligne[i]
    if (c === "'" && !double) simple = !simple
    else if (c === '"' && !simple) double = !double
    else if (c === '#' && !simple && !double && (i === 0 || /\s/.test(ligne[i - 1]))) return [i, ligne.length]
  }
  return [ligne.length, ligne.length]
}

export function resoudre(texte, valeurs) {
  const a = (n) => valeurs && Object.prototype.hasOwnProperty.call(valeurs, n)
  const remplacees = new Set(), manquantes = new Set()
  const lignes = String(texte || '').split('\n').map((ligne) => {
    const [fin] = coupeCommentaire(ligne)
    const code = ligne.slice(0, fin).replace(REF, (tout, nom, sorte, defaut) => {
      if (!nom) return tout                                   // $$
      if (sorte === ':-') {
        if (a(nom) && valeurs[nom] !== '') { remplacees.add(nom); return valeurs[nom] }
        return defaut
      }
      if (sorte === '-') {
        if (a(nom)) { remplacees.add(nom); return valeurs[nom] }
        return defaut
      }
      if (a(nom)) { remplacees.add(nom); return valeurs[nom] }
      manquantes.add(nom)
      return tout
    })
    return code + ligne.slice(fin)
  })
  return { texte: lignes.join('\n'), remplacees: [...remplacees], manquantes: [...manquantes] }
}
