import streamlit as st
import pandas as pd
import sqlite3
import os
import threading
from datetime import datetime

# ==========================================================
# ---- CONFIGURATION ----
# ==========================================================
DB_PATH = r"\\bioblrnas\msat\inventory.db"

st.set_page_config(page_title="Inventory Management", layout="wide")
st.title("📦 Inventory Management")

# ---- Show DB details in sidebar ----
st.sidebar.write("### 🗂️ Database Info")
st.sidebar.write(f"📁 **Path:** `{DB_PATH}`")
st.sidebar.write(f"✅ Exists: {os.path.exists(DB_PATH)}")

if os.path.exists(DB_PATH):
    mtime = datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    st.sidebar.write(f"🕒 **Last Modified:** {mtime}")
else:
    st.sidebar.warning("⚠️ Database not found — will be created automatically.")

# ==========================================================
# ---- DATABASE HANDLING ----
# ==========================================================
lock = threading.Lock()  # ensures thread-safe writes

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)

def init_db():
    with lock:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            item_id TEXT PRIMARY KEY,
            item_name TEXT,
            category TEXT,
            quantity REAL,
            uom TEXT,
            price REAL,
            currency TEXT DEFAULT 'USD',
            reorder_level REAL DEFAULT 70.0,
            reorder_triggered INTEGER DEFAULT 0
        )
        ''')
        conn.commit()
        conn.close()

def add_or_update_item(item_id, item_name, category, quantity, uom, price, currency, reorder_level):
    with lock:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM inventory WHERE item_id=?", (item_id,))
        if c.fetchone():
            c.execute("""
                UPDATE inventory
                SET item_name=?, category=?, quantity=?, uom=?, price=?, currency=?, reorder_level=?, reorder_triggered=0
                WHERE item_id=?
            """, (item_name, category, quantity, uom, price, currency, reorder_level, item_id))
        else:
            c.execute("""
                INSERT INTO inventory (item_id, item_name, category, quantity, uom, price, currency, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, item_name, category, quantity, uom, price, currency, reorder_level))
        conn.commit()
        conn.close()

def get_inventory():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()
    return df

def update_stock(item_id, change):
    with lock:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?", (change, item_id))
        conn.commit()
        conn.close()

def delete_item(item_id):
    with lock:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM inventory WHERE item_id=?", (item_id,))
        conn.commit()
        conn.close()

def mark_ordered(item_id):
    with lock:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE inventory SET reorder_triggered = 1 WHERE item_id=?", (item_id,))
        conn.commit()
        conn.close()

def highlight_low_stock(row):
    if row['quantity'] < row['reorder_level']:
        return ['background-color: #FF9999'] * len(row)
    return [''] * len(row)

# Initialize DB once
init_db()

# ==========================================================
# ---- TABS ----
# ==========================================================
tab1, tab2, tab3 = st.tabs(["Inventory Overview", "Add / Update Item", "Stock Management"])

# ==========================================================
# ---- TAB 1: OVERVIEW ----
# ==========================================================
with tab1:
    st.subheader("📊 Current Inventory")

    if st.button("🔄 Refresh Inventory"):
        st.rerun()

    df = get_inventory()

    search_term = st.text_input("🔍 Search by Item Name or Category")
    if search_term:
        df = df[df['item_name'].str.contains(search_term, case=False) |
                df['category'].str.contains(search_term, case=False)]

    # Low-stock warning
    low_stock = df[df['quantity'] < df['reorder_level']]
    if not low_stock.empty:
        st.warning(
            "⚠️ Low Stock Alert:\n" +
            "\n".join([
                f"{row['item_name']} ({row['quantity']} {row['uom']} — threshold {row['reorder_level']})"
                for _, row in low_stock.iterrows()
            ])
        )

    if not df.empty:
        df['price'] = df.apply(lambda x: f"{x['currency']} {x['price']:.2f}", axis=1)
        st.dataframe(df.style.apply(highlight_low_stock, axis=1), use_container_width=True)
    else:
        st.info("No items in inventory yet.")

    # Summary statistics
    st.subheader("📈 Summary Statistics")
    total_items = len(df)
    total_qty = df["quantity"].sum() if not df.empty else 0
    try:
        df["numeric_price"] = pd.to_numeric(df["price"].str.replace("[^0-9.]", "", regex=True), errors="coerce")
        total_value = (df["quantity"] * df["numeric_price"]).sum()
    except Exception:
        total_value = 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Items", total_items)
    c2.metric("Total Quantity", total_qty)
    c3.metric("Total Inventory Value", f"{total_value:,.2f}" if total_value else "N/A")

    # Export option
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export Inventory to CSV", csv, "inventory_export.csv", "text/csv")

# ==========================================================
# ---- TAB 2: ADD / UPDATE ITEM ----
# ==========================================================
with tab2:
    st.subheader("➕ Add or Update Item")

    item_id = st.text_input("Item ID")
    item_name = st.text_input("Item Name")
    category = st.text_input("Category")
    quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
    uom = st.text_input("Unit of Measurement (e.g., pcs, kg)")
    price = st.number_input("Price per Unit", min_value=0.0, step=0.01)
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR"], index=3)
    reorder_level = st.number_input("Reorder Threshold", min_value=0.0, step=1.0, value=70.0)

    if st.button("💾 Save Item"):
        if item_id and item_name and uom:
            add_or_update_item(item_id, item_name, category, quantity, uom, price, currency, reorder_level)
            st.success(f"✅ Item '{item_name}' added/updated successfully!")
            st.rerun()
        else:
            st.warning("⚠️ Item ID, Name, and UOM are required.")

# ==========================================================
# ---- TAB 3: STOCK MANAGEMENT ----
# ==========================================================
with tab3:
    st.subheader("📦 Manage Stock")
    df = get_inventory()

    if df.empty:
        st.info("No items to manage yet.")
    else:
        selected_id = st.selectbox("Select Item ID", df["item_id"])
        item_row = df[df["item_id"] == selected_id].iloc[0]
        st.write(f"**Item Name:** {item_row['item_name']}")
        st.write(f"**Current Quantity:** {item_row['quantity']} {item_row['uom']}")
        st.write(f"**Reorder Threshold:** {item_row['reorder_level']}")
        st.write(f"**Reorder Triggered:** {'Yes' if item_row['reorder_triggered'] else 'No'}")

        stock_change = st.number_input("Change Quantity (+/-)", value=0.0, step=1.0)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📈 Update Stock"):
                update_stock(selected_id, stock_change)
                st.success("✅ Stock updated successfully!")
                st.rerun()
        with col2:
            if st.button("🛒 Mark as Ordered"):
                mark_ordered(selected_id)
                st.success("✅ Marked as ordered — low-stock notification stopped.")
                st.rerun()
        with col3:
            if st.button("❌ Delete Item"):
                delete_item(selected_id)
                st.success(f"Item '{item_row['item_name']}' deleted from inventory!")
                st.rerun()