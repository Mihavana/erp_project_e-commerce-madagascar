from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timedelta
import os
import time
import random

# --- CONFIGURATION BDD ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@db/erp_db")

def wait_for_db():
    retries = 0
    while retries < 30:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                pass
            print("✅ BDD Connectée.")
            return engine
        except:
            print("⏳ Attente BDD...")
            time.sleep(2)
            retries += 1
    raise Exception("Erreur connexion BDD")

engine = wait_for_db()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()

# --- 1. MODÈLES DE DONNÉES (SQLAlchemy) ---

class User(Base):
    """User admin and vendor accounts"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    role = Column(String)  # 'admin', 'vendor', 'customer_support'

class Customer(Base):
    """Customer CRM module for Madagascar e-commerce marketplace"""
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True)  # Mobile money account
    payment_method = Column(String, default="Mvola")  # Mvola, Orange Money, Airtel Money
    credit_limit = Column(Float, default=50000.0)  # In Ariary (Ar)
    current_debt = Column(Float, default=0.0)
    is_premium = Column(Boolean, default=False)

class Product(Base):
    """Product catalog for Madagascar marketplace"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    price = Column(Float)  # Price in Ariary
    purchase_price = Column(Float)  # Cost in Ariary
    stock_quantity = Column(Integer, default=0)
    safety_stock = Column(Integer, default=10)
    category = Column(String, default="General")  # Product category

class Order(Base):
    """Order management for Madagascar e-commerce"""
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total_amount = Column(Float, default=0.0)  # Amount in Ariary
    status = Column(String, default="PENDING")  # PENDING, VALIDATED, DELIVERED
    payment_method = Column(String, default="Mvola")  # Mobile money payment
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    discount_applied = Column(Float, default=0.0)
    
    order = relationship("Order", back_populates="items")

class StockMovement(Base):
    """Stock movement tracking"""
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    movement_type = Column(String)  # 'IN' (purchase), 'OUT' (sale)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))

class AuditLog(Base):
    """Audit and traceability log for compliance"""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    details = Column(String)
    user_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Madagascar E-Commerce Platform (ERP SOA)", version="3.0")

# --- FONCTIONS UTILITAIRES ---
def log_action(db, action, details, user_id=None):
    db.add(AuditLog(action=action, details=details, user_id=user_id))

# --- DTOs (Data Transfer Objects) ---
class OrderItemDTO(BaseModel):
    product_id: int
    quantity: int

class OrderCreateDTO(BaseModel):
    customer_id: int
    items: list[OrderItemDTO]
    user_id: int
    payment_method: str = "Mvola"  # Mvola, Orange Money, Airtel Money

# --- ENDPOINTS ---

@app.post("/orders/")
def create_order(order_data: OrderCreateDTO):
    """Create a new order for Madagascar marketplace"""
    db = SessionLocal()
    
    try:
        # 1. Customer validation
        customer = db.query(Customer).filter(Customer.id == order_data.customer_id).first()
        if not customer:
            raise HTTPException(404, "Customer not found")

        # 2. Business rule: Block if debt exceeds credit limit
        if customer.current_debt > customer.credit_limit:
            log_action(db, "BLOCKED_ORDER", f"Customer {customer.id} exceeded credit limit.", order_data.user_id)
            db.commit()
            raise HTTPException(400, "Order blocked: Credit limit exceeded.")

        new_order = Order(customer_id=customer.id, created_by_id=order_data.user_id, payment_method=order_data.payment_method)
        db.add(new_order)
        db.flush()

        total = 0.0
        for item_data in order_data.items:
            product = db.query(Product).filter(Product.id == item_data.product_id).first()
            if not product:
                raise HTTPException(404, f"Product {item_data.product_id} not found")
            
            discount = 0.10 if customer.is_premium else 0.0
            final_price = product.price * (1 - discount)
            
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                quantity=item_data.quantity,
                unit_price=final_price,
                discount_applied=discount
            )
            db.add(order_item)
            total += final_price * item_data.quantity

        new_order.total_amount = total
        log_action(db, "CREATE_ORDER", f"Order {new_order.id} created via {order_data.payment_method}", order_data.user_id)
        
        db.commit()
        db.refresh(new_order)
        
        # --- EXTRACTION SÉCURISÉE DES DONNÉES ---
        final_order_id = new_order.id 
        final_total = total
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()
        
    # --- LE RETURN EST EN DEHORS DE LA BDD ---
    return {"status": "PENDING", "order_id": final_order_id, "total": final_total}

@app.put("/orders/{order_id}/validate")
def validate_order(order_id: int, user_id: int):
    """Validate order and process stock deduction"""
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order or order.status != "PENDING":
        raise HTTPException(400, "Order invalid or already processed.")

    # 1. Stock verification for each item
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        
        # Business rule: Prevent order if insufficient stock
        if product.stock_quantity < item.quantity:
            log_action(db, "STOCK_ERROR", f"Out of stock for product {product.sku} in order {order_id}", user_id)
            raise HTTPException(400, f"Insufficient stock for product {product.name}")

    # 2. Stock deduction and traceability
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product.stock_quantity -= item.quantity
        
        # Stock movement record
        db.add(StockMovement(product_id=product.id, quantity=item.quantity, movement_type="OUT", user_id=user_id))
        
        # Safety stock alert
        if product.stock_quantity < product.safety_stock:
            log_action(db, "ALERT_STOCK", f"Product {product.sku} is below safety stock threshold!", user_id)

    order.status = "VALIDATED"
    
    # Update customer debt
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    customer.current_debt += order.total_amount

    log_action(db, "VALIDATE_ORDER", f"Order {order_id} validated and stock deducted.", user_id)
    db.commit()
    db.close()
    return {"status": "VALIDATED", "msg": "Stock updated successfully"}

@app.api_route("/seed/", methods=["GET", "POST"])
def seed_data():
    """Generate Master Data for demo"""
    db = SessionLocal()
    try:
        if not db.query(User).first():
            db.add(User(username="admin", role="admin"))
            db.commit()
        
        admin = db.query(User).first()

        # Seed Products (Madagascar marketplace items)
        if db.query(Product).count() == 0:
            products = [
                Product(sku="MAD001", name="Artisan Woven Basket", price=15000.0, purchase_price=9000.0, stock_quantity=50, safety_stock=5, category="Crafts"),
                Product(sku="MAD002", name="Vanilla Extract 100ml", price=35000.0, purchase_price=20000.0, stock_quantity=200, safety_stock=20, category="Food"),
                Product(sku="MAD003", name="Sisal Rope 50m", price=45000.0, purchase_price=28000.0, stock_quantity=2, safety_stock=10, category="Agriculture")  # Low stock
            ]
            db.add_all(products)
            db.commit()

        # Seed Customers
        if db.query(Customer).count() == 0:
            customers = [
                Customer(name="Andry Shop", email="contact@andryshop.mg", phone="+26134001122", payment_method="Mvola", credit_limit=250000.0, is_premium=True),
                Customer(name="Zafy Store", email="hello@zafy.mg", phone="+26133009988", payment_method="Orange Money", credit_limit=100000.0, current_debt=120000.0)  # Customer will be blocked
            ]
            db.add_all(customers)
            db.commit()
            
            log_action(db, "SEED", "Master data products and customers generated for Madagascar marketplace", admin.id)

        return {"msg": "Master data seeding completed!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()





@app.api_route("/seed_massive/", methods=["GET", "POST"])
def seed_massive_data():
    """Generate bulk data for BI analytics and AI models"""
    db = SessionLocal()
    try:
        admin = db.query(User).first()
        if not admin:
            admin = User(username="admin", role="admin")
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # --- Security check: verify if bulk data already exists ---
        if db.query(Product).filter(Product.sku == "BULK-001").first():
            return {"msg": "✅ Bulk data already present! No need to recreate. You can now run the ETL."}

        # 1. Generate 5 new products (Madagascar marketplace items)
        for i in range(1, 6):
            price = 50000.0 * i  # In Ariary
            db.add(Product(sku=f"BULK-00{i}", name=f"Madagascar Product {i}", price=price, purchase_price=price*0.6, stock_quantity=10000, safety_stock=10, category="General"))
        db.commit()

        # 2. Generate 10 new customers
        payment_methods = ["Mvola", "Orange Money", "Airtel Money"]
        for i in range(1, 11):
            unique_id = random.randint(1000, 9999)
            db.add(Customer(
                name=f"Customer {i} Madagascar", 
                email=f"customer_{unique_id}_{i}@marketplace.mg", 
                phone=f"+261{unique_id}0{i}",
                payment_method=random.choice(payment_methods),
                credit_limit=250000.0, 
                is_premium=(i % 3 == 0)
            ))
        db.commit()

        # 3. Generate 50 validated orders (for ARIMA time series)
        products = db.query(Product).filter(Product.sku.like("BULK-%")).all()
        customers = db.query(Customer).filter(Customer.email.like("customer_%")).all()
        
        for _ in range(50):
            c = random.choice(customers)
            random_days_ago = random.randint(1, 90)
            past_date = datetime.utcnow() - timedelta(days=random_days_ago)
            
            order = Order(customer_id=c.id, created_by_id=admin.id, status="VALIDATED", created_at=past_date, payment_method=c.payment_method)
            db.add(order)
            db.flush()
            
            total = 0
            for _ in range(random.randint(1, 3)):
                p = random.choice(products)
                qty = random.randint(1, 5)
                discount = 0.10 if c.is_premium else 0.0
                price = p.price * (1 - discount)
                
                db.add(OrderItem(order_id=order.id, product_id=p.id, quantity=qty, unit_price=price, discount_applied=discount))
                total += price * qty
            
            order.total_amount = total
            
        db.commit()
        return {"msg": "✅ Bulk data seeding completed! 50 orders generated for analytics."}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error during bulk seeding: {str(e)}")
    finally:
        db.close()