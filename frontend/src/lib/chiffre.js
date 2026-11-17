// 0.10 (repris d'Atlas 1.10) : chiffrement age (X25519) du fichier d'environnement, tout dans le navigateur.
// Bibliothèque « age-encryption » de Filippo Valsorda, intégrée à l'interface au build (aucun appel réseau).
// La page n'autorise chiffrer et ouvrir qu'en contexte sûr (HTTPS) : voir sur() plus bas.
//
// Règle : la clé privée (AGE-SECRET-KEY-…) n'est JAMAIS écrite ailleurs que dans la mémoire de la page
// (ni localStorage, ni sessionStorage, ni IndexedDB, ni requête). Ce module ne garde rien : il reçoit
// les clés en argument et rend des résultats ; c'est l'écran qui les tient et les efface à « Oublier ».
import { Encrypter, Decrypter, armor, generateX25519Identity, identityToRecipient } from 'age-encryption'
// En http, le navigateur ne donne pas crypto.subtle. L'Anneau refuse alors chiffrer et ouvrir (sur()), mais la
// génération de paire et les tests peuvent tourner sans WebCrypto. La bibliothèque ne bascule d'elle-même sur sa version JavaScript (noble) que si
// X25519 manque dans WebCrypto, pas si WebCrypto entier manque : on lui dit de le faire. Même module que celui
// qu'importe la bibliothèque (chemin de fichier identique), son réglage interne n'est pas exporté par le paquet.
// Le hasard (crypto.getRandomValues) reste celui du navigateur, disponible même en http.
import { forceWebCryptoOff } from '../../node_modules/age-encryption/dist/x25519.js'

if (!globalThis.crypto?.subtle) forceWebCryptoOff(true)

export const PREFIXE_PRIVEE = 'AGE-SECRET-KEY-1'
const RE_PUBLIQUE = /^age1[02-9ac-hj-np-z]{58}$/        // bech32, X25519 seulement (62 caractères)
const RE_PRIVEE = /^AGE-SECRET-KEY-1[02-9AC-HJ-NP-Z]{58}$/

const ILLISIBLE = 'Clé privée mal formée (somme de contrôle fausse) : vérifie qu\'elle est recopiée en entier, sans espace.'
const net = (t) => String(t || '').trim()
export const clePubliqueValide = (cle) => RE_PUBLIQUE.test(net(cle))
export const clePriveeValide = (cle) => RE_PRIVEE.test(net(cle).toUpperCase())

// Une paire neuve : { privee: 'AGE-SECRET-KEY-1…', publique: 'age1…' }.
export async function genererPaire() {
  const privee = await generateX25519Identity()
  const publique = await identityToRecipient(privee)
  return { privee, publique }
}

// La clé publique qui va avec une clé privée (pour vérifier qu'on a la bonne).
export async function publiqueDe(privee) {
  if (!clePriveeValide(privee)) throw new Error('Clé privée mal formée : elle commence par AGE-SECRET-KEY-1 et fait 74 caractères.')
  try { return await identityToRecipient(net(privee).toUpperCase()) }
  catch { throw new Error(ILLISIBLE) }
}

// Texte clair → texte armuré « -----BEGIN AGE ENCRYPTED FILE----- ».
export async function chiffrer(texte, publique) {
  const cle = net(publique)
  if (!clePubliqueValide(cle)) throw new Error('Clé publique mal formée : elle commence par age1 et fait 62 caractères.')
  const e = new Encrypter()
  e.addRecipient(cle)
  return armor.encode(await e.encrypt(String(texte)))
}

// Armuré (texte) ou binaire (Uint8Array / ArrayBuffer) → texte clair. Message clair si la clé ne va pas.
export async function dechiffrer(contenu, privee) {
  if (!clePriveeValide(privee)) throw new Error('Clé privée mal formée : elle commence par AGE-SECRET-KEY-1 et fait 74 caractères.')
  let octets
  if (typeof contenu === 'string') {
    const t = contenu.trim()
    if (!t.startsWith('-----BEGIN AGE ENCRYPTED FILE-----')) throw new Error('Ce n\'est pas un fichier chiffré age (texte « BEGIN AGE ENCRYPTED FILE » attendu).')
    try { octets = armor.decode(t) } catch { throw new Error('Fichier chiffré abîmé : l\'armure age ne se lit pas.') }
  } else {
    octets = contenu instanceof Uint8Array ? contenu : new Uint8Array(contenu)
    // Un .age armuré lu en binaire : on le repasse en texte
    const debut = new TextDecoder().decode(octets.slice(0, 40))
    if (debut.startsWith('-----BEGIN AGE')) return dechiffrer(new TextDecoder().decode(octets), privee)
  }
  const d = new Decrypter()
  try { d.addIdentity(net(privee).toUpperCase()) } catch { throw new Error(ILLISIBLE) }
  try { return await d.decrypt(octets, 'text') }
  catch (e) {
    const m = String(e?.message || e)
    if (/no identity matched/i.test(m)) throw new Error('Cette clé privée n\'ouvre pas ce fichier : il a été chiffré pour une autre clé.')
    throw new Error('Déchiffrement impossible : fichier abîmé ou qui n\'est pas un fichier age.')
  }
}

// Contexte sûr : HTTPS (ou localhost). Hors de lui, la page refuse chiffrer et ouvrir (décision du 17/11/2026) :
// une page servie en clair sur le réseau local pourrait être modifiée en route et lire ce qu'on y colle.
export const sur = () => typeof window !== 'undefined' && window.isSecureContext === true

// Empreinte lisible d'une clé publique, à comparer à la copie gardée dans le coffre : « age1abcd…wxyz1234 ».
export const empreinte = (cle) => { const c = net(cle); return c.length > 20 ? `${c.slice(0, 8)}…${c.slice(-8)}` : c }
