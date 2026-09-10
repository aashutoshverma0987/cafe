from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time
import uuid
import json
import hmac
import hashlib
import base64
import urllib.parse
import urllib.request
import urllib.error

app = Flask(__name__)
app.secret_key = "lumo-cafe-secret-key"

# Payment & Cafe Configuration
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_lumoCafeDemoKey")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "demoSecretKey12345678")
CAFE_UPI_ID = os.environ.get("CAFE_UPI_ID", "lumocafe@upi")
CAFE_PHONE = "+916388067839"
CAFE_WHATSAPP = os.environ.get("CAFE_WHATSAPP", "916388067839")
CAFE_EMAIL = os.environ.get("CAFE_EMAIL", "lumocafe00@gmail.com")

# Admin Dashboard Credentials
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lumocafe.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def is_demo_razorpay():
    return (
        RAZORPAY_KEY_ID.startswith("rzp_test_lumo")
        or "demo" in RAZORPAY_KEY_ID.lower()
        or RAZORPAY_KEY_SECRET == "demoSecretKey12345678"
    )


def create_razorpay_order(amount_rupees, receipt_id):
    """Create a Razorpay order via REST API; demo keys use a simulated order id."""
    if is_demo_razorpay():
        return f"order_{uuid.uuid4().hex[:14]}"

    amount_paise = int(round(float(amount_rupees) * 100))
    payload = json.dumps({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt_id,
        "notes": {"cafe": "LUMO CAFE", "order_id": receipt_id}
    }).encode("utf-8")

    auth = base64.b64encode(
        f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    ).decode("utf-8")

    req = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("id") or f"order_{uuid.uuid4().hex[:14]}"
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return f"order_{uuid.uuid4().hex[:14]}"


def verify_razorpay_signature(razorpay_order_id, payment_id, signature):
    """Verify Razorpay payment signature server-side."""
    if not razorpay_order_id or not payment_id or not signature:
        return is_demo_razorpay()

    if is_demo_razorpay():
        return True

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{razorpay_order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def clean_whatsapp_number(number):
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def build_whatsapp_order_message(order_id, customer_name, customer_phone, order_type,
                                 address_or_table, items, total_amount, payment_label):
    lines = [
        "🍔 *NEW ORDER - LUMO CAFE* 🍔",
        "------------------------------------",
        f"*Order ID:* #{order_id}",
        f"*Customer:* {customer_name} ({customer_phone})",
        f"*Order Type:* {order_type}",
    ]

    if address_or_table and order_type != "Takeaway":
        lines.append(f"*Detail:* {address_or_table}")

    lines.extend([
        f"*Payment:* {payment_label} (₹{total_amount:.0f})",
        "------------------------------------",
        "*Items:*"
    ])

    for item in items:
        size = item.get("size") or item.get("item_size")
        name = item.get("name") or item.get("item_name", "Item")
        qty = int(item.get("quantity", 1))
        price = float(item.get("price") or item.get("item_price") or 0)
        size_text = f" ({size})" if size else ""
        lines.append(f"• {qty}x {name}{size_text} - ₹{price * qty:.0f}")

    lines.extend([
        "------------------------------------",
        f"*Grand Total:* ₹{total_amount:.0f}",
        "",
        "Please confirm and prepare our order. Thank you! ❤️"
    ])

    return "\n".join(lines)


def build_whatsapp_url(message):
    number = clean_whatsapp_number(CAFE_WHATSAPP)
    return f"https://wa.me/{number}?text={urllib.parse.quote(message)}"


def save_order_to_db(order_id, user_id, customer_name, customer_phone, order_type,
                     address_or_table, total_amount, payment_method, payment_status,
                     order_status, items):
    conn = get_db()
    conn.execute("""
        INSERT INTO orders (
            order_id, user_id, customer_name, customer_phone,
            order_type, address_or_table, total_amount,
            payment_method, payment_status, order_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, user_id, customer_name, customer_phone,
        order_type, address_or_table, total_amount,
        payment_method, payment_status, order_status
    ))

    for item in items:
        conn.execute("""
            INSERT INTO order_items (
                order_id, item_id, item_name, item_size, item_price, quantity
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            item.get("id", 0),
            item.get("name") or item.get("item_name", "Unknown Item"),
            item.get("size") or item.get("item_size"),
            float(item.get("price") or item.get("item_price") or 0),
            int(item.get("quantity", 1))
        ))

    conn.commit()
    conn.close()


# ============================================================
# LUMO CAFE MENU
# ============================================================

menu_items = [
    # SHAWARMA
    {"id": 1, "name": "Veg Shawarma", "category": "Shawarma", "price": 50, "emoji": "🌯", "description": "Fresh veg shawarma with creamy sauces"},
    {"id": 2, "name": "Paneer Shawarma", "category": "Shawarma", "price": 69, "emoji": "🌯", "description": "Delicious paneer shawarma with fresh fillings"},
    {"id": 3, "name": "Chicken Shawarma", "category": "Shawarma", "price": 69, "emoji": "🌯", "description": "Tender chicken shawarma with fresh fillings"},
    {"id": 4, "name": "Loaded Chicken Shawarma", "category": "Shawarma", "price": 79, "emoji": "🌯", "description": "Loaded chicken shawarma packed with flavour"},
    {"id": 5, "name": "Cheese Chicken Shawarma", "category": "Shawarma", "price": 89, "emoji": "🌯", "description": "Chicken shawarma finished with extra cheese"},

    # BURGERS
    {"id": 6, "name": "Aloo Tikki Burger", "category": "Burgers", "price": 39, "emoji": "🍔", "description": "Crispy aloo tikki burger with fresh vegetables"},
    {"id": 7, "name": "Cheese Burger", "category": "Burgers", "price": 49, "emoji": "🍔", "description": "Classic burger loaded with cheese"},
    {"id": 8, "name": "Paneer Burger", "category": "Burgers", "price": 59, "emoji": "🍔", "description": "Delicious paneer burger with fresh veggies"},
    {"id": 9, "name": "Tandoori Burger", "category": "Burgers", "price": 59, "emoji": "🍔", "description": "Tandoori flavoured burger with a smoky kick"},
    {"id": 10, "name": "Chicken Burger", "category": "Burgers", "price": 60, "emoji": "🍔", "description": "Juicy chicken burger with fresh toppings"},
    {"id": 11, "name": "Grilled Chicken Burger", "category": "Burgers", "price": 99, "emoji": "🍔", "description": "Grilled chicken burger with premium toppings"},

    # SANDWICHES
    {"id": 12, "name": "Veg Sandwich", "category": "Sandwiches", "price": 39, "emoji": "🥪", "description": "Fresh vegetable sandwich"},
    {"id": 13, "name": "Chicken Sandwich", "category": "Sandwiches", "price": 69, "emoji": "🥪", "description": "Tasty chicken sandwich"},
    {"id": 14, "name": "Grilled Veg Sandwich", "category": "Sandwiches", "price": 59, "emoji": "🥪", "description": "Crispy grilled vegetable sandwich"},
    {"id": 15, "name": "Chicken Sandwich Grilled", "category": "Sandwiches", "price": 79, "emoji": "🥪", "description": "Grilled chicken sandwich with fresh fillings"},
    {"id": 16, "name": "Paneer Sandwich", "category": "Sandwiches", "price": 69, "emoji": "🥪", "description": "Creamy paneer sandwich"},
    {"id": 17, "name": "Paneer Sandwich Grilled", "category": "Sandwiches", "price": 79, "emoji": "🥪", "description": "Crispy grilled paneer sandwich"},

    # FRIES
    {"id": 18, "name": "French Fries", "category": "Fries", "price": 29, "emoji": "🍟", "description": "Crispy golden french fries"},
    {"id": 19, "name": "Peri Peri Fries", "category": "Fries", "price": 39, "emoji": "🍟", "description": "Crispy fries with peri peri seasoning"},

    # MAGGIE
    {"id": 20, "name": "Classic Maggie", "category": "Maggie", "price": 40, "emoji": "🍜", "description": "Hot and comforting classic Maggie"},
    {"id": 21, "name": "Cheese Maggie", "category": "Maggie", "price": 60, "emoji": "🍜", "description": "Classic Maggie topped with melted cheese"},

    # PIZZA
    {"id": 22, "name": "Onion Pizza", "category": "Pizza", "emoji": "🍕", "description": "Fresh onion topped pizza", "sizes": {"Regular": 59, "Medium": 89}},
    {"id": 23, "name": "Tomato Pizza", "category": "Pizza", "emoji": "🍕", "description": "Fresh tomato topped pizza", "sizes": {"Regular": 59, "Medium": 89}},
    {"id": 24, "name": "Capsicum Pizza", "category": "Pizza", "emoji": "🍕", "description": "Fresh capsicum topped pizza", "sizes": {"Regular": 59, "Medium": 89}},
    {"id": 25, "name": "Paneer Pizza", "category": "Pizza", "emoji": "🍕", "description": "Delicious paneer loaded pizza", "sizes": {"Regular": 69, "Medium": 119}},
    {"id": 26, "name": "Sweet Corn Pizza", "category": "Pizza", "emoji": "🍕", "description": "Sweet corn loaded pizza", "sizes": {"Regular": 69, "Medium": 109}},
    {"id": 27, "name": "Chicken Pizza", "category": "Pizza", "emoji": "🍕", "description": "Chicken loaded pizza", "sizes": {"Regular": 110, "Medium": 189}},

    # ADD-ONS
    {"id": 28, "name": "Extra Cheese", "category": "Add-ons", "price": 20, "emoji": "🧀", "description": "Extra cheese for your favourite food"},

    # BEVERAGES
    {"id": 29, "name": "Hot Coffee", "category": "Beverages", "price": 30, "emoji": "☕", "description": "Fresh hot coffee"},
    {"id": 30, "name": "Black Coffee", "category": "Beverages", "price": 30, "emoji": "☕", "description": "Strong and refreshing black coffee"},
    {"id": 31, "name": "Chai", "category": "Beverages", "price": 20, "emoji": "🍵", "description": "Classic hot chai"},
    {"id": 32, "name": "Cold Coffee", "category": "Beverages", "price": 40, "emoji": "🥤", "description": "Chilled creamy cold coffee"},
    {"id": 33, "name": "Cold Coffee with Ice Cream", "category": "Beverages", "price": 50, "emoji": "🥤", "description": "Cold coffee topped with ice cream"},
    {"id": 34, "name": "Oreo Shake", "category": "Beverages", "price": 69, "emoji": "🥤", "description": "Creamy Oreo shake"},
    {"id": 35, "name": "KitKat Shake", "category": "Beverages", "price": 79, "emoji": "🥤", "description": "Rich KitKat shake"},
    {"id": 36, "name": "Cold Drinks", "category": "Beverages", "price": None, "price_label": "MRP", "emoji": "🥤", "description": "Assorted chilled cold drinks"},
    {"id": 37, "name": "Mineral Water", "category": "Beverages", "price": None, "price_label": "MRP", "emoji": "💧", "description": "Chilled packaged mineral water"},

    # ICE CREAM
    {"id": 38, "name": "Vanilla Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🍦", "description": "Classic creamy vanilla"},
    {"id": 39, "name": "Chocolate Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🍨", "description": "Rich chocolate flavour"},
    {"id": 40, "name": "Strawberry Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🍓", "description": "Sweet strawberry flavour"},
    {"id": 41, "name": "Butterscotch Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🍨", "description": "Creamy butterscotch flavour"},
    {"id": 42, "name": "Mango Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🥭", "description": "Refreshing mango flavour"},
    {"id": 43, "name": "Mint Chocolate Ice Cream", "category": "Ice Cream", "price": 20, "emoji": "🍨", "description": "Mint and chocolate combination"},

    # CONES
    {"id": 44, "name": "Single Cone", "category": "Cones", "price": 20, "emoji": "🍦", "description": "Classic single scoop cone"},
    {"id": 45, "name": "Double Cone", "category": "Cones", "price": 40, "emoji": "🍦", "description": "Double scoop cone"},
    {"id": 46, "name": "Capsicum Cone", "category": "Cones", "price": 59, "emoji": "🍦", "description": "Special capsicum flavoured cone"},
    {"id": 47, "name": "Paneer Cone", "category": "Cones", "price": 69, "emoji": "🍦", "description": "Special paneer cone"},
    {"id": 48, "name": "Loaded Cone", "category": "Cones", "price": 79, "emoji": "🍦", "description": "Loaded cone with delicious toppings"},

    # SUNDAES
    {"id": 49, "name": "Chocolate Sundae", "category": "Sundaes", "price": 49, "emoji": "🍨", "description": "Chocolate sundae with rich toppings"},
    {"id": 50, "name": "Strawberry Sundae", "category": "Sundaes", "price": 49, "emoji": "🍓", "description": "Strawberry sundae"},
    {"id": 51, "name": "Butterscotch Sundae", "category": "Sundaes", "price": 49, "emoji": "🍨", "description": "Creamy butterscotch sundae"},
    {"id": 52, "name": "Mango Sundae", "category": "Sundaes", "price": 49, "emoji": "🥭", "description": "Refreshing mango sundae"},
    {"id": 53, "name": "Oreo Sundae", "category": "Sundaes", "price": 59, "emoji": "🍨", "description": "Oreo loaded sundae"},

    # ICE CREAM COMBOS
    {"id": 54, "name": "Cone + Scoop", "category": "Ice Cream Combos", "price": 35, "emoji": "🍦", "description": "A crispy cone with a scoop of ice cream"},
    {"id": 55, "name": "Cone + Sundae", "category": "Ice Cream Combos", "price": 69, "emoji": "🍨", "description": "Cone paired with a delicious sundae"},
    {"id": 56, "name": "Scoop + Shake", "category": "Ice Cream Combos", "price": 69, "emoji": "🥤", "description": "Ice cream scoop with a creamy shake"},
    {"id": 57, "name": "Sundae + Shake", "category": "Ice Cream Combos", "price": 89, "emoji": "🍨", "description": "Sundae paired with a creamy shake"},
]

# ============================================================
# DATABASE
# ============================================================

DATABASE = "lumo_cafe.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            order_type TEXT NOT NULL,
            address_or_table TEXT,
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_status TEXT NOT NULL,
            payment_id TEXT,
            order_status TEXT DEFAULT 'received',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            item_size TEXT,
            item_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
    """)
    conn.commit()
    conn.close()

# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():
    return render_template(
        "index.html",
        menu_items=menu_items,
        razorpay_key_id=RAZORPAY_KEY_ID,
        cafe_upi_id=CAFE_UPI_ID,
        cafe_phone=CAFE_PHONE,
        cafe_whatsapp=CAFE_WHATSAPP
    )

# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Check empty fields
        if not email or not password:

            return render_template(
                "login.html",
                error="Please enter email and password."
            )

        # Find user
        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        # User doesn't exist
        if user is None:

            return render_template(
                "login.html",
                error="No account found with this email."
            )

        # Check password
        if not check_password_hash(
            user["password"],
            password
        ):

            return render_template(
                "login.html",
                error="Incorrect password."
            )

        # Login successful
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return redirect(url_for("home"))

    return render_template("login.html")

# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))

# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validation

        if not name or not email or not password:

            return render_template(
                "register.html",
                error="All fields are required."
            )

        if len(password) < 6:

            return render_template(
                "register.html",
                error="Password must be at least 6 characters."
            )

        # Password hash

        hashed_password = generate_password_hash(password)

        try:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            return render_template(
                "register.html",
                error="This email is already registered."
            )

    return render_template("register.html")

# ============================================================
# PAYMENT & ORDER APIS
# ============================================================

@app.route("/api/create-order", methods=["POST"])
def create_order():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "Invalid order data"}), 400

        customer_name = data.get("customer_name", "").strip()
        customer_phone = data.get("customer_phone", "").strip()
        order_type = data.get("order_type", "Dine-in")
        address_or_table = data.get("address_or_table", "").strip()
        payment_method = data.get("payment_method", "upi_qr")
        items = data.get("items", [])

        if not customer_name or not customer_phone:
            return jsonify({"success": False, "error": "Name and phone number are required"}), 400

        if not items or len(items) == 0:
            return jsonify({"success": False, "error": "Cart is empty"}), 400

        # Calculate total amount
        total_amount = 0
        for item in items:
            price = float(item.get("price", 0))
            qty = int(item.get("quantity", 1))
            total_amount += price * qty

        if total_amount <= 0:
            return jsonify({"success": False, "error": "Invalid order total"}), 400

        # Unique Order ID
        order_id = f"LUMO-{int(time.time()):X}"
        user_id = session.get("user_id")

        # Initial Status
        if payment_method == "cash":
            payment_status = "pending"
            order_status = "confirmed"
        else:
            payment_status = "pending"
            order_status = "awaiting_payment"

        # Generate UPI payment URI for direct scan
        upi_uri = f"upi://pay?pa={CAFE_UPI_ID}&pn=LUMO%20CAFE&am={total_amount:.2f}&cu=INR&tn=Order%20{order_id}"

        # Create Razorpay order via API (or demo fallback)
        razorpay_order_id = create_razorpay_order(total_amount, order_id)

        save_order_to_db(
            order_id, user_id, customer_name, customer_phone,
            order_type, address_or_table, total_amount,
            payment_method, payment_status, order_status, items
        )

        whatsapp_message = build_whatsapp_order_message(
            order_id, customer_name, customer_phone, order_type,
            address_or_table, items, total_amount,
            "PENDING" if payment_method != "cash" else "PAY AT COUNTER"
        )

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "upi_uri": upi_uri,
            "cafe_upi_id": CAFE_UPI_ID,
            "razorpay_key_id": RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order_id,
            "whatsapp_url": build_whatsapp_url(whatsapp_message),
            "message": "Order created successfully"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "Invalid request"}), 400

        order_id = data.get("order_id")
        payment_id = data.get("payment_id", f"PAY-{int(time.time()):X}")
        payment_method = data.get("payment_method", "online")
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature")

        if not order_id:
            return jsonify({"success": False, "error": "Order ID is required"}), 400

        if payment_method == "razorpay" and razorpay_order_id and razorpay_signature:
            if not verify_razorpay_signature(razorpay_order_id, payment_id, razorpay_signature):
                return jsonify({"success": False, "error": "Payment verification failed. Invalid signature."}), 400

        conn = get_db()
        order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not order:
            conn.close()
            return jsonify({"success": False, "error": "Order not found"}), 404

        conn.execute("""
            UPDATE orders
            SET payment_status = 'paid',
                payment_id = ?,
                order_status = 'confirmed'
            WHERE order_id = ?
        """, (payment_id, order_id))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Payment verified and order confirmed!",
            "order_id": order_id,
            "payment_id": payment_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/whatsapp-order", methods=["POST"])
def whatsapp_order():
    """Save a WhatsApp order to the database and return a pre-filled WhatsApp link."""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "Invalid order data"}), 400

        customer_name = data.get("customer_name", "").strip()
        customer_phone = data.get("customer_phone", "").strip()
        order_type = data.get("order_type", "Takeaway")
        address_or_table = data.get("address_or_table", "WhatsApp Order").strip()
        items = data.get("items", [])

        if not customer_name or not customer_phone:
            return jsonify({"success": False, "error": "Name and phone number are required"}), 400

        if not items:
            return jsonify({"success": False, "error": "Cart is empty"}), 400

        total_amount = sum(
            float(item.get("price", 0)) * int(item.get("quantity", 1))
            for item in items
        )

        if total_amount <= 0:
            return jsonify({"success": False, "error": "Invalid order total"}), 400

        order_id = f"LUMO-{int(time.time()):X}"
        user_id = session.get("user_id")

        save_order_to_db(
            order_id, user_id, customer_name, customer_phone,
            order_type, address_or_table, total_amount,
            "whatsapp", "pending", "received", items
        )

        message = build_whatsapp_order_message(
            order_id, customer_name, customer_phone, order_type,
            address_or_table, items, total_amount, "WHATSAPP ORDER"
        )

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total_amount": total_amount,
            "whatsapp_url": build_whatsapp_url(message),
            "message": "WhatsApp order saved. Opening chat..."
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/order-details/<order_id>", methods=["GET"])
def get_order_details(order_id):
    try:
        conn = get_db()
        order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not order:
            conn.close()
            return jsonify({"success": False, "error": "Order not found"}), 404

        items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        conn.close()

        order_dict = dict(order)
        items_list = [dict(item) for item in items]

        return jsonify({
            "success": True,
            "order": order_dict,
            "items": items_list
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# ADMIN AUTHENTICATION & DASHBOARD
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_email"] = email
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin.html", login_error="Invalid admin email or password.", show_login=True)

    return render_template("admin.html", show_login=True)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    orders_rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    
    orders = []
    total_revenue = 0
    today_revenue = 0
    total_orders = len(orders_rows)
    today_orders = 0
    active_orders = 0
    completed_orders = 0

    today_str = time.strftime("%Y-%m-%d")

    for row in orders_rows:
        order = dict(row)
        items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order["order_id"],)).fetchall()
        order["items"] = [dict(item) for item in items]

        amount = float(order.get("total_amount") or 0)
        order_time = str(order.get("created_at") or "")
        is_today = today_str in order_time

        if order.get("payment_status") == "paid":
            total_revenue += amount
            if is_today:
                today_revenue += amount

        if is_today:
            today_orders += 1

        status = order.get("order_status", "received")
        if status in ("received", "preparing", "ready", "awaiting_payment"):
            active_orders += 1
        elif status == "completed":
            completed_orders += 1

        orders.append(order)

    conn.close()

    stats = {
        "total_revenue": int(total_revenue),
        "today_revenue": int(today_revenue),
        "total_orders": total_orders,
        "today_orders": today_orders,
        "active_orders": active_orders,
        "completed_orders": completed_orders
    }

    return render_template(
        "admin.html",
        show_login=False,
        orders=orders,
        stats=stats,
        cafe_phone=CAFE_PHONE,
        cafe_whatsapp=CAFE_WHATSAPP
    )


@app.route("/api/admin/orders")
def api_admin_orders():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = get_db()
    orders_rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    orders = []
    for row in orders_rows:
        order = dict(row)
        items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order["order_id"],)).fetchall()
        order["items"] = [dict(item) for item in items]
        orders.append(order)
    conn.close()

    return jsonify({"success": True, "orders": orders})


@app.route("/api/admin/update-status", methods=["POST"])
def api_admin_update_status():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    order_id = data.get("order_id")
    new_status = data.get("status")

    valid_statuses = ["received", "preparing", "ready", "completed", "cancelled"]
    if not order_id or new_status not in valid_statuses:
        return jsonify({"success": False, "error": "Invalid order or status"}), 400

    conn = get_db()
    conn.execute("UPDATE orders SET order_status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Order status updated to {new_status}"})


@app.route("/api/admin/update-payment", methods=["POST"])
def api_admin_update_payment():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    order_id = data.get("order_id")
    new_payment_status = data.get("payment_status")

    if not order_id or new_payment_status not in ["paid", "pending"]:
        return jsonify({"success": False, "error": "Invalid order or payment status"}), 400

    conn = get_db()
    conn.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", (new_payment_status, order_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Payment status updated to {new_payment_status}"})

# ============================================================
# RUN APPLICATION
# ============================================================
if __name__ == "__main__":

    init_db()

    app.run()
