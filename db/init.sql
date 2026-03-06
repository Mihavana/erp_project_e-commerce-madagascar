-- Base pour le Data Warehouse (BI)
CREATE DATABASE bi_warehouse;
GRANT ALL PRIVILEGES ON DATABASE bi_warehouse TO admin;

-- Base pour la configuration interne de Metabase (Sauvegarde des dashboards)
CREATE DATABASE metabase_app_db;
GRANT ALL PRIVILEGES ON DATABASE metabase_app_db TO admin;