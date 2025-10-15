import streamlit as st
import pandas as pd

# ---- Page Config ----
st.set_page_config(page_title="Inventory App", layout="wide")
st.title("📦 Inventory Management App")

# ---- Initialize Inventory ----
if "inventory" not in st.session_state:
    st.session_state.inventory = pd.DataFrame(
        columns=["Item ID", "Item Name", "Category", "Quantity", "Price per Unit"]
    )

# ---- Tabs Layout ----
tab1, tab2, tab3 = st.tabs(["Inventory Overview", "Add / Update Item", "Stock Management"])

# ---- Tab 1: Inventory Overview ----
with tab1:
    st.subheader("📊 Current Inventory")
    st.dataframe(st.session_state.inventory)

    st.subheader("📈 Summary Stats")
    total_items = len(st.session_state.inventory)
    total_quantity = st.session_state.inventory["Quantity"].sum() if not st.session_state.inventory.empty else 0
    total_value = (st.session_state.inventory["Quantity"] * st.session_state.inventory["Price per Unit"]).sum() if not st.session_state.inventory.empty else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", total_items)
    col2.metric("Total Quantity", total_quantity)
    col3.metric("Total Inventory Value", f"${total_value:,.2f}")

    st.subheader("🔍 Search / Filter Inventory")
    search_term = st.text_input("Search by Item Name or Category")
    if search_term:
        filtered_df = st.session_state.inventory[
            st.session_state.inventory["Item Name"].str.contains(search_term, case=False) |
            st.session_state.inventory["Category"].str.contains(search_term, case=False)
        ]
        st.dataframe(filtered_df)

    st.subheader("💾 Export Inventory")
    if st.button("Export as CSV"):
        st.session_state.inventory.to_csv("inventory.csv", index=False)
        st.success("✅ Inventory exported to 'inventory.csv'")

# ---- Tab 2: Add / Update Item ----
with tab2:
    st.subheader("➕ Add or Update Item")
    item_id = st.text_input("Item ID")
    item_name = st.text_input("Item Name")
    category = st.text_input("Category")
    quantity = st.number_input("Quantity", min_value=0, step=1)
    price = st.number_input("Price per Unit", min_value=0.0, step=0.01)

    if st.button("Add / Update Item"):
        if item_id and item_name:
            if item_id in st.session_state.inventory["Item ID"].values:
                st.session_state.inventory.loc[
                    st.session_state.inventory["Item ID"] == item_id,
                    ["Item Name", "Category", "Quantity", "Price per Unit"]
                ] = [item_name, category, quantity, price]
                st.success(f"✅ Item '{item_name}' updated successfully!")
            else:
                st.session_state.inventory = pd.concat(
                    [
                        st.session_state.inventory,
                        pd.DataFrame([[item_id, item_name, category, quantity, price]],
                                     columns=["Item ID", "Item Name", "Category", "Quantity", "Price per Unit"])
                    ],
                    ignore_index=True
                )
                st.success(f"✅ Item '{item_name}' added successfully!")
        else:
            st.warning("⚠️ Item ID and Item Name are required!")

# ---- Tab 3: Stock Management ----
with tab3:
    st.subheader("📦 Manage Stock")
    selected_id = st.selectbox("Select Item ID", st.session_state.inventory["Item ID"] if not st.session_state.inventory.empty else ["No items"])
    
    if selected_id != "No items":
        item_row = st.session_state.inventory[st.session_state.inventory["Item ID"] == selected_id].iloc[0]
        st.write(f"**Item Name:** {item_row['Item Name']}")
        st.write(f"**Current Quantity:** {item_row['Quantity']}")
        
        stock_change = st.number_input("Increase / Decrease Quantity", value=0, step=1)
        if st.button("Update Stock"):
            st.session_state.inventory.loc[
                st.session_state.inventory["Item ID"] == selected_id, "Quantity"
            ] += stock_change
            st.success(f"✅ Stock updated. New quantity: {st.session_state.inventory.loc[st.session_state.inventory['Item ID'] == selected_id, 'Quantity'].values[0]}")

    st.subheader("🗑️ Delete Item")
    delete_id = st.selectbox("Select Item ID to delete", st.session_state.inventory["Item ID"] if not st.session_state.inventory.empty else ["No items"], key="delete_id")
    if st.button("Delete Item"):
        if delete_id != "No items":
            st.session_state.inventory = st.session_state.inventory[st.session_state.inventory["Item ID"] != delete_id]
            st.success(f"🗑️ Item ID '{delete_id}' deleted successfully!")
