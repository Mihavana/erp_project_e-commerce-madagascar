import pandas as pd
from sqlalchemy import create_engine, text
import os
import time
import schedule
import threading
from fastapi import FastAPI, BackgroundTasks

# --- CONFIGURATION ---
SRC_URL = os.getenv("SRC_DB_URL", "postgresql://admin:password@db/erp_db")
TGT_URL = os.getenv("TGT_DB_URL", "postgresql://admin:password@db/bi_warehouse")

app = FastAPI(
    title="ETL Manager (Madagascar E-Commerce)",
    description="Extraction from ERP to Data Warehouse (Star Schema)",
    version="3.0"
)

etl_status = {
    "last_run": "Jamais",
    "status": "En attente",
    "rows_loaded": 0
}

# --- FONCTION UTILITAIRE : SAISON ---
def get_season(month):
    if month in [12, 1, 2]:
        return "Hiver"
    elif month in [3, 4, 5]:
        return "Printemps"
    elif month in [6, 7, 8]:
        return "Été"
    else:
        return "Automne"

# --- BUSINESS LOGIC ETL ---
def run_etl_logic():
    global etl_status
    print("--- 🔄 Starting ETL (Star Schema) ---")
    etl_status["status"] = "Extraction in progress..."
    
    try:
        src_engine = create_engine(SRC_URL)
        tgt_engine = create_engine(TGT_URL)

        # ==========================================
        # 1. EXTRACTION (From ERP)
        # ==========================================
        query = """
        SELECT 
            o.id as order_id, o.created_at as date_commande, o.customer_id,
            oi.product_id, oi.quantity, oi.unit_price, oi.discount_applied,
            p.sku, p.name as product_name, p.purchase_price,
            c.name as customer_name, c.is_premium
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN customers c ON o.customer_id = c.id
        WHERE o.status = 'VALIDATED'
        """
        with src_engine.connect() as conn:
            df_raw = pd.read_sql(query, conn)
        
        if df_raw.empty:
            print("No validated orders to process.")
            etl_status["status"] = "Completed (Empty)"
            return

        etl_status["status"] = "Transformation in progress..."

        # ==========================================
        # 2. TRANSFORMATION (Create Dimensions)
        # ==========================================
        
        # --- Dim_Time ---
        df_raw['date_commande'] = pd.to_datetime(df_raw['date_commande'])
        dim_temps = pd.DataFrame({'date_key': df_raw['date_commande'].dt.date.unique()})
        dim_temps['date_key'] = pd.to_datetime(dim_temps['date_key'])
        dim_temps['annee'] = dim_temps['date_key'].dt.year
        dim_temps['mois'] = dim_temps['date_key'].dt.month
        dim_temps['jour'] = dim_temps['date_key'].dt.day
        dim_temps['saison'] = dim_temps['mois'].apply(get_season)

        # --- Dim_Product ---
        dim_produit = df_raw[['product_id', 'sku', 'product_name', 'purchase_price']].drop_duplicates()

        # --- Dim_Customer ---
        dim_client = df_raw[['customer_id', 'customer_name', 'is_premium']].drop_duplicates()
        dim_client['segment'] = dim_client['is_premium'].apply(lambda x: 'Premium' if x else 'Standard')
        # Add geographic dimension for compliance
        dim_client['geographie'] = 'Madagascar'

        # --- Dim_Store ---
        # Since current ERP doesn't have multi-store, create default dimension
        dim_magasin = pd.DataFrame({
            'magasin_id': [1],
            'nom_magasin': ['Online Marketplace'],
            'ville': ['Antananarivo']
        })

        # ==========================================
        # 3. TRANSFORMATION (Create Fact Table)
        # ==========================================
        fact_ventes = df_raw.copy()
        
        # Calculate indicators (Measures)
        fact_ventes['date_key'] = fact_ventes['date_commande'].dt.date
        fact_ventes['magasin_id'] = 1  # Link to Dim_Store
        fact_ventes['montant_ht'] = fact_ventes['quantity'] * fact_ventes['unit_price']
        fact_ventes['cout_total'] = fact_ventes['quantity'] * fact_ventes['purchase_price']
        fact_ventes['marge'] = fact_ventes['montant_ht'] - fact_ventes['cout_total']

        # Final column selection for fact table
        fact_ventes = fact_ventes[[
            'order_id', 'date_key', 'customer_id', 'product_id', 'magasin_id',
            'quantity', 'montant_ht', 'marge'
        ]]

        etl_status["status"] = "Loading in progress..."

        # ==========================================
        # 4. LOADING (To Data Warehouse)
        # ==========================================
        with tgt_engine.connect() as conn:
            dim_temps.to_sql('dim_temps', conn, if_exists='replace', index=False)
            dim_produit.to_sql('dim_produit', conn, if_exists='replace', index=False)
            dim_client.to_sql('dim_client', conn, if_exists='replace', index=False)
            dim_magasin.to_sql('dim_magasin', conn, if_exists='replace', index=False)
            fact_ventes.to_sql('fact_ventes', conn, if_exists='replace', index=False)
        
        count = len(fact_ventes)
        print(f"✅ ETL Completed: {count} sales facts loaded.")
        etl_status["rows_loaded"] = count
        etl_status["status"] = "Success"
        etl_status["last_run"] = time.strftime("%H:%M:%S")
        
    except Exception as e:
        print(f"❌ ETL Error: {e}")
        etl_status["status"] = f"Error: {str(e)}"

# --- SCHEDULER (Automatisation) ---
def run_scheduler():
    schedule.every(1).minutes.do(run_etl_logic)
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.on_event("startup")
def start_scheduler():
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()

# --- ENDPOINTS (Swagger) ---
@app.get("/")
def health_check():
    return {"status": "Online"}

@app.get("/status")
def get_status():
    return etl_status

@app.api_route("/trigger", methods=["GET", "POST"])
def trigger_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_etl_logic)
    return {"msg": "ETL launched in background to Data Warehouse!"}