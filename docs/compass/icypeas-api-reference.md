# Icypeas API — référence (capturée en live, 2026-07-02)

Doc officielle : https://api-doc.icypeas.com/

## Auth
- Header `Authorization: <API_KEY>` (la clé brute, **pas** de `Bearer`, pas de HMAC).
- Header `Content-Type: application/json`.
- Base : `https://app.icypeas.com/api/`
- Rate limit : ~30 req/min.

## Email finder (async)
`POST /api/email-search`
```json
{"firstname":"John","lastname":"Doe","domainOrCompany":"icypeas.com"}
```
→ `{"success":true,"item":{"_id":"<id>","status":"NONE"}}`

## Email verifier (async)
`POST /api/email-verification`
```json
{"email":"john@icypeas.com"}
```
→ `{"success":true,"item":{"_id":"<id>","status":"NONE"}}`

## Lecture du résultat (polling)
`POST /api/bulk-single-searchs/read`
```json
{"id":"<id renvoyé par la soumission>"}
```
Réponse (finder ET verifier ont la MÊME structure) :
```json
{"success":true,"items":[{
  "results":{
    "firstname":"Herve","lastname":"Dhelin","fullname":"Herve Dhelin","li":"",
    "emails":[{"email":"herve@fast-growth.fr","certainty":"ultra_sure",
               "mxRecords":["ovh.net"],"mxProvider":"ovh"}],
    "phones":[],"saasServices":[]
  },
  "status":"DEBITED","_id":"<id>"
}],"total":1}
```
- Email trouvé : `items[0].results.emails[0].email`
- Certitude : `items[0].results.emails[0].certainty`
- LinkedIn : `items[0].results.li`
- Statut item : `items[0].status`
- Non trouvé : `emails: []`, status `NOT_FOUND`.

## Statuts item
- Non terminaux (continuer à poller) : `NONE`, `SCHEDULED`, `IN_PROGRESS`.
- Terminaux : `DEBITED`, `FOUND` (trouvé + débité) ; `NOT_FOUND`, `DEBITED_NOT_FOUND` ; `BAD_INPUT`, `INSUFFICIENT_FUNDS`, `ABORTED`.

## Certitudes (certainty)
- `ultra_sure` / `very_sure` : 99% (bounce < 1%) → `valid`.
- `probable` : 95% (bounce < 5%) → `valid` (déliverable, confiance moindre).
- `undeliverable` : n'existe pas → `invalid`.
- `not_found` : inconnu → `invalid`.
- (pas de `catch_all` explicite dans les certitudes Icypeas.)

## Find People (leads DB, SYNCHRONE) — intégré (IcypeasPeopleSource)
`POST /api/find-people`
```json
{"query":{"currentCompanyWebsite":{"include":["www.upsun.com"]},
          "currentJobTitle":{"include":["CTO"]}},
 "pagination":{"size":2}}
```
→ `{"total":2,"success":true,"leads":[{...}]}`. Un lead (pas d'email — profil LinkedIn) :
```json
{"firstname":"Guillaume","lastname":"Moigneu","lastJobTitle":"Field CTO",
 "profileUrl":"https://www.linkedin.com/in/guillaumemoigneu",
 "headline":"...","description":"...","address":"...",
 "lastCompanyName":"Upsun","lastCompanyWebsite":"http://www.upsun.com",
 "lastCompanyIndustry":"Software Development","lastCompanySize":281,
 "lastCompanyAddress":"22 Rue de Palestro, 75002, Paris, ..."}
```
- `currentJobTitle.include` fait du fuzzy ("CTO" matche "Field CTO").
- Mapping : `firstname`/`lastname`, `title_raw=lastJobTitle`, `linkedin_url=profileUrl`.
- Pas d'email → alimente ensuite le finder (email-search).
