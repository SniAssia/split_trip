# ✈️ SplitTrip – Gestion des dépenses de voyage en groupe

Application Django pour gérer les dépenses collectives lors de voyages en groupe.
Calcule automatiquement les soldes et génère un plan de règlement optimisé.

---

## 🚀 Installation & Lancement

### 1. Cloner / décompresser le projet

```bash
cd splittrip
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

```bash
cp .env.example .env
# Éditez .env si nécessaire (SQLite utilisé par défaut)
```

### 5. Appliquer les migrations

```bash
python manage.py migrate
```

### 6. Créer un super-utilisateur

```bash
python manage.py createsuperuser
```

### 7. Lancer le serveur

```bash
python manage.py runserver
```

Accédez à : **http://127.0.0.1:8000**

---

## 📁 Structure du projet

```
splittrip/
├── manage.py
├── requirements.txt
├── .env.example
├── splittrip/           # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── trips/               # App principale
│   ├── models.py        # Trip, Membership, Expense, ExpenseSplit, Settlement
│   ├── views.py         # Vues Django (interface web)
│   ├── forms.py         # Formulaires
│   ├── services.py      # Algorithme de calcul des soldes & règlements
│   ├── urls.py
│   └── admin.py
├── api/                 # API REST (Django REST Framework)
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
└── templates/
    ├── base.html
    ├── registration/
    │   ├── login.html
    │   └── register.html
    └── trips/
        ├── dashboard.html
        ├── trip_detail.html
        ├── trip_form.html
        ├── expense_form.html
        └── trip_summary_guest.html
```

---

## 🔌 API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/trips/` | Lister les voyages |
| POST | `/api/trips/` | Créer un voyage |
| GET | `/api/trips/{id}/` | Détail d'un voyage |
| GET | `/api/trips/{id}/expenses/` | Lister les dépenses |
| POST | `/api/trips/{id}/expenses/` | Ajouter une dépense |
| GET | `/api/trips/{id}/balances/` | Soldes des membres |
| GET | `/api/trips/{id}/settlements/` | Plan de règlement optimisé |
| POST | `/api/trips/{id}/invite/` | Inviter un membre |
| POST | `/api/trips/{id}/settlements/record/` | Enregistrer un paiement |

**Authentification API :** Session ou Token (`Authorization: Token <token>`)

---

## ⚙️ Fonctionnalités

- ✅ Gestion des voyages (CRUD)
- ✅ Invitation par email ou lien
- ✅ Ajout de dépenses (split égal, pourcentage, montant exact)
- ✅ Calcul des soldes en temps réel
- ✅ Algorithme d'optimisation des règlements (min transactions)
- ✅ Enregistrement des paiements effectués
- ✅ Vue lecture seule pour invités
- ✅ API REST complète (DRF)
- ✅ Interface admin Django

---

## 🗄️ Base de données

SQLite par défaut. Pour PostgreSQL, modifiez `.env` :

```
DB_NAME=splittrip
DB_USER=postgres
DB_PASSWORD=motdepasse
DB_HOST=localhost
DB_PORT=5432
```

Et décommentez la config PostgreSQL dans `settings.py`.

---

## 👨‍💻 Auteur

Projet académique – UM6P College of Computing  
Pr. Fakir BENHLIMA – Année 2025-2026
