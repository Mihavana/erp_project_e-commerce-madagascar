## Équipe Projet

- **RAHOLDINA FIARA ANJARA MIHAVANA**
- **ANDRIATSIFERANA NO KANTO LORIDA**
- **RAKOTONIRINA MENDRIKA ITOKIANA**

---

# Demo Guide: Madagascar E-Commerce Platform (ERP & BI)

This project is a comprehensive e-commerce management solution (ERP) coupled with an intelligent Business Intelligence (BI) and Artificial Intelligence stack.

## Project Architecture

The system comprises **6 services** orchestrated by Docker:

1.  **Database (PostgreSQL)**: Central storage for ERP data and Data Warehouse.
2.  **ERP Service (FastAPI)**: Management of orders, customers, and inventory for Madagascar marketplace.
3.  **ETL Service (Pandas)**: Automation of extraction and transformation to star schema.
4.  **Analytics Service (Scikit-Learn)**: Data Mining engine (RFM, ARIMA).
5.  **AI Dashboard (Streamlit)**: User interface with AI-powered reporting (NLG).
6.  **Metabase**: Self-service BI tool for visual exploration.

---

## Quick Installation

1.  **Set environment variables**:
    Create a `.env` file at project root:
    ```env
    # Database
    DB_USER=admin
    DB_PASS=123456
    DB_NAME_ERP=erp_db
    DB_NAME_BI=bi_warehouse

    # AI Token (Free on https://console.groq.com/keys)
    GROQ_TOKEN==your_Groq_token_here
    ```

2.  Launch the infrastructure:
    ```bash
    docker-compose up -d --build
    ```

---

## Demo Steps

### 1. Master Data Initialization
Populate ERP with initial products and customers.
-   **Action**: Click on [http://localhost:8000/seed/](http://localhost:8000/seed/)
-   **Tool**: Browser or Postman.

### 2. Generate Bulk Data
Generate 50+ historical orders for AI model training.
-   **Action**: Click on [http://localhost:8000/seed_massive/](http://localhost:8000/seed_massive/)

### 3. Launch ETL
Transfer ERP data to Data Warehouse BI (Star Schema).
-   **Action**: Click on [http://localhost:8002/trigger](http://localhost:8002/trigger)
-   **Verification**: Check `http://localhost:8002/status` for loaded rows.

### 4. Data Analysis & Mining
Analytics service now processes Warehouse data.
-   **RFM Segmentation**: `http://localhost:8001/mining/rfm`
-   **ARIMA Predictions**: `http://localhost:8001/mining/predictions`

### 5. Interactive Dashboard & AI
Access the interface (`http://localhost:8501`).
-   **RFM Tab**: View customer segments (Premium, Occasional, At-Risk).
-   **Predictions Tab**: See future sales trends.
-   **AI Tab**: Generate automated strategic report based on KPIs.

### 6. BI Exploration (Metabase)
For advanced analysis: `http://localhost:3000`.

**Initial Configuration (if needed):**
-   **Database Type**: PostgreSQL
-   **Host**: `db` (from Docker) or `localhost` (direct access)
-   **Database**: `bi_warehouse`
-   **User**: `admin` (or from `.env`)
-   **Password**: `123456` (or from `.env`)

*Note: ETL must run at least once for tables to be visible.*

---

## Useful Links

| Service | URL / Port | API Documentation |
| :--- | :--- | :--- |
| **ERP** | [localhost:8000](http://localhost:8000) | [/docs](http://localhost:8000/docs) |
| **ETL** | [localhost:8002](http://localhost:8002) | [/docs](http://localhost:8002/docs) |
| **Analytics** | [localhost:8001](http://localhost:8001) | [/docs](http://localhost:8001/docs) |
| **Dashboard** | [localhost:8501](http://localhost:8501) | - |
| **Metabase** | [localhost:3000](http://localhost:3000) | - |
