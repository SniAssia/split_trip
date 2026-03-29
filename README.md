# split_trip
#  SplitTrip — Gestion des dépenses de voyage en groupe

> Application web Django pour gérer les dépenses collectives lors de voyages en groupe.  
> Calcule automatiquement les soldes individuels et génère un plan de règlement optimisé qui **minimise le nombre de transactions**.

---

##  Table des matières

1. [Installation & Lancement](#-installation--lancement)
2. [Architecture du projet](#-architecture-du-projet)
3. [Modèles de données](#-modèles-de-données)
4. [Logique métier](#-logique-métier)
5. [API REST](#-api-rest)
6. [Rôles & Permissions](#-rôles--permissions)
7. [Interface web](#-interface-web)

---

##  Installation & Lancement

### Prérequis

- Python 3.9+
- pip

### Étapes

**1. Décompresser et entrer dans le projet**

```bash
unzip splittrip.zip
cd splittrip
```

**2. Créer un environnement virtuel**

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

**3. Installer les dépendances**

```bash
pip install -r requirements.txt
```

**4. Configurer les variables d'environnement**

```bash
cp .env.example .env
# Le fichier .env est prêt à l'emploi avec SQLite par défaut
```

**5.  Créer les tables en base de données (étape obligatoire)**

```bash
python manage.py makemigrations trips
python manage.py migrate
```

**6. Créer un super-utilisateur (accès admin)**

```bash
python manage.py createsuperuser
```

**7. Lancer le serveur**

```bash
python manage.py runserver
```

L'application est accessible sur **http://127.0.0.1:8000**  
L'interface admin est accessible sur **http://127.0.0.1:8000/admin**

---

### Utiliser PostgreSQL à la place de SQLite (optionnel)

Dans `.env`, ajouter :

```
DB_NAME=splittrip
DB_USER=postgres
DB_PASSWORD=motdepasse
DB_HOST=localhost
DB_PORT=5432
```

Puis dans `splittrip/settings.py`, décommenter le bloc PostgreSQL et commenter le bloc SQLite.

---

## 🗂️ Architecture du projet

```
splittrip/
│
├── manage.py
├── requirements.txt
├── .env.example
│
├── splittrip/                  # Configuration centrale Django
│   ├── settings.py             # Paramètres (BDD, apps, DRF, auth...)
│   ├── urls.py                 # Routage principal
│   └── wsgi.py
│
├── trips/                      # Application principale (logique métier)
│   ├── models.py               # Modèles : Trip, Membership, Expense, ExpenseSplit, Settlement
│   ├── services.py             # Algorithmes : calcul soldes + optimisation règlements
│   ├── views.py                # Vues Django (interface web HTML)
│   ├── forms.py                # Formulaires Django
│   ├── urls.py                 # Routes de l'interface web
│   └── admin.py                # Interface d'administration
│
├── api/                        # API REST (Django REST Framework)
│   ├── serializers.py          # Sérialisation des modèles en JSON
│   ├── views.py                # Vues API (APIView, generics)
│   └── urls.py                 # Routes /api/...
│
└── templates/
    ├── base.html               # Layout principal (navbar, messages)
    ├── registration/
    │   ├── login.html
    │   └── register.html
    └── trips/
        ├── dashboard.html              # Liste des voyages de l'utilisateur
        ├── trip_detail.html            # Vue principale d'un voyage (4 onglets)
        ├── trip_form.html              # Créer / modifier un voyage
        ├── expense_form.html           # Ajouter une dépense
        ├── trip_summary_guest.html     # Vue lecture seule (invité sans compte)
        ├── trip_confirm_delete.html
        └── expense_confirm_delete.html
```

---

##  Modèles de données

### `Trip` — Voyage

| Champ | Type | Description |
|-------|------|-------------|
| `name` | CharField | Nom du voyage |
| `creator` | ForeignKey(User) | Utilisateur créateur |
| `currency` | CharField | Devise (MAD, EUR, USD, GBP) |
| `start_date` / `end_date` | DateField | Dates du voyage |
| `cover_image` | ImageField | Photo de couverture (optionnel) |
| `invite_token` | UUIDField | Token unique pour le lien d'invitation |

---

### `Membership` — Appartenance à un voyage

Table de liaison entre `User` et `Trip` avec un rôle.

| Champ | Type | Description |
|-------|------|-------------|
| `user` | ForeignKey(User) | Membre |
| `trip` | ForeignKey(Trip) | Voyage |
| `role` | CharField | `organizer`, `member`, ou `guest` |

> **Contrainte** : un utilisateur ne peut appartenir qu'une seule fois à un voyage (`unique_together`).

---

### `Expense` — Dépense

| Champ | Type | Description |
|-------|------|-------------|
| `trip` | ForeignKey(Trip) | Voyage associé |
| `paid_by` | ForeignKey(User) | Qui a payé |
| `title` | CharField | Description de la dépense |
| `amount` | DecimalField | Montant total |
| `category` | CharField | food, transport, accommodation, activities, shopping, health, other |
| `split_type` | CharField | `equal`, `percentage`, ou `exact` |
| `date` | DateField | Date de la dépense |
| `receipt` | ImageField | Photo du reçu (optionnel) |

---

### `ExpenseSplit` — Répartition d'une dépense

Détaille combien chaque participant doit pour une dépense donnée.

| Champ | Type | Description |
|-------|------|-------------|
| `expense` | ForeignKey(Expense) | Dépense concernée |
| `user` | ForeignKey(User) | Participant |
| `amount_owed` | DecimalField | Montant dû par ce participant |
| `percentage` | DecimalField | Pourcentage (pour split de type `percentage`) |

---

### `Settlement` — Paiement enregistré

Trace les remboursements réels effectués entre membres.

| Champ | Type | Description |
|-------|------|-------------|
| `trip` | ForeignKey(Trip) | Voyage |
| `payer` | ForeignKey(User) | Celui qui paie |
| `receiver` | ForeignKey(User) | Celui qui reçoit |
| `amount` | DecimalField | Montant remboursé |

---

### Schéma relationnel

```
User ──< Membership >── Trip
                         │
                         ├──< Expense >── ExpenseSplit >── User
                         │
                         └──< Settlement (payer → receiver)
```

---

## ⚙️ Logique métier

Toute la logique de calcul est centralisée dans `trips/services.py`.

---

### 1. Calcul des soldes — `calculate_balances(trip)`

Pour chaque membre du voyage, on calcule un **solde net** :

```
solde = (somme de ce qu'il a payé) - (somme de ce qu'il doit aux autres) - (paiements effectués) + (paiements reçus)
```

- **Solde positif** → le membre a avancé de l'argent, il doit être remboursé.
- **Solde négatif** → le membre doit de l'argent aux autres.
- **Solde zéro** → le membre est équilibré.

Les règlements déjà enregistrés (`Settlement`) sont déduits en temps réel pour refléter l'état actuel.

---

### 2. Matrice des dettes directes — `calculate_who_owes_whom(trip)`

Construit une matrice des dettes brutes entre chaque paire d'utilisateurs en parcourant toutes les `ExpenseSplit`. Les règlements déjà effectués sont soustraits.

Retourne une liste de tuples `(de: User, à: User, montant: Decimal)`.

---

### 3. Algorithme d'optimisation des règlements — `calculate_optimized_settlements(trip)`

C'est le cœur algorithmique de l'application. L'objectif est de **minimiser le nombre de transactions** nécessaires pour solder tous les comptes.

**Algorithme utilisé : Greedy Min-Cash-Flow**

```
1. Calculer le solde net de chaque membre
2. Séparer en deux groupes :
   - créditeurs  : solde > 0 (doivent recevoir de l'argent)
   - débiteurs   : solde < 0 (doivent payer)
3. Trier les deux groupes par montant décroissant
4. Boucle greedy :
   - Prendre le plus grand créditeur et le plus grand débiteur
   - Le débiteur paie min(sa_dette, crédit_du_créditeur) au créditeur
   - Mettre à jour les soldes
   - Si un solde atteint 0, passer au suivant
5. Répéter jusqu'à ce que tous les soldes soient nuls
```

**Exemple concret :**

```
Voyage à 3 : Alice, Bob, Charlie
Alice paie le restaurant : 300 MAD  → split égal : chacun doit 100
Bob paie le taxi         : 60 MAD   → split égal : chacun doit 20
Charlie paie rien.

Soldes bruts :
  Alice   : +300 payé - 100 dû - 20 dû = +180
  Bob     : +60 payé  - 100 dû - 20 dû = -60
  Charlie : +0 payé   - 100 dû - 20 dû = -120

Règlements optimisés (2 transactions seulement) :
  Charlie → Alice  : 120 MAD
  Bob     → Alice  :  60 MAD
```

**Complexité** : O(n log n) — très efficace même pour de grands groupes.

---

### 4. Types de répartition d'une dépense

| Type | Logique |
|------|---------|
| **Égal** (`equal`) | `montant / nombre_participants` — le premier participant absorbe l'arrondi décimal |
| **Pourcentage** (`percentage`) | Chaque participant se voit attribuer un % du total. La somme des % doit faire 100. |
| **Montant exact** (`exact`) | Chaque participant a un montant fixé manuellement. La somme doit égaler le total. |

---

##  API REST

Base URL : `/api/`  
Authentification : Session Django ou Token (`Authorization: Token <votre_token>`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/trips/` | Lister les voyages de l'utilisateur connecté |
| `POST` | `/api/trips/` | Créer un voyage |
| `GET` | `/api/trips/{id}/` | Détail d'un voyage |
| `PUT/PATCH` | `/api/trips/{id}/` | Modifier un voyage (organisateur) |
| `DELETE` | `/api/trips/{id}/` | Supprimer un voyage (organisateur) |
| `GET` | `/api/trips/{id}/expenses/` | Lister les dépenses |
| `POST` | `/api/trips/{id}/expenses/` | Ajouter une dépense |
| `GET` | `/api/trips/{id}/balances/` | Soldes de tous les membres |
| `GET` | `/api/trips/{id}/settlements/` | Plan de règlement optimisé |
| `POST` | `/api/trips/{id}/settlements/record/` | Enregistrer un paiement effectué |
| `GET` | `/api/trips/{id}/members/` | Lister les membres |
| `POST` | `/api/trips/{id}/invite/` | Inviter un membre par email |

### Exemple — Créer une dépense (POST `/api/trips/1/expenses/`)

```json
{
  "title": "Dîner rooftop",
  "amount": "450.00",
  "category": "food",
  "split_type": "equal",
  "date": "2026-03-29",
  "participant_ids": [1, 2, 3]
}
```

### Exemple — Réponse balances (GET `/api/trips/1/balances/`)

```json
[
  { "user": { "id": 1, "username": "alice"   }, "balance":  "180.00" },
  { "user": { "id": 2, "username": "bob"     }, "balance":  "-60.00" },
  { "user": { "id": 3, "username": "charlie" }, "balance": "-120.00" }
]
```

### Exemple — Réponse settlements (GET `/api/trips/1/settlements/`)

```json
{
  "optimized_settlements": [
    { "payer": { "username": "charlie" }, "receiver": { "username": "alice" }, "amount": "120.00" },
    { "payer": { "username": "bob"     }, "receiver": { "username": "alice" }, "amount":  "60.00" }
  ]
}
```

---

## Rôles & Permissions

| Action | Organisateur | Membre | Invité (lien public) |
|--------|:---:|:---:|:---:|
| Voir le voyage | t | t | t lecture seule |
| Ajouter une dépense | t | t | f |
| Supprimer une dépense | t | t (seulement les siennes) | f |
| Inviter des membres | t |  | f |
| Retirer un membre | t | f | f |
| Modifier le voyage | t | f | f |
| Supprimer le voyage | t | f | f |
| Enregistrer un règlement | t | t | f |

Le lien d'invitation (`/trips/summary/<uuid>/`) donne une **vue publique lecture seule** sans compte nécessaire — idéal pour partager un résumé du voyage.

---

##  Interface web — Pages principales

| URL | Page |
|-----|------|
| `/` | Tableau de bord — liste des voyages |
| `/trips/create/` | Créer un voyage |
| `/trips/<id>/` | Détail voyage (4 onglets : Dépenses, Soldes, Règlements, Membres) |
| `/trips/<id>/expenses/add/` | Ajouter une dépense |
| `/trips/join/<token>/` | Rejoindre un voyage via lien |
| `/trips/summary/<token>/` | Vue publique lecture seule |
| `/auth/login/` | Connexion |
| `/auth/register/` | Inscription |
| `/admin/` | Interface d'administration Django |

---

##  Stack technique

| Composant | Technologie |
|-----------|-------------|
| Framework | Django 4.2 |
| API REST | Django REST Framework 3.14 |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Bootstrap 5 + Font Awesome 6 |
| Auth | Django Auth intégré + Token DRF |
| Upload fichiers | Pillow |
| Config | python-decouple (.env) |

---

*Projet académique — UM6P College of Computing | Pr. Fakir BENHLIMA | 2025-2026*
