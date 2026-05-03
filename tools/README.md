# Email Finder — Fast Growth Advisor

Script standalone qui genere et verifie les adresses email professionnelles a partir d'un fichier Excel de contacts.

## Principe de fonctionnement

Le script suit un pipeline en 3 etapes :

```
Excel → Resolution domaine → Generation emails → Verification SMTP → CSV
```

### 1. Resolution du domaine

Pour chaque contact, le script determine le domaine email de l'entreprise :

- **Si une colonne `site_web` est renseignee** : extraction du domaine depuis l'URL (ex: `https://www.ovh.com` → `ovh.com`). Verification que le domaine a des enregistrements MX (= peut recevoir des emails).
- **Sinon** : deduction automatique depuis le nom de la societe. Le script normalise le nom (suppression des formes juridiques SAS/SARL/Ltd, accents, espaces) et teste les extensions `.fr`, `.com`, `.io`, `.eu`, `.net`, `.co` jusqu'a trouver un domaine avec des MX valides.

Exemple : `Mistral AI` → teste `mistralai.fr` (MX trouve) → utilise `mistralai.fr`.

### 2. Generation des emails

Pour chaque contact, 8 patterns sont generes :

| Pattern | Exemple (Jean Dupont) |
|---|---|
| `prenom.nom` | jean.dupont@domain.com |
| `p.nom` | j.dupont@domain.com |
| `pnom` | jdupont@domain.com |
| `prenom` | jean@domain.com |
| `nom.prenom` | dupont.jean@domain.com |
| `nom` | dupont@domain.com |
| `prenomnom` | jeandupont@domain.com |
| `nomp` | dupontj@domain.com |

Les noms sont normalises : accents supprimes, minuscules, caracteres speciaux retires (`François Lefèvre` → `francois.lefevre`).

### 3. Verification SMTP

Chaque email genere est verifie en 3 niveaux :

1. **MX Lookup** — Le domaine a-t-il des serveurs mail ? (DNS MX record)
2. **Detection catch-all** — Le serveur accepte-t-il n'importe quelle adresse ? (test avec une adresse fictive)
3. **SMTP RCPT TO** — Connexion au serveur mail, envoi d'un `RCPT TO:` pour verifier si l'adresse existe reellement

**Statuts retournes :**

| Statut | Signification |
|---|---|
| `valide` | Le serveur accepte l'adresse (reponse 250) |
| `invalide` | Le serveur rejette l'adresse (reponse 550/553) |
| `catch_all` | Le domaine accepte toutes les adresses — impossible de verifier unitairement |
| `inconnu` | Timeout, greylisting, ou serveur non cooperatif |
| `domaine_introuvable` | Aucun domaine trouve pour cette societe |
| `pas_de_mx` | Le domaine existe mais n'a pas de serveur mail |
| `erreur` | Erreur de connexion au serveur |

**Protections anti-blocage :**
- Delai de 1.5s entre chaque verification SMTP
- Maximum 2 serveurs MX testes par domaine
- Abandon automatique apres 3 echecs consecutifs sur un meme domaine
- Timeout de 10s par connexion

## Installation

```bash
pip install openpyxl dnspython
```

## Utilisation

```bash
# Sortie par defaut : contacts_emails.csv
python3 tools/email_finder.py contacts.xlsx

# Sortie personnalisee
python3 tools/email_finder.py contacts.xlsx resultats.csv
```

## Format du fichier Excel

Le fichier doit contenir une ligne d'en-tete. La detection des colonnes est automatique et insensible a la casse.

**Colonnes obligatoires :**

| Champ | Noms acceptes |
|---|---|
| Nom | `nom`, `last_name`, `family_name`, `name` |
| Prenom | `prenom`, `prénom`, `first_name`, `given_name` |
| Societe | `societe`, `société`, `company`, `entreprise`, `organisation` |

**Colonnes optionnelles :**

| Champ | Noms acceptes |
|---|---|
| Site web | `site_web`, `site web`, `website`, `url`, `site` |
| LinkedIn | `linkedin`, `linkedin_url`, `profil_linkedin` |

## Format du CSV de sortie

Separateur : `;` (compatible Excel FR). Encodage : UTF-8 BOM.

| Colonne | Description |
|---|---|
| `prenom` | Prenom original |
| `nom` | Nom original |
| `societe` | Nom de la societe |
| `domaine` | Domaine email resolu |
| `email` | Adresse email generee |
| `pattern` | Pattern utilise |
| `mx_valide` | Le domaine a des MX (`oui`/`non`) |
| `smtp_statut` | Resultat de la verification |
| `linkedin` | URL LinkedIn (reprise de l'Excel) |

## Exemple

```
$ python3 tools/email_finder.py prospects.xlsx

==================================================
EMAIL FINDER — Fast Growth Advisor
==================================================
  Input  : prospects.xlsx
  Output : prospects_emails.csv

[1/3] Lecture du fichier Excel...
       42 contacts trouves

[2/3] Generation et verification des emails...
  [1/42] Jean Dupont @ ovh.com — 8 variantes
  [2/42] Sophie Martin @ doctolib.fr — 8 variantes
  ...

[3/3] Export CSV...

==================================================
RESUME
==================================================
  Contacts traites   : 42
  Emails generes     : 336
  Valides (SMTP 250) : 28
  Invalides          : 245
  Catch-all          : 48
  Inconnus           : 15
  Sans domaine       : 0
==================================================
```

## Limites

- **Catch-all** : certains domaines (souvent les grandes entreprises) acceptent toutes les adresses. Le script le detecte mais ne peut pas verifier unitairement.
- **Greylisting** : certains serveurs rejettent temporairement la premiere connexion. Ces emails apparaissent comme `inconnu`.
- **Pas de scraping LinkedIn** : le profil LinkedIn est conserve dans le CSV mais n'est pas utilise pour extraire le site web de l'entreprise.
- **Noms composes** : `Jean-Pierre` est normalise en `jeanpierre`. Les tirets sont supprimes.
