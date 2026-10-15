import streamlit as st		# Imports Streamlit to build the web UI
import sqlite3			# SQLite database driver for local storage
import pandas as pd		# Pandas for reading/writing tabular data from the DB or CSV
import datetime		# Standard library for date/time stamping
import time			# Standard library for timestamps and delays
import io			# In-memory binary streams for generating PDFs without writing to disk
import cv2			# OpenCV for image processing
import numpy as np		# NumPy; indirectly used with OpenCV frames
import re
import av
import secrets
import hashlib
import queue
from pyzbar import pyzbar	# Barcode decoding from image frames.
#from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, WebRtcMode			# Real-time webcam streaming and frame transforms in Streamlit
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode, RTCConfiguration
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer		#  PDF document and components	
from reportlab.graphics.barcode import code39, eanbc, widgets 						# Barcode widgets for generating Code 39 and EAN-13 barcodes				
from reportlab.lib.pagesizes import A4								# PDF page size constant
from reportlab.lib.styles import getSampleStyleSheet						# Basic text styles for PDF.
from reportlab.lib import colors								# Color constants for PDF styling
from reportlab.graphics.shapes import Drawing
from st_cookie import CookieManager
from datetime import timezone, timedelta
from argon2 import PasswordHasher # for password hashing

# ======================================================
# CONFIG & SETUP
# ======================================================
st.set_page_config(page_title="SuperMart POS Suite", layout="wide", page_icon="🛒")		# Sets the Streamlit page title, layout (wide), and icon (shopping cart).
DB_NAME = "inventory.db"								# Defines the SQLite file name called inventory.db that is used across the app.
pwh = PasswordHasher()
cookie_manager = CookieManager()


# ======================================================
# DATABASE MANAGER
# ======================================================

def get_conn():			# Returns a SQLite connection to the global DB file
    return sqlite3.connect(DB_NAME, check_same_thread=False)	# Allows using the connection across Streamlit’s thread model

def init_db():								# Creates all required tables and seeds a default admin user
    conn = get_conn()						# Opens DB
    c = conn.cursor()						# Opens a cursor

    # 1. Users: Users table with unique username, plaintext password (demo), role
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )""")
    

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # 2. Suppliers: Suppliers table with contact info; name is unique.
    c.execute("""CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT
    )""")

    # 3. Warehouse Stock: Warehouse inventory master table.
    # Note: item_id is TEXT to preserve leading zeros in barcodes (e.g., 012345)

    c.execute("""CREATE TABLE IF NOT EXISTS warehouse_stock (
        item_id TEXT PRIMARY key,
        barcode TEXT,
        Country_GS1 INTEGER,
        manufacturer_code INTEGER,
        product_code INTEGER,
        name TEXT,
        Product_Category TEXT,
        quantity INTEGER DEFAULT 0,
        cost_price REAL DEFAULT 0.0,
        selling_price REAL DEFAULT 0.0,
        supplier_id INTEGER,
        low_stock_threshold INTEGER DEFAULT 5,											
        expiry_date DATE,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)						
    )""")

    # 4. Store Stock: Store-front stock levels referencing warehouse item_id
    c.execute("""CREATE TABLE IF NOT EXISTS store_stock (
        item_id TEXT PRIMARY KEY,
        Product_Category TEXT,
        quantity INTEGER DEFAULT 0,
        FOREIGN KEY(item_id) REFERENCES warehouse_stock(item_id)
    )""")

    # 5. Customers
    c.execute("""CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        email TEXT,
        loyalty_points INTEGER DEFAULT 0
    )""")

    # 6. Transactions
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        item_id TEXT,
        quantity INTEGER,
        total_price REAL,
        discount_applied REAL,
        date TEXT,
        user_id INTEGER,
        customer_id INTEGER,
        receipt_ref TEXT
    )""")

    # 7. Purchase Orders: with items stored as JSON text and status
    c.execute("""CREATE TABLE IF NOT EXISTS purchase_orders (
        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE,
        supplier_id INTEGER,
        status TEXT DEFAULT 'Pending',
        date_created TEXT,
        items_json TEXT,
        total_cost REAL
    )""")

    # 7. --- Barcode persistence table ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS Barcode (
        item_id TEXT PRIMARY KEY,
        last_scanned TEXT,
        quantity INTEGER DEFAULT 0,
        FOREIGN KEY(item_id) REFERENCES warehouse_stock(item_id)
        )
    """)


    
    # 8. Persist changes and close connection.
    conn.commit()
    conn.close()


# ======================================================
#  FUNCTIONS
# ======================================================

def authenticate(username, password):											# Looks up user by username/password; returns (user_id, role) or None.
    conn = get_conn()
    c = conn.cursor()

    # The ? is a parameter placeholder. The username is supplied separately
    # to help prevent SQL injection attacks.
    c.execute("SELECT user_id, password, role FROM users WHERE username=?", (username,))
    
    # Get the first matching user from the database.
    # If no user exists with this username, fetchone() returns None.
    user = c.fetchone()
    conn.close()

    if not user:
        return None

    user_id, stored_hash, role = user

    try:
        pwh.verify(stored_hash, password)
        return (user_id, role)

    except Exception:
        return None

def create_session(user_id, hours = 8):
    """
    Generate a secure session token and store only its hash
    Return the raw token so the browser can store it later.
    """

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    now = datetime.datetime.now(timezone.utc)
    created_at = now.isoformat()
    expires_at = (now + timedelta(hours = hours)).isoformat()

    conn = get_conn()

    try:
        conn.execute(
            """
            INSERT INTO user_sessions
                (user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, token_hash, created_at, expires_at)
        )
        conn.commit()
    finally:
        conn.close()

    return token


def validate_session(token):
    """
    Validate a session token and return the associated user.
    Return None if the token is invalid, expired, or revoked.
    """
    if not isinstance(token, str) or not token:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.datetime.now(timezone.utc).isoformat()

    conn = get_conn()

    try:
        user = conn.execute(
            """
            SELECT u.user_id, u.username, u.role
            FROM user_sessions AS s
            JOIN users as u ON u.user_id = s.user_id
            WHERE s.token_hash = ?
                AND s.revoked_at IS NULL
                AND s.expires_at > ?
            """,
            (token_hash, now)
        ).fetchone()

        if user is None:
            return None

        return {
            "id": user[0],
            "name": user[1],
            "role": user[2]
        }
    finally:
        conn.close()

def revoke_session(token):
    """
    Invalidate a session so it cannot be reused.
    """
    if not isinstance(token, str) or not token:
        return

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    revoked_at = datetime.datetime.now(timezone.utc).isoformat()

    conn = get_conn()

    try:
        conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = ?
            WHERE token_hash = ?
                AND revoked_at IS NULL
            """,
            (revoked_at, token_hash)
        )
        conn.commit()
    finally:
        conn.close()



def transfer_stock(item_id, qty):
    # Moves quantity from warehouse_stock to store_stock.

    conn = get_conn()
    c = conn.cursor()

    # Reject invalid quantities.
    if qty <= 0:
        conn.close()
        return False

    # Check available warehouse quantity.
    c.execute(
        "SELECT quantity FROM warehouse_stock WHERE item_id=?",
        (item_id,)
    )

    wh_qty = c.fetchone()

    if wh_qty and wh_qty[0] >= qty:

        # Deduct from Warehouse.
        c.execute(
            "UPDATE warehouse_stock "
            "SET quantity = quantity - ? "
            "WHERE item_id=?",
            (qty, item_id)
        )

        # Add to Store.
        # If the item already exists, increase its quantity.
        c.execute(
            """
            INSERT INTO store_stock (item_id, quantity)
            VALUES (?, ?)
            ON CONFLICT(item_id)
            DO UPDATE SET quantity = quantity + ?
            """,
            (item_id, qty, qty)
        )

        conn.commit()
        success = True

    else:
        success = False

    conn.close()

    return success
# --- Barcode & PDF Logic ---

def generate_barcode_pdf(item_data, barcode_type, qty_per_item):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20, rightMargin=20)
    styles = getSampleStyleSheet()
    story = []
    table_data = []
    row = []
    
    for _ in range(qty_per_item):
        try:
            raw_id = str(item_data['id'])
            
            if barcode_type == "EAN-13":
                final_code = ean13_checksum(raw_id)
                bc = eanbc.Ean13BarcodeWidget(final_code, barHeight=30, barWidth=1)
            else:
                # FIX 1: Clean data for Code 39 (Uppercase only, valid symbols only)
                # Valid: 0-9, A-Z, space, -, ., $, /, +, %
                clean_id = re.sub(r'[^A-Z0-9\-\.\$\/\+\%\s]', '', raw_id.upper())
                
                # FIX 2: Use the widget version of Standard39 for compatibility with Drawing
                bc = widgets.BarcodeStandard39(value=clean_id, barHeight=30, barWidth=1)
            
            # Use Drawing as the Flowable container
            d = Drawing(150, 45) 
            d.add(bc)
            
            cell_content = [
                Paragraph(f"<b>{item_data['name'][:20]}</b>", styles['Normal']),
                d,
                Paragraph(f"R{item_data['price']:.2f}", styles['Normal'])
            ]
            row.append(cell_content)
        except Exception as e:
            # Logs "Invalid Barcode Data" if character set is violated
            row.append([Paragraph(f"Invalid Data: {raw_id}", styles['Normal'])])
        
        if len(row) == 3:
            table_data.append(row)
            row = []
    
    if row:
        while len(row) < 3: 
            row.append([Paragraph("", styles['Normal'])])
        table_data.append(row)

    if table_data:
        # colWidths and rowHeights ensure fixed spacing to prevent overlapping
        t = Table(table_data, colWidths=[180, 180, 180], rowHeights=[95]*len(table_data))
        t.setStyle(TableStyle([
            # REMOVED 'GRID' to eliminate borders
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            # ADDED PADDING to ensure barcodes don't touch or overlap
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t)
        doc.build(story)
        buffer.seek(0)
        return buffer
    return None

def generate_receipt_pdf(cart, subtotal, discount, total, paid, change, cashier, customer):			#Generates a simple receipt PDF					
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>SuperMart Retail</b>", styles["Title"]))
    story.append(Paragraph(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    story.append(Paragraph(f"Cashier: {cashier}", styles["Normal"]))
    if customer: story.append(Paragraph(f"Customer: {customer}", styles["Normal"]))
    story.append(Spacer(1, 10))

    data = [["Item", "Qty", "Price", "Total"]]
    for item in cart:
        data.append([
            item['name'][:25], 
            str(item['qty']), 
            f"{item['price']:.2f}", 
            f"{item['price']*item['qty']:.2f}"
        ])
    
    t = Table(data, colWidths=[220, 50, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"Subtotal: {subtotal:.2f}", styles["Normal"]))
    story.append(Paragraph(f"Discount: -{discount:.2f}", styles["Normal"]))
    story.append(Paragraph(f"<b>TOTAL: {total:.2f}</b>", styles["Heading3"]))
    story.append(Paragraph(f"Paid: {paid:.2f} | Change: {change:.2f}", styles["Normal"]))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- 1. RTC Configuration for Remote/Mobile Access ---
# This allows the video stream to work over cellular or different Wi-Fi networks.
RTC_CONFIG = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)
# --- 2. Updated Camera Processor (2026 Standards) ---
# Implementation Note: To send data back to Streamlit UI 
# from this separate thread, use a shared queue or st.session_state updates.
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self):
        # Create a queue to hold results
        self.result_queue = queue.Queue()

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        decoded_objects = pyzbar.decode(img)
        
        for obj in decoded_objects:
            barcode_data = obj.data.decode("utf-8")
            # Draw on image as you already do
            (x, y, w, h) = obj.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, barcode_data, (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # PUSH to queue for the main thread to read
            self.result_queue.put(barcode_data)
            
        return av.VideoFrame.from_ndarray(img, format="bgr24")



# ======================================================
# MAIN APPLICATION
# ======================================================


# Load browser cookies into streamlit session state.
cookie_manager.apply()
if "auth_token" not in st.session_state:
    st.session_state.auth_token = ""

# Initialize Session
if 'user' not in st.session_state: 
    st.session_state.user = None

if 'cart' not in st.session_state: 
    st.session_state.cart = []

if st.session_state.user is None:
    saved_token = st.session_state.get("auth_token","")

    if saved_token:
        restored_user = validate_session(saved_token)

        if restored_user:
            st.session_state.user = restored_user
            st.session_state.session_token = saved_token

        else:
            # revoked token.
            st.session_state.user = None
            st.session_state.session_token = None
            st.session_state.auth_token = ""
            cookie_manager.update("auth_token")

# --- LOGIN ---
if not st.session_state.user:
    st.markdown("<h1 style='text-align: center;'>🔐 SuperMart POS Login</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])

    with c2:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")

            if st.form_submit_button("Login", width="stretch"):
                user = authenticate(u, p)

                if user:
                    user_id, role = user

                    try:
                        token = create_session(user_id, hours = 8)

                        # save the token in server-side session state


                        st.session_state.session_token = token
                        st.session_state.auth_token = token

                        # set the cookie so the token can be restored after refresh.
                        cookie_manager.update("auth_token")

                        # store the authenticated user's details
                        conn = get_conn()

                        try:
                            row = conn.execute(
                                "SELECT user_id, username, role FROM users WHERE user_id = ?",
                                (user_id,)
                            ).fetchone()
                        finally:
                            conn.close()

                        if row:
                            st.session_state.user = {
                                "id": row[0],
                                "name": row[1],
                                "role": row[2]
                            }
                            st.rerun()
                        else:
                            revoke_session(token)
                            st.session_state.user = None
                            st.session_state.auth_token = ""
                            cookie_manager.update("auth_token")
                            st.error("Unable to load your user profile.")

                    except sqlite3.Error:
                        st.error("unable to create your login session")

                else:
                    st.error("Invalid credentials.")

    st.stop()

# --- SIDEBAR & NAV ---
st.sidebar.title(f"👤 {st.session_state.user['name']}")
st.sidebar.info(f"Role: {st.session_state.user['role']}")
if st.sidebar.button("Logout"):
    token = st.session_state.get("session_token")

    # Invalidate the session in SQLite
    if token:
        revoke_session(token)

    # clear the authentication state.
    st.session_state.user = None
    st.session_state.session_token = None
    st.session_state.auth_token = ""

    # Synchronize the cleared token with the browser cookie.
    cookie_manager.update("auth_token")

    st.rerun()

menu = st.sidebar.radio("Navigation", ["🛒 POS Register", "📦 Inventory", "🚚 Suppliers & PO", "📊 Reports"])

# ======================================================
# 1. POS REGISTER
# ======================================================
if menu == "🛒 POS Register":
    st.title("🛒 POS Register")
    col1, col2 = st.columns([2, 1.5])

    # LEFT: Input & Search
    with col1:
        tab_man, tab_scan = st.tabs(["🔍 Search Item (Name/ID)", "📷 Scan Barcode"])
        
        with tab_man:
            query = st.text_input("Search Name or Barcode", placeholder="Enter text...")
            if query:
                conn = get_conn()
                # Dual search logic with LEFT JOIN to warehouse
                sql = """
                    SELECT w.item_id, w.name, w.selling_price, 
                           IFNULL(s.quantity, 0) as store_qty, 
                           w.quantity as warehouse_qty
                    FROM warehouse_stock w
                    LEFT JOIN store_stock s ON w.item_id = s.item_id
                    WHERE w.name LIKE ? OR w.item_id = ?
                """
                res = pd.read_sql(sql, conn, params=(f"%{query}%", query))
                conn.close()
                
                if not res.empty:
                    # Stock Alert Logic
                    for _, row in res.iterrows():
                        if row['store_qty'] <= 0:
                            st.error(f"⚠️ {row['name']} ({row['item_id']}): No stock on store shelves, {row['warehouse_qty']} remain in the warehouse")
                        else:
                            st.info(f"✅ {row['name']}: {row['store_qty']} available on shelf")

                    sellable = res[res['store_qty'] > 0]
                    if not sellable.empty:
                        with st.form("add_to_cart_manual"):
                            sel_text = st.selectbox("Select Item", sellable['item_id'] + " - " + sellable['name'])
                            qty = st.number_input("Quantity", 1, int(row['store_qty']), 1)
                            if st.form_submit_button("Add to Cart"):
                                item_id = sel_text.split(" - ")[0]
                                row = sellable[sellable['item_id'] == item_id].iloc[0]
                                st.session_state.cart.append({'id': item_id, 'name': row['name'], 'price': row['selling_price'], 'qty': qty})
                                st.success("Added to cart!")
                                st.rerun()
                else:
                    st.warning("Item not found in system.")

        # Camera. Note: Deployment requires HTTPS for camera access
        if "cart" not in st.session_state:
            st.session_state.cart = []

        def get_scanned_code(image_file):
            """Processes camera input, resizes for speed, and decodes barcode."""
            if image_file is None:
                return None
                
            # Convert file buffer to OpenCV format
            file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
            frame = cv2.imdecode(file_bytes, 1)

            # PERFORMANCE BOOST: Resize image if it's too large
            # Standardizing to a width of 800px significantly speeds up pyzbar decoding
            height, width = frame.shape[:2]
            if width > 800:
                scaling_factor = 800 / width
                new_size = (800, int(height * scaling_factor))
                frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

            # Decode barcodes
            barcodes = pyzbar.decode(frame)
            if barcodes:
                # Return the first detected barcode data
                return barcodes[0].data.decode("utf-8")
            return None

        # --- UI LAYOUT ---
        #st.title("Inventory Scanner")

       # tab_scan, tab_cart = st.tabs(["Scanner", "View Cart"])

        with tab_scan:
            # 1. CAMERA INPUT (Replacement for WebRTC)
            # Using camera_input triggers native mobile camera autofocus/flash

            # ----RESFRESH DATA------
            if st.button("🔄 Refresh Data"):
                st.rerun()

            img_file = st.camera_input("Scan Barcode")
            scanned_result = get_scanned_code(img_file)

            # 2. STATE UPDATE & MANUAL OVERRIDE
            if scanned_result:
                conn = get_conn()
                conn.execute("UPDATE Barcode SET last_scanned=?", (scanned_result,))
                conn.commit()
                conn.close()
                st.success(f"Scanned: `{scanned_result}`")

            # Fetch last scanned for the text input (allows manual entry)
            conn = get_conn()
            row = conn.execute("SELECT last_scanned FROM Barcode").fetchone()
            conn.close()

            bc_code = st.text_input(
                "Barcode Value",
                value=row[0] if row and row[0] else ""
            ).strip()[:12]


            # 3. LOOKUP & ADD TO CART
            if bc_code:
                conn = get_conn()
                df = pd.read_sql(
                    """
                    SELECT w.item_id, w.name, w.selling_price, s.quantity store_qty
                    FROM warehouse_stock w
                    LEFT JOIN store_stock s ON w.item_id=s.item_id
                    WHERE w.item_id=?
                    """,
                    conn,
                    params=(bc_code,)
                )
                conn.close()

                if not df.empty:
                    r = df.iloc[0]
                    if r["store_qty"] is not None and r["store_qty"] > 0:
                        with st.form("add_to_cart_form", clear_on_submit=True):
                            st.write(f"**Item:** {r['name']} | **Price:** R{r['selling_price']:.2f}")
                            qty = st.number_input("Quantity", 1, int(r["store_qty"]), 1)
                            
                            if st.form_submit_button("Add to Cart"):
                                st.session_state.cart.append({
                                    "id": r["item_id"],
                                    "name": r["name"],
                                    "price": r["selling_price"],
                                    "qty": qty
                                })
                                st.toast(f"Added {r['name']} to cart!")
                    else:
                        st.error("Out of Stock")
                else:
                    st.warning("Item not found in database.")

        #with tab_cart:
            #if st.session_state.cart:
               # cart_df = pd.DataFrame(st.session_state.cart)
                #st.table(cart_df)
               # if st.button("Clear Cart"):
                    #st.session_state.cart = []
                   # st.rerun()
           # else:
                #st.info("Your cart is empty.")


    # RIGHT COLUMN: Cart & Checkout
    with col2:
        st.subheader("Current Cart")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[['name', 'qty', 'price']], width="stretch")
            
            # --- START CART ACTIONS ---
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ Clear Entire Cart", width="stretch"):
                    st.session_state.cart = []
                    st.rerun()
            with c2:
                with st.popover("❌ Remove Items", width="stretch"):
                    # Create labels for each item in the cart to handle duplicates
                    options = [f"{i}: {item['name']}" for i, item in enumerate(st.session_state.cart)]
                    to_remove = st.multiselect("Select items to remove", options)
                    if st.button("Confirm Removal"):
                        # Extract the original indices and remove in reverse order
                        indices = sorted([int(x.split(":")[0]) for x in to_remove], reverse=True)
                        for idx in indices:
                            st.session_state.cart.pop(idx)
                        st.rerun()
            # --- END CART ACTIONS ---

            subtotal = sum(i['qty'] * i['price'] for i in st.session_state.cart)
            
            # Loyalty Section
            cust_id, cust_name = None, None
            ph = st.text_input("Loyalty Phone #")
            if ph:
                conn = get_conn()
                c_res = conn.execute("SELECT customer_id, name, loyalty_points FROM customers WHERE phone=?", (ph,)).fetchone()
                conn.close()
                if c_res:
                    st.success(f"Customer: {c_res[1]} (Pts: {c_res[2]})")
                    cust_id, cust_name = c_res[0], c_res[1]
                else:
                    st.caption("New customer or incorrect number.")

            # Payment Section
            disc = st.number_input("Discount Amount", 0.0)
            total = max(0.0, subtotal - disc)
            st.metric("Total Due", f"R{total:.2f}")
            
            paid = st.number_input("Amount Received", 0.0)
            if paid >= total:
                change = paid - total
                st.write(f"Change to Return: **R{change:.2f}**")
                
                if st.button("COMPLETE TRANSACTION", type="primary", width="stretch"):
                    conn = get_conn()
                    # Generate unique reference
                    ref = f"REC-{int(time.time())}"
                    try:
                        for item in st.session_state.cart:
                            # 1. Deduct from Store Shelves
                            conn.execute("UPDATE store_stock SET quantity = quantity - ? WHERE item_id=?", (item['qty'], item['id']))
                            
                            # 2. Log Sale
                            conn.execute("""
                                INSERT INTO transactions (type, item_id, quantity, total_price, date, user_id, customer_id, receipt_ref) 
                                VALUES ('sale', ?, ?, ?, ?, ?, ?, ?)
                            """, (item['id'], item['qty'], item['qty']*item['price'], 
                                  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                  st.session_state.user['id'], cust_id, ref))
                        
                        # 3. Update Loyalty Points (1 point per dollar spent)
                        if cust_id:
                            conn.execute("UPDATE customers SET loyalty_points = loyalty_points + ? WHERE customer_id=?", (int(total), cust_id))
                        
                        conn.commit()
                        
                        # 4. Receipt
                        if "generate_receipt_pdf" in globals():
                            pdf = generate_receipt_pdf(st.session_state.cart, subtotal, disc, total, paid, change, st.session_state.user['name'], cust_name)
                            st.download_button("Download Receipt", pdf, f"receipt_{ref}.pdf")
                        
                        st.session_state.cart = [] # Clear cart
                        st.success("Transaction Complete!")
                        time.sleep(10)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Transaction Error: {e}")
                    finally:
                        conn.close()
            else:
                st.warning("Insufficient payment amount.")
        else:
            st.info("Your cart is currently empty.")


# =====================================================
# 2. INVENTORY
# =====================================================
elif menu == "📦 Inventory":
    st.title("📦 Inventory Manager")
    tabs = st.tabs(["Warehouse", "Store Front", "Transfers", "CSV Tools", "Barcodes"])
    
    with tabs[0]:
        st.subheader("Warehouse Stock")
        
        # --- REFRESH BUTTON ---
        if st.button("🔄 Refresh Data"):
            st.rerun()

        conn = get_conn()
        
        # Load current stock
        #df = pd.read_sql("SELECT * FROM warehouse_stock ORDER BY item_id DESC LIMIT 3", conn)
        #df = pd.read_sql("SELECT * FROM warehouse_stock ORDER BY item_id", conn)
        #st.dataframe(df, width="stretch")
        # Load current stock
        df = pd.read_sql("SELECT * FROM warehouse_stock ORDER BY item_id", conn)

        # 1. Select which columns to filter
        filter_columns = st.multiselect("Filter by columns:", df.columns.tolist())

        # 2. Dynamically create filters for selected columns
        filtered_df = df.copy()
        if filter_columns:
            cols = st.columns(len(filter_columns))
            for i, col_name in enumerate(filter_columns):
                unique_values = df[col_name].unique().tolist()
                with cols[i]:
                    selection = st.multiselect(f"Select {col_name}", unique_values)
                    if selection:
                        filtered_df = filtered_df[filtered_df[col_name].isin(selection)]

        # 3. Display the filtered table
        st.dataframe(filtered_df, width="stretch")


        
        # --- PART 1: ADD OR AUTO-UPDATE QUANTITY ---
        with st.expander("Add Item Manually (Auto-Updates Existing)"):
            with st.form("new_item"):
                col_a, col_b = st.columns(2)
                with col_a:
                    i_id = st.text_input("Item ID")
                    i_barcode = st.text_input("barcode")
                    i_name = st.text_input("Name")
                    i_Country_GS1 = st.text_input("Country_GS1 (Optional)", value=600)
                    i_manufacturer_code = st.text_input("manufacturer_code (Optional)", value=None)
                    i_Product_Category = st.text_input("Product_Category")
                    i_product_code = st.text_input("product_code (Optional)", value=None)
                    i_qty = st.number_input("Qty to Add", 0)
                with col_b:
                    i_cost = st.number_input("Cost", 0.0)
                    i_price = st.number_input("Price", 0.0)
                    # Set default value to None to allow blank expiry
                    i_supp = st.text_input("Supplier ID (Optional)", value=None)
                    i_exp = st.date_input("Expiry Date (Optional)",value=None)
                    i_low_stock_threshold = st.number_input("Low stock threshold (Optional)",0)
                
                if st.form_submit_button("Save Item"):
                    cursor = conn.cursor()
                    cursor.execute("SELECT quantity, cost_price, selling_price FROM warehouse_stock WHERE item_id = ?", (i_id,))
                    existing = cursor.fetchone()

                    # Convert date to string for SQLite storage
                    exp_str = str(i_exp) if i_exp else None

                    if existing:
                        # UPDATE: Add qty, update prices and optional fields
                        new_qty = existing[0] + i_qty
                        new_cost = i_cost if i_cost > 0 else existing[1]
                        new_price = i_price if i_price > 0 else existing[2]
                        
                        cursor.execute("""
                            UPDATE warehouse_stock 
                            SET barcode=?,Country_GS1 =?, manufacturer_code=?, product_code=?,quantity = ?, cost_price = ?, selling_price = ?, supplier_id = ?,low_stock_threshold=?, expiry_date = ?
                            WHERE item_id = ?
                        """, (i_barcode,i_Country_GS1,i_manufacturer_code,i_product_code, new_qty, new_cost, new_price, i_supp, i_low_stock_threshold,exp_str, i_id))
                        st.success(f"Stock Updated: {i_id}")
                    else:
                        # INSERT: Specify all 13 columns explicitly to match the 13 values provided
                        cursor.execute("""
                            INSERT INTO warehouse_stock (item_id, barcode, name,Country_GS1, manufacturer_code,Product_Category, product_code, quantity, cost_price, selling_price, supplier_id,low_stock_threshold, expiry_date)
                            VALUES (?,?, ?, ?, ?, ?, ?, ?,?,?,?,?,?)
                        """, (i_id,i_barcode, i_name,i_Country_GS1,i_manufacturer_code,i_Product_Category,i_product_code, i_qty, i_cost, i_price, i_supp,i_low_stock_threshold, exp_str))
                        st.success(f"New Item Saved: {i_id}")
                    
                    conn.commit()
                    st.rerun()

        # --- PART 2: SELECT TO MANUALLY UPDATE OR DELETE ---
        if not df.empty:
            with st.expander("Manage / Delete Existing Items"):
                selected_id = st.selectbox("Select Item ID", options=df['item_id'].tolist())
                item_row = df[df['item_id'] == selected_id].iloc[0]
                
                # 1. Setup the 3 columns for the input fields
                col_a, col_b, col_c = st.columns(3)

                # --- Column 1: Core Identifiers ---
                with col_a:
                    st.markdown("### Core Identifiers")
                    u_id = st.text_input("Edit Item ID", value=item_row['item_id'])
                    u_barcode = st.text_input("Edit barcode", value=item_row['barcode'])
                    u_name = st.text_input("Edit Name", value=item_row['name'])
                    u_Product_Category = st.text_input("Edit Category", value=item_row['Product_Category'])

                # --- Column 2: GS1 & Manufacturing ---
                with col_b:
                    st.markdown("### GS1 & Manufacturing")
                    u_Country_GS1 = st.text_input("Country_GS1", value=item_row['Country_GS1'])
                    u_manufacturer_code = st.text_input("Manufacturer Code", value=item_row['manufacturer_code'])
                    u_product_code = st.text_input("Product Code", value=item_row['product_code'])
                    u_supp = st.text_input("Supplier ID", value=str(item_row['supplier_id']) if item_row['supplier_id'] else "")

                # --- Column 3: Inventory & Pricing ---
                with col_c:
                    st.markdown("### Inventory & Pricing")
                    u_qty = st.number_input("Quantity", value=int(item_row['quantity']))
                    u_cost = st.number_input("Cost Price", value=float(item_row['cost_price']))
                    u_price = st.number_input("Selling Price", value=float(item_row['selling_price']))
                    
                    # Correct Date conversion to prevent StreamlitAPIException
                    try:
                        expiry_default = pd.to_datetime(item_row['expiry_date']).date() if item_row['expiry_date'] else datetime.today()
                    except:
                        #expiry_default = date.today()
                        expiry_default = None

                    u_exp = st.date_input("Expiry Date", value=expiry_default)

                # --- Bottom Section for Threshold and Actions ---
                u_low_stock_threshold = st.number_input("Low Stock Threshold", value=int(item_row['low_stock_threshold'] or 5))

                st.divider()

                # Create two action columns for Save and Delete
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    if st.button("💾 Apply Changes", use_container_width=True):
                        # 14 bindings to match 14 '?' placeholders
                        sql_values = (
                            u_id, u_barcode, u_name, u_Country_GS1, u_manufacturer_code, 
                            u_Product_Category, u_product_code, u_qty, u_cost, u_price, 
                            u_supp, u_low_stock_threshold, u_exp, selected_id
                        )
                        conn.execute("""UPDATE warehouse_stock SET 
                                     item_id=?, barcode=?, name=?, Country_GS1=?, 
                                     manufacturer_code=?, Product_Category=?, product_code=?, 
                                     quantity=?, cost_price=?, selling_price=?, 
                                     supplier_id=?, low_stock_threshold=?, expiry_date=?
                                     WHERE item_id=?""", sql_values)
                        conn.commit()
                        st.success(f"Item {u_id} updated successfully!")
                        st.rerun()

                with btn_col2:
                    # 1. First button click sets a flag in session state
                    if st.button("🗑️ Delete Item", use_container_width=True, type="primary"):
                        st.session_state.confirm_delete_id = selected_id

                    # 2. If the flag is set, show the confirmation UI
                    if "confirm_delete_id" in st.session_state and st.session_state.confirm_delete_id == selected_id:
                        st.warning(f"Are you sure you want to permanently delete item: {selected_id}?")
                        
                        # Display 'Yes' and 'No' buttons side-by-side
                        sub_col1, sub_col2 = st.columns(2)
                        
                        with sub_col1:
                            if st.button("✅ Yes, Delete", use_container_width=True, type="primary"):
                                conn.execute("DELETE FROM warehouse_stock WHERE item_id=?", (selected_id,))
                                conn.commit()
                                # Clear the flag so the message disappears
                                del st.session_state.confirm_delete_id 
                                st.success("Item deleted.")
                                st.rerun()
                        
                        with sub_col2:
                            if st.button("❌ Cancel", use_container_width=True):
                                # Clear the flag to hide the confirmation UI
                                del st.session_state.confirm_delete_id
                                st.rerun()



        conn.close()


    with tabs[1]:
        st.subheader("Store Stock")
        conn = get_conn()
        st.dataframe(pd.read_sql("SELECT s.item_id, w.name, s.quantity FROM store_stock s JOIN warehouse_stock w ON s.item_id=w.item_id", conn), width="stretch")
        conn.close()

    with tabs[2]:
        st.subheader("Stock Transfer")
        conn = get_conn()
        opts = pd.read_sql("SELECT item_id, name, quantity FROM warehouse_stock WHERE quantity > 0", conn)
        conn.close()
        
        if not opts.empty:
            sel = st.selectbox("Select Item", opts['item_id'].astype(str) + " - " + opts['name'])
            t_qty = st.number_input("Transfer Qty", 1)
            if st.button("Move to Store"):
                t_id = sel.split(" - ")[0]
                if transfer_stock(t_id, t_qty):
                    st.success("Transferred")
                    time.sleep(2)
                    st.rerun() 
                else:
                    st.error("Failed (Check stock)")

    with tabs[3]:
        st.subheader("CSV Tools")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Import Stock")
            mode = st.radio("Import Mode", ["Restock (Add to existing)", "Overwrite (Replace data)"])
            u_file = st.file_uploader("Upload CSV", type=['csv'])
            if u_file and st.button("Run Import"):
                try:
                    idf = pd.read_csv(u_file)
                    conn = get_conn()
                    for _, r in idf.iterrows():
                        # Basic validation
                        if 'item_id' in r and 'name' in r:
                            if mode.startswith("Restock"):
                                conn.execute("""
                                    INSERT INTO warehouse_stock (item_id,barcode, name,Country_GS1,manufacturer_code,Product_Category,product_code, quantity, cost_price, selling_price,low_stock_threshold, supplier_id,expiry_date)
                                    VALUES (?,?, ?, ?, ?, ?, ?,?,?,?,?,?,?)
                                    ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + excluded.quantity
                                """, (str(r['item_id']), r['barcode'],r['name'],r['Country_GS1'], r['manufacturer_code'], r['Product_Category'], r['product_code'],r['quantity'], r.get('cost_price',0), r.get('selling_price',0),r.get('low_stock_threshold',5), r.get('supplier_id', None),r.get('expiry_date', None)))
                            else:
                                conn.execute("INSERT OR REPLACE INTO warehouse_stock (item_id, barcode,name,Country_GS1,manufacturer_code,Product_Category,product_code,quantity, cost_price, selling_price,low_stock_threshold, supplier_id,expiry_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                            (str(r['item_id']),r['barcode'], r['name'],r['Country_GS1'], r['manufacturer_code'], r['Product_Category'], r['product_code'],r['quantity'],r.get('cost_price',0), r.get('selling_price',0),r.get('low_stock_threshold',5), r.get('supplier_id', None),r.get('expiry_date', None)))
                    conn.commit()
                    conn.close()
                    st.success("Import Successful")
                except Exception as e:
                    st.error(f"Import Failed: {e}")

        with c2:
            st.markdown("### Export")
            if st.button("Download Warehouse CSV"):
                conn = get_conn()
                csv = pd.read_sql("SELECT * FROM warehouse_stock", conn).to_csv(index=False)
                conn.close()
                st.download_button("Click to Download", csv, "warehouse.csv")

    with tabs[4]:
        st.subheader("Barcode Generation")
        conn = get_conn()
        items = pd.read_sql("SELECT item_id, name, selling_price FROM warehouse_stock", conn)
        conn.close()
        ##+ "-" + items['name']
        if not items.empty:
            # Use the row index as the internal selectbox index
            item_list = items['name'].tolist()
            selected_idx = st.selectbox(
                "Select Item", 
                range(len(item_list)), 
                format_func=lambda x: item_list[x]
            )
            
            # Directly access the correct row by index (no filter needed)
            bdata = items.iloc[selected_idx]
            bid = bdata['item_id']
            
            b_type = st.radio("Type", ["EAN-13", "Code 39"], horizontal=True)
            b_qty = st.number_input("Label Count", 1, 1000, 1)
            
            if st.button("Generate Labels"):
                # 1. Update the database
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE warehouse_stock SET barcode = ? WHERE item_id = ?", 
                    (str(bid), str(bid))
                )
                conn.commit()
                conn.close()
                
                # 2. Proceed with PDF generation
                pdf = generate_barcode_pdf(
                    {'id': bid, 'name': bdata['name'], 'price': bdata['selling_price']}, 
                    b_type, 
                    b_qty
                )
                
                if pdf:
                    st.success(f"Barcode `{bid}` saved for {bdata['name']}")
                    st.download_button("Download PDF", pdf, f"labels_{bid}.pdf")
                else:
                    st.error("Error generating PDF")





# ======================================================
# 3. SUPPLIER & PO
# ======================================================
elif menu == "🚚 Suppliers & PO":
    st.title("Supply Chain")
    t1, t2 = st.tabs(["Suppliers", "Purchase Orders"])
    
    with t1:
        with st.form("sup"):
            st.subheader("Add New Supplier")
            c1, c2 = st.columns(2)
            s_name = c1.text_input("Company Name")
            s_cont = c2.text_input("Contact Person")
            s_phone = c1.text_input("Phone Number")
            s_email = c2.text_input("Email Address")
            s_addr = st.text_area("Physical Address")
            if st.form_submit_button("Save Supplier"):

                # Validate all supplier input first.
                validation_error = validate_supplier(
                    s_name,
                    s_cont,
                    s_phone,
                    s_email,
                    s_addr
                )

                # Stop the database operation if validation fails.
                if validation_error:
                    st.error(validation_error)

                else:
                    conn = get_conn()

                    try:
                        # Insert validated supplier information.
                        # ? placeholders protect against SQL injection.
                        conn.execute(
                            """
                            INSERT INTO suppliers
                            (name, contact_person, phone, email, address)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                s_name.strip(),
                                s_cont.strip(),
                                s_phone.strip(),
                                s_email.strip(),
                                s_addr.strip()
                            )
                        )

                        conn.commit()

                        st.success("Supplier Profile Created")

                    except sqlite3.IntegrityError:
                        # The name column is UNIQUE.
                        # This catches duplicate supplier names.
                        st.error(
                            "A supplier with this company name already exists."
                        )

                    finally:
                        # Always close the database connection.
                        conn.close()
                        
    st.divider()
    conn = get_conn()

    st.subheader("Existing Suppliers")
    st.dataframe(pd.read_sql("SELECT * FROM suppliers", conn), width="stretch")

    with t2:
        st.write("Recent POs")
        conn = get_conn()
        st.dataframe(pd.read_sql("SELECT * FROM purchase_orders", conn), width="stretch")
    conn.close()

# ======================================================
# 4. REPORTS
# ======================================================
elif menu == "📊 Reports":
    st.title("Reports")
    conn = get_conn()
    
    c1, c2 = st.columns(2)
    with c1:
        st.error("Low Stock Alerts")
        st.dataframe(pd.read_sql("SELECT name, quantity FROM warehouse_stock WHERE quantity < low_stock_threshold", conn), width="stretch")
    
    with c2:
        st.success("Recent Sales")
        st.dataframe(pd.read_sql("SELECT date, total_price FROM transactions WHERE type='sale' ORDER BY date DESC LIMIT 10", conn), width="stretch")
    
    conn.close()