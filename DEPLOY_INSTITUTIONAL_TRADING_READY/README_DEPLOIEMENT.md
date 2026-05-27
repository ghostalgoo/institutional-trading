# Deploiement Institutional Trading

## Recommande

Publier sur Railway ou Render en tant que service Python, pas en hebergement statique simple.
Le site a besoin du backend Python pour le calendrier, l'admin, l'espace client, les webhooks PayPal, les dons, les stats visiteurs et la vente flash.

## Commande de demarrage

```bash
python ghost_calendar_api.py --host 0.0.0.0 --port $PORT
```

Le `Procfile` contient deja cette commande.

## Variables de production

```bash
TRADING_ADMIN_PASSWORD=un-mot-de-passe-fort
TRADING_ADMIN_KEY=un-lien-prive-long
TRADING_DONATION_EMAIL=Mehdi.parisville@outlook.com
SUPABASE_URL=https://votre-projet.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
PAYPAL_WEBHOOK_ID=...
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

Liens PayPal utilises dans le site :

- Gold : https://www.paypal.com/ncp/payment/DCVU8JTEY7GJ4
- Nasdaq : https://www.paypal.com/ncp/payment/VMTBQ5G9EMWTU
- BTC : https://www.paypal.com/ncp/payment/SB6UU4KPJ974A

Ne pas activer `PAYPAL_WEBHOOK_ALLOW_UNVERIFIED` en production.

## Stockage

Sur Render gratuit, utiliser Supabase pour conserver les donnees.
Executer `supabase_schema.sql` dans le SQL Editor Supabase, puis ajouter `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` dans les variables Render.

Le site garde aussi une copie fichier locale en fallback, mais sans disque persistant Render cette copie locale peut disparaitre au redeploiement.

## URLs apres publication

- Site public : `/`
- Espace client : `/client.html`
- Admin prive : `/admin.html?owner=VOTRE_TRADING_ADMIN_KEY`
- Webhook PayPal : `/api/paypal/webhook`

## Checklist publication

1. Publier le dossier complet sur Render ou Railway en service Python.
2. Executer `supabase_schema.sql` dans Supabase.
3. Mettre les variables de production.
4. Dans PayPal Developer, creer un webhook vers `https://votre-domaine.com/api/paypal/webhook`.
5. Copier le `PAYPAL_WEBHOOK_ID` dans les variables de production.
6. Faire un paiement test, verifier `/admin.html?owner=...`, puis valider l'espace client.
