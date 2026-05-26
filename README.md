# BreatheESG — Enterprise Carbon Intelligence Platform

BreatheESG is a modern, enterprise-grade web application built to ingest, normalize, and audit corporate carbon emissions data. It provides organizations with an end-to-end solution for carbon accounting, featuring automated parsing of raw ERP exports, live emissions factor application, and a strictly immutable Carbon Ledger.

## Architecture

BreatheESG uses a decoupled Full-Stack architecture:
*   **Frontend:** React (Vite), Tailwind CSS, Lucide Icons. Designed with modern glassmorphism aesthetics and micro-animations for an exceptional user experience.
*   **Backend:** Django & Django REST Framework (DRF). Provides robust routing, strict model validation, JWT authentication, and tenant isolation.
*   **Database:** SQLite (for local development).

## Key Features

*   **Multi-Source Data Ingestion:** Automated parsers capable of handling raw data from SAP (MB51 CSVs), Utility Bills (eGRID/Green Button), and Concur Corporate Travel exports.
*   **Normalization Engine:** Automatically maps raw consumption data to the latest **DEFRA 2025** and **EPA eGRID 2025** emission factors to calculate tCO2e (tonnes of carbon).
*   **Analyst Review Queue:** A staging area where human analysts can review, flag, reject, or approve parsed rows before they are permanently committed.
*   **Immutable Carbon Ledger:** The final source of truth for all approved corporate emissions. Once data hits the ledger, it can never be deleted—only reversed or amended.
*   **Complete Audit Trail:** Deep, immutable audit logging tracking every state change, user action, and before/after JSON diff across the entire platform.

---

## Local Setup Instructions

Follow these steps to run the BreatheESG application on your local machine.

### 1. Backend Setup (Django)

Open your terminal and navigate to the `backend` directory:
```bash
cd backend
```

Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

Run database migrations to initialize SQLite:
```bash
python manage.py migrate
```

(Optional) Create a superuser to access the Django Admin panel:
```bash
python manage.py createsuperuser
```

Start the Django development server:
```bash
python manage.py runserver
```
*The backend API will now be running at `http://localhost:8000/api/v1`*

### 2. Frontend Setup (React/Vite)

Open a **new** terminal window and navigate to the `frontend` directory:
```bash
cd frontend
```

Install the Node modules:
```bash
npm install
```

Ensure your `.env` file exists in the `frontend/` directory and points to your local backend:
```env
VITE_API_URL=http://localhost:8000/api/v1
```

Start the Vite development server:
```bash
npm run dev
```
*The frontend will launch at `http://localhost:5173` (or whichever port Vite provides).*

---

## Deployment Notes (Vercel)

If deploying this repository to Vercel or a similar cloud platform:
1. **Frontend:** Simply deploy the `frontend` folder and set `VITE_API_URL` to your production backend URL.
2. **Backend:** If deploying the backend serverless on Vercel, be aware that Vercel uses an ephemeral, read-only filesystem. **SQLite (`db.sqlite3`) will not work for write operations in production.** You will need to migrate to a cloud PostgreSQL provider (like Neon or Supabase) and update the `DATABASE_URL` environment variable.
