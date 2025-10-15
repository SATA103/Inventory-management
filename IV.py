import streamlit as st
import pandas as pd
import sqlite3

# ---- Shared Database Path ----
DB_PATH = r"\\bioblrnas\msat\inventory.db"

# ---- Page Config ----
st.set_page_config(page_title="Inventory Management", layout="wide")
st.title("📦 Inventory Management (Shared Network Database)")

# ---- Database Connection ----
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ---- Table Creation ----
c.execute('''
CREATE TABLE IF NOT EXISTS inventory (
    item_id TEXT PRIMARY KEY,
    item_name TEXT,
    category TEXT,
    quantity REAL,
    price REAL
)
''')
conn.commit()

# ---- Add missing columns safely ----
def add_missing_column(table, column, col_type, default_value=None):
    c.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in c.fetchall()]
    if column not in columns:
        query = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        if default_value is not None:
            query += f" DEFAULT {default_value}"
        c.execute(query)
        conn.commit()

add_missing_column("inventory", "uom", "TEXT", "'pcs'")
add_missing_column("inventory", "reorder_level", "REAL", 70.0)
add_missing_column("inventory", "reorder_triggered", "INTEGER", 0)
add_missing_column("inventory", "currency", "TEXT", "'USD'")

# ---- Helper Functions ----
def get_inventory():
    return pd.read_sql("SELECT * FROM inventory", conn)

def add_or_update_item(item_id, item_name, category, quantity, uom, price, currency, reorder_level):
    c.execute("SELECT * FROM inventory WHERE item_id=?", (item_id,))
    if c.fetchone():
        c.execute("""
        UPDATE inventory
        SET item_name=?, category=?, quantity=?, uom=?, price=?, currency=?, reorder_triggered=0, reorder_level=?
        WHERE item_id=?
        """, (item_name, category, quantity, uom, price, currency, reorder_level, item_id))
    else:
        c.execute("""
        INSERT INTO inventory (item_id, item_name, category, quantity, uom, price, currency, reorder_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, item_name, category, quantity, uom, price, currency, reorder_level))
    conn.commit()

def update_stock(item_id, change):
    c.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?", (change, item_id))
    conn.commit()

def delete_item(item_id):
    c.execute("DELETE FROM inventory WHERE item_id=?", (item_id,))
    conn.commit()

def mark_ordered(item_id):
    c.execute("UPDATE inventory SET reorder_triggered = 1 WHERE item_id = ?", (item_id,))
    conn.commit()

# ---- Highlight Low-Stock ----
def highlight_low_stock(row):
    if row['quantity'] < row['reorder_level']:
        return ['background-color: #FF9999'] * len(row)
    else:
        return [''] * len(row)

# ---- Tabs ----
tab1, tab2, tab3 = st.tabs(["Inventory Overview", "Add / Update Item", "Stock Management"])

# ---- Tab 1: Overview ----
with tab1:
    st.subheader("📊 Current Inventory")

    if st.button("🔄 Refresh Inventory"):
        st.rerun()

    df = get_inventory()

    search_term = st.text_input("🔍 Search by Item Name or Category")
    if search_term:
        df = df[df['item_name'].str.contains(search_term, case=False) |
                df['category'].str.contains(search_term, case=False)]

    # Low-stock notification
    low_stock = df[df['quantity'] < df['reorder_level']]
    if not low_stock.empty:
        st.warning(
            "⚠️ Low Stock Alert:\n" +
            "\n".join([
                f"{row['item_name']} ({row['quantity']} {row['uom']}, threshold {row['reorder_level']})"
                for _, row in low_stock.iterrows()
            ])
        )

    # Rearrange columns: UOM after quantity
    if not df.empty:
        cols = df.columns.tolist()
        if 'uom' in cols and 'quantity' in cols:
            cols.remove('uom')
            qty_index = cols.index('quantity')
            cols.insert(qty_index + 1, 'uom')
            df = df[cols]

        # Show currency inline
        df['price'] = df.apply(lambda x: f"{x['currency']} {x['price']:.2f}", axis=1)
        st.dataframe(df.style.apply(highlight_low_stock, axis=1))
    else:
        st.info("No items in inventory yet.")

    # Summary stats
    # ---- Summary stats ----
    st.subheader("📈 Summary Statistics")
    
    total_items = len(df)
    total_qty = df["quantity"].sum() if not df.empty else 0
    
    # Safely convert price to numeric if any text slipped in
    try:
        df["numeric_price"] = pd.to_numeric(df["price"].replace({',': ''}, regex=True), errors='coerce')
        total_value = (df["quantity"] * df["numeric_price"]).sum()
    except Exception:
        total_value = 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Items", total_items)
    c2.metric("Total Quantity", total_qty)
    c3.metric("Total Inventory Value", f"{total_value:,.2f}" if total_value else "N/A")


    # Export
    if not df.empty:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export to CSV", csv, "inventory_export.csv", "text/csv")

# ---- Tab 2: Add / Update ----
with tab2:
    st.subheader("➕ Add or Update Item")

    item_id = st.text_input("Item ID")
    item_name = st.text_input("Item Name")
    category = st.text_input("Category")
    quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
    uom = st.text_input("Unit of Measurement (e.g., pcs, kg)")
    price = st.number_input("Price per Unit", min_value=0.0, step=0.01)
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR"])
    reorder_level = st.number_input("Reorder Threshold", min_value=0.0, step=1.0, value=70.0)

    if st.button("💾 Save Item"):
        if item_id and item_name and uom:
            add_or_update_item(item_id, item_name, category, quantity, uom, price, currency, reorder_level)
            st.success(f"✅ Item '{item_name}' added/updated successfully!")
        else:
            st.warning("⚠️ Item ID, Name, and UOM are required.")

# ---- Tab 3: Stock Management ----
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
        if st.button("Update Stock"):
            update_stock(selected_id, stock_change)
            st.success("✅ Stock updated successfully!")
            st.rerun()

        if st.button("Mark as Ordered"):
            mark_ordered(selected_id)
            st.success("✅ Marked as ordered — low-stock notification stopped.")
            st.rerun()

        if st.button("❌ Delete Item"):
            delete_item(selected_id)
            st.success(f"Item '{item_row['item_name']}' deleted from inventory!")
            st.rerun()