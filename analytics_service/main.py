from fastapi import FastAPI, HTTPException
import pandas as pd
from sqlalchemy import create_engine
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
from datetime import timedelta
import warnings

warnings.filterwarnings('ignore')

# Utilise la variable DATABASE_URL définie dans ton docker-compose
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@db/bi_warehouse")

app = FastAPI(title="Analytics Service (Madagascar E-Commerce)", version="3.0")

def get_bi_engine():
    return create_engine(DATABASE_URL)

# --- 1. DATA MINING: RFM SEGMENTATION (K-MEANS) ---
@app.get("/mining/rfm")
def get_rfm_segmentation():
    engine = get_bi_engine()
    query = """
        SELECT 
            c.customer_name, 
            MAX(f.date_key) as last_order_date,
            COUNT(DISTINCT f.order_id) as frequence,
            SUM(f.montant_ht) as montant_total
        FROM fact_ventes f
        JOIN dim_client c ON f.customer_id = c.customer_id
        GROUP BY c.customer_name
    """
    try:
        df = pd.read_sql(query, engine)
        if df.empty or len(df) < 3:
            return {"status": "Not enough data for K-Means (Min: 3 customers). Run ETL first."}

        df['last_order_date'] = pd.to_datetime(df['last_order_date'])
        reference_date = df['last_order_date'].max()
        df['recence'] = (reference_date - df['last_order_date']).dt.days

        features = df[['recence', 'frequence', 'montant_total']]
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(scaled_features)

        cluster_means = df.groupby('cluster')['montant_total'].mean().sort_values()
        labels = {cluster_means.index[0]: 'At Risk', cluster_means.index[1]: 'Occasional', cluster_means.index[2]: 'Premium'}
        df['segment'] = df['cluster'].map(labels)

        return df[['customer_name', 'recence', 'frequence', 'montant_total', 'segment']].to_dict(orient="records")
    except Exception as e:
        raise HTTPException(500, f"RFM Error: {str(e)}")

# --- 2. TIME SERIES: SALES PREDICTIONS (ARIMA) ---
@app.get("/mining/predictions")
def get_sales_predictions():
    engine = get_bi_engine()
    query = "SELECT date_key, SUM(montant_ht) as total_sales FROM fact_ventes GROUP BY date_key ORDER BY date_key"
    try:
        df = pd.read_sql(query, engine)
        if len(df) < 5:
            return {"status": "mock", "message": "Simulation of next 3 months (insufficient historical data).", 
                    "data": [{"date": "Month +1", "prediction": 625000000}, {"date": "Month +2", "prediction": 660000000}, {"date": "Month +3", "prediction": 705000000}]}
        
        df['date_key'] = pd.to_datetime(df['date_key'])
        df.set_index('date_key', inplace=True)
        
        model = ARIMA(df['total_sales'], order=(1, 1, 1))
        fitted = model.fit()
        forecast = fitted.forecast(steps=90)
        
        future_dates = [df.index[-1] + timedelta(days=i) for i in range(1, 91)]
        df_forecast = pd.DataFrame({'date': future_dates, 'prediction': forecast.values})
        df_forecast['month'] = df_forecast['date'].dt.strftime('%Y-%m')
        monthly_forecast = df_forecast.groupby('month')['prediction'].sum().reset_index()

        return {"status": "success", "data": monthly_forecast.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(500, f"ARIMA Error: {str(e)}")

# --- 3. KPI PROVIDER FOR AI ---
@app.get("/kpis")
def get_kpis():
    """Provides global metrics to Dashboard for AI processing"""
    engine = get_bi_engine()
    try:
        ca = pd.read_sql("SELECT SUM(montant_ht) as total FROM fact_ventes", engine).iloc[0]['total']
        marge = pd.read_sql("SELECT SUM(marge) as total FROM fact_ventes", engine).iloc[0]['total']
        return {"ca_total": float(ca) if pd.notna(ca) else 0, "marge_totale": float(marge) if pd.notna(marge) else 0}
    except Exception:
        return {"ca_total": 0, "marge_totale": 0}