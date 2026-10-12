from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import config
from dotenv import load_dotenv
import os
import re
load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")


def get_db_connection():
    return mysql.connector.connect(
        user=config.DB_USER,
        host=config.DB_HOST,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
    )


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/signup", methods=["GET"])
def signup_page():
    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    fullname = data["fullname"]
    username = data["username"]
    email = data["email"]
    phone = data["phone"]
    password = data["password"]

    hashed_password = generate_password_hash(password=password)

    # cursor......it is a readymade function and its purpose is to connect db and mysql
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO users(fullname, username, email, phone, password)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (fullname, username, email, phone, hashed_password),
    )
    db.commit()
    cursor.close()
    return jsonify({"success": True, "message": "Account created successfully"})


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    username = data["username"]
    password = data["password"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT * FROM users
            WHERE username = %s OR email = %s
            """,
            (username, username),
        )

        user = cursor.fetchone()

        if user:

            if check_password_hash(user["password"], password):

                # Create Session
                session["user_id"] = user["id"]
                session["username"] = user["username"]

                return jsonify({"success": True, "message": "Login successful."})

        return (
            jsonify(
                {"success": False, "message": "Invalid username/email or password."}
            ),
            401,
        )

    except mysql.connector.Error as error:

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# dashbord
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("home"))

    full_name = session["username"]
    return render_template("dashboard.html", full_name=full_name)


# dashboard stats
@app.route("/api/dashboard/stats", methods=["GET"])
#  api...application program interface....it is used for communication between 2 things
def dashboard_stats():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        # for total products
        cursor.execute("""
            SELECT COUNT(*) AS total_products
            FROM products
         """)

        total_products = cursor.fetchone()["total_products"]
        # for total categories
        cursor.execute("""
            SELECT COUNT(*) AS total_categories
            FROM categories
            """)
        total_categories = cursor.fetchone()["total_categories"]
        # for total customers
        cursor.execute("""
            SELECT COUNT(*) AS total_customers
            FROM customers
            """)
        total_customers = cursor.fetchone()["total_customers"]
        # for low stock products
        cursor.execute("""
            SELECT COUNT(*) AS low_stock
            FROM products
            WHERE stock_quantity <= minimum_stock
            """)
        low_stock = cursor.fetchone()["low_stock"]
        # for today's sale
        cursor.execute("""
            SELECT 
               COALESCE(  
                   SUM(final_amount),
                   0
                ) AS today_sales
            FROM sales
            WHERE DATE(created_at) = CURDATE()    
            """)
        today_sales = cursor.fetchone()["today_sales"]
        # coalesce is used so we can use our point value as well
        # 386.9 our point value will be calculated in our amount
        #  for recent sales
        cursor.execute("""
            SELECT 
                s.id AS invoice,
                COALESCE(
                    c.customer_name,
                    'WALK-IN Customer'
                ) AS customer,
                
                DATE_FORMAT(
                    s.created_at,
                    '%d %b %Y'
                ) AS date,
                
                s.final_amount AS amount,
                
                'Completed' AS status
            
            FROM sales s 
            
            LEFT JOIN customers c
                ON s.customer_id = c.id
                
            ORDER BY s.created_at DESC
            
            LIMIT 5       
            """)
        recent_sales = cursor.fetchall()

        # LOW STOCK PRODUCTS LIST
        # ===============================

        cursor.execute("""
            SELECT
                product_name AS name,
                stock_quantity AS quantity

            FROM products

            WHERE stock_quantity <= minimum_stock

            ORDER BY stock_quantity ASC

            LIMIT 5
            """)

        low_stock_products = cursor.fetchall()

        # response
        return (
            jsonify(
                {
                    "success": True,
                    "total_products": total_products,
                    "total_categories": total_categories,
                    "total_customers": total_customers,
                    "low_stock": low_stock,
                    "today_sales": float(today_sales or 0),
                    "recent_sales": recent_sales,
                    "low_stock_products": low_stock_products,
                }
            ),
            200,
        )
    except mysql.connector.Error as error:
        print("Dashboard stats database error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while loading dashboard stats.",
                },
            ),
            500,
        )
    except Exception as error:
        # Exception means any error in app.py
        print("Dashboard stats error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Something went wrong while loading dashboard stats.",
                }
            ),
            500,
        )
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# logout
@app.route("/logout")
def logout():
    return render_template("/logout.html")


# categories page flask code
@app.route("/categories")
def categories():
    full_name = session["username"]
    return render_template("categories.html", full_name=full_name)


# Get all categories
@app.route("/api/categories", methods=["GET"])
def get_categories():
    # This route is responsible for retrieving all categories from the database.
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                name,
                description,
                status,
                created_at,
                updated_at
            FROM categories
            ORDER BY id DESC
            """)

        # DESC means order the results in descending order
        categories = cursor.fetchall()

        return jsonify({"success": True, "categories": categories}), 200
        # 200 means OK

    except mysql.connector.Error as error:
        return jsonify({"success": False, "message": str(error)}), 500
        # 500 means internal server error

    finally:
        cursor.close()
        db.close()


# Get one category
@app.route("/api/categories/<int:category_id>", methods=["GET"])
def get_category(category_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                id,
                name,
                description,
                status,
                created_at,
                updated_at
            FROM categories
            WHERE id = %s
            """,
            (category_id,),
        )

        # The comma makes it a Python tuple containing one value.
        category = cursor.fetchone()

        if not category:
            return jsonify({"success": False, "message": "Category not found."}), 404

        # 404 means not found

        return jsonify({"success": True, "category": category}), 200

    except mysql.connector.Error as error:
        return jsonify({"success": False, "message": str(error)}), 500

    finally:
        cursor.close()
        db.close()
        # GET...........database to backend and backend to frontend
        # POST..........frontend to backend and backend to database


#
# Create Category
@app.route("/api/categories", methods=["POST"])
def create_category():
    data = request.get_json()

    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    status = data.get("status", "active")

    if not name:
        return jsonify({"success": False, "message": "Category name is required."}), 400

        # 400 means bad request

    db = get_db_connection()
    cursor = db.cursor()
    # check duplicate
    try:
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE LOWER(name) = LOWER(%s)
            """,
            (name,),
        )
        # This checks whether a category with the same name already exists.

        existing_category = cursor.fetchone()

        # The database returns one matching record if it exists.
        if existing_category:

            return (
                jsonify({"success": False, "message": "Category already exists."}),
                409,
            )

            # 409 means conflict

        # Insert Category
        cursor.execute(
            """
            INSERT INTO categories
                (name, description, status)
            VALUES
                (%s, %s, %s)
            """,
            (name, description, status),
        )

        db.commit()
        # commit() permanently saves the database changes.
        cursor.lastrowid
        # Successful create response
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Category created successfully.",
                    "category_id": cursor.lastrowid,
                }
            ),
            201,
        )

        # 201 means created

    except mysql.connector.Error as error:
        db.rollback()
        return jsonify({"success": False, "message": str(error)}), 500

    finally:
        cursor.close()
        db.close()


# update category
@app.route("/api/categories/<int:category_id>", methods=["PUT"])
def update_category(category_id):
    # PUT is used when we want to update existing data.
    data = request.get_json()

    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    status = data.get("status", "active")
    # post ...first time send data from frontend to backend and then backend to db
    # put.....first fetches the data and then update that data
    if not name:
        return jsonify({"success": False, "message": "Category name is required."}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE id = %s
            """,
            (category_id,),
        )

        category = cursor.fetchone()

        if not category:
            return jsonify({"success": False, "message": "Category not found."}), 404
        # check duplicate id
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE LOWER(name) = LOWER(%s)
            AND id != %s
            """,
            (name, category_id),
        )

        duplicate = cursor.fetchone()

        if duplicate:
            # The API returns:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Another category with this name already exists.",
                    }
                ),
                409,
            )

        cursor.execute(
            """
            UPDATE categories
            SET
                name = %s,
                description = %s,
                status = %s
            WHERE id = %s
            """,
            (name, description, status, category_id),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Category updated successfully."}),
            200,
        )

    except mysql.connector.Error as error:
        db.rollback()
        return jsonify({"success": False, "message": str(error)}), 500

    finally:
        cursor.close()
        db.close()


# 58. DELETE CATEGORY
@app.route("/api/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE id = %s
            """,
            (category_id,),
        )

        category = cursor.fetchone()

        if not category:
            return jsonify({"success": False, "message": "Category not found."}), 404

        cursor.execute(
            """
            DELETE FROM categories
            WHERE id = %s
            """,
            (category_id,),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Category deleted successfully."}),
            200,
        )

    except mysql.connector.IntegrityError:
        # we cant del the thing that we are using......integrityerror

        db.rollback()

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Category cannot be deleted because it is being used by a product.",
                }
            ),
            409,
        )

    except mysql.connector.Error as error:
        return (
            jsonify(
                {
                    "success": False,
                    "message": str(error),
                }
            ),
            500,
        )

    finally:

        cursor.close()
        db.close()


# Products Page
@app.route("/products")
def products():
    if "user_id" not in session:
        return redirect(url_for("home"))
    full_name = session["username"]
    return render_template("products.html", full_name=full_name)


# Get All Products
@app.route("/api/products", methods=["GET"])
def get_products():

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            products.id,
            products.product_name,
            products.sku,
            products.category_id,
            categories.name AS category_name,
            products.purchase_price,
            products.selling_price,
            products.stock_quantity,
            products.minimum_stock,
            products.description,
            products.created_at,
            products.updated_at
        FROM products
        INNER JOIN categories
            ON products.category_id = categories.id
        ORDER BY products.id DESC
    """

    try:

        cursor.execute(query)

        products = cursor.fetchall()

        return jsonify(products), 200

    except mysql.connector.Error as error:

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# =========================
# Add Product
# =========================


@app.route("/api/products", methods=["POST"])
def add_product():

    data = request.get_json()

    product_name = data.get("product_name")
    sku = data.get("sku")
    category_id = data.get("category_id")
    purchase_price = data.get("purchase_price")
    selling_price = data.get("selling_price")
    stock_quantity = data.get("stock_quantity", 0)
    minimum_stock = data.get("minimum_stock", 5)
    description = data.get("description", "")

    # Validate required fields
    if not product_name or not sku or not category_id:

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Product name, SKU and category are required",
                }
            ),
            400,
        )

    db = get_db_connection()
    cursor = db.cursor()

    query = """
        INSERT INTO products (
            product_name,
            sku,
            category_id,
            purchase_price,
            selling_price,
            stock_quantity,
            minimum_stock,
            description
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        product_name,
        sku,
        category_id,
        purchase_price,
        selling_price,
        stock_quantity,
        minimum_stock,
        description,
    )

    try:

        cursor.execute(query, values)

        db.commit()

        product_id = cursor.lastrowid

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Product added successfully",
                    "product_id": product_id,
                }
            ),
            201,
        )

    except mysql.connector.IntegrityError:

        db.rollback()

        return jsonify({"success": False, "message": "SKU already exists"}), 409

    except mysql.connector.Error as error:

        db.rollback()

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# =========================
# Get One Product
# =========================


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            products.id,
            products.product_name,
            products.sku,
            products.category_id,
            categories.name AS category_name,
            products.purchase_price,
            products.selling_price,
            products.stock_quantity,
            products.minimum_stock,
            products.description,
            products.created_at,
            products.updated_at
        FROM products
        INNER JOIN categories
            ON products.category_id = categories.id
        WHERE products.id = %s
    """

    try:

        cursor.execute(query, (product_id,))

        product = cursor.fetchone()

        if not product:

            return jsonify({"success": False, "message": "Product not found"}), 404

        return jsonify({"success": True, "product": product}), 200

    except mysql.connector.Error as error:

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# =========================
# Update Product
# =========================


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):

    data = request.get_json()

    product_name = data.get("product_name")
    sku = data.get("sku")
    category_id = data.get("category_id")
    purchase_price = data.get("purchase_price")
    selling_price = data.get("selling_price")
    stock_quantity = data.get("stock_quantity")
    minimum_stock = data.get("minimum_stock")
    description = data.get("description", "")

    # Validate required fields
    if not product_name or not sku or not category_id:

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Product name, SKU and category are required",
                }
            ),
            400,
        )

    db = get_db_connection()
    cursor = db.cursor()

    try:

        # Check if product exists
        cursor.execute(
            """
            SELECT id
            FROM products
            WHERE id = %s
            """,
            (product_id,),
        )

        product = cursor.fetchone()

        if not product:

            return jsonify({"success": False, "message": "Product not found"}), 404

        query = """
            UPDATE products
            SET
                product_name = %s,
                sku = %s,
                category_id = %s,
                purchase_price = %s,
                selling_price = %s,
                stock_quantity = %s,
                minimum_stock = %s,
                description = %s
            WHERE id = %s
        """

        values = (
            product_name,
            sku,
            category_id,
            purchase_price,
            selling_price,
            stock_quantity,
            minimum_stock,
            description,
            product_id,
        )

        cursor.execute(query, values)

        db.commit()

        return (
            jsonify({"success": True, "message": "Product updated successfully"}),
            200,
        )

    except mysql.connector.IntegrityError:

        db.rollback()

        return jsonify({"success": False, "message": "SKU already exists"}), 409

    except mysql.connector.Error as error:

        db.rollback()

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# =========================
# Delete Product
# =========================


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):

    db = get_db_connection()
    cursor = db.cursor()

    try:

        # Check if product exists
        cursor.execute(
            """
            SELECT id
            FROM products
            WHERE id = %s
            """,
            (product_id,),
        )

        product = cursor.fetchone()

        if not product:

            return jsonify({"success": False, "message": "Product not found"}), 404

        cursor.execute(
            """
            DELETE FROM products
            WHERE id = %s
            """,
            (product_id,),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Product deleted successfully"}),
            200,
        )

    except mysql.connector.IntegrityError:

        db.rollback()

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Product cannot be deleted because it is being used",
                }
            ),
            409,
        )

    except mysql.connector.Error as error:

        db.rollback()

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        cursor.close()
        db.close()


# stock page-------------------------------------------
@app.route("/stock")
def stock():
    if "user_id" not in session:
        return redirect(url_for("/home"))
    full_name = session["username"]

    return render_template("stock.html", full_name=full_name)


# stock api
@app.route("/api/stock", methods=["GET"])
def get_stock():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
    SELECT 
        products.id,
        products.product_name,
        products.sku,
        products.category_id,
        categories.name AS category_name,
        products.stock_quantity,
        products.minimum_stock
    FROM products
    INNER JOIN categories
    ON products.category_id = categories.id
    ORDER BY products.id DESC
    """
    try:
        cursor.execute(query)
        stock = cursor.fetchall()
        return (
            jsonify(
                {"success": True, "message": "Successfully stored", "stock": stock}
            ),
            200,
        )
    except mysql.connector.Error as error:
        return jsonify({"success": False, "message": str(error)}), 500
    finally:
        db.close()
        cursor.close()


# update stock
@app.route("/api/stock/<int:product_id>", methods=["PUT"])
def update(product_id):
    data = request.get_json()
    quantity = data.get("quantity")
    action = data.get("action")

    if quantity is None:
        return jsonify({"success": False, "message": "Quantity is required"}), 400

    try:
        quantity = int(quantity)
        # explicit typecasting
    except (TypeError, ValueError):
        return (
            jsonify({"success": False, "message": "Quantity must be a valid number"}),
            400,
        )

    if quantity <= 0:
        return (
            jsonify(
                {"success": False, "message": "Quantity must be greater than zero"}
            ),
            400,
        )

    if action not in ["in", "out"]:
        return jsonify({"success": False, "message": "Invalid Stock Action"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(f"""
            SELECT
                id,
                product_name,
                stock_quantity,
            FROM products
            WHERE id = {product_id}
            """)
        product = cursor.fetchone()

        if not product:
            return jsonify({"success": False, "message": "Product not found"}), 404
        current_stock = int(product["stock_quantity"])
        # stock in
        if action == "in":
            new_stock = current_stock + quantity
            message = f"{quantity} units added successfully."
        else:
            if quantity > current_stock:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Stock out quantity cannot be greater than stock.",
                        }
                    ),
                    400,
                )
            new_stock = current_stock - quantity
            message = f"{quantity} units removed successfully."
        cursor.execute(
            """
            UPDATE products
            SET stock_quantity = %s
            WHERE id = %s
            """,
            (new_stock, product_id),
        )
        db.commit()
        return (
            jsonify({"success": True, "message": message, "new_stock": new_stock}),
            200,
        )
    except mysql.connector.Error as error:
        db.rollback()
        return jsonify({"success": False, "message": str(error)}), 500

    finally:
        db.close()
        cursor.close()


# =========================
# CUSTOMERS PAGE
# =========================


@app.route("/customers")
def customer():
    if "user_id" not in session:
        return redirect(url_for("home"))

    full_name = session["username"]

    return render_template("customers.html", full_name=full_name)


# =========================
# GET ALL CUSTOMERS
# =========================


@app.route("/api/customers", methods=["GET"])
def get_customers():

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                customer_name,
                phone,
                email,
                address,
                created_at,
                updated_at
            FROM customers
            ORDER BY id DESC
        """)

        customers = cursor.fetchall()

        return jsonify({"success": True, "customers": customers}), 200

    except mysql.connector.Error as error:

        print("Get customers error:", error)

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# =========================
# ADD CUSTOMER
# =========================


@app.route("/api/customers", methods=["POST"])
def add_customer():

    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "No customer data received."}), 400

    customer_name = data.get("customer_name", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    address = data.get("address", "").strip()

    if not customer_name:

        return jsonify({"success": False, "message": "Customer name is required."}), 400

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO customers
            (
                customer_name,
                phone,
                email,
                address
            )
            VALUES
            (%s, %s, %s, %s)
        """,
            (customer_name, phone, email, address),
        )

        db.commit()

        customer_id = cursor.lastrowid

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Customer added successfully.",
                    "customer_id": customer_id,
                }
            ),
            201,
        )

    except mysql.connector.Error as error:

        if db:
            db.rollback()

        print("Add customer error:", error)

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# =========================
# UPDATE CUSTOMER
# =========================


@app.route("/api/customers/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):

    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "No customer data received."}), 400

    customer_name = data.get("customer_name", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    address = data.get("address", "").strip()

    if not customer_name:

        return jsonify({"success": False, "message": "Customer name is required."}), 400

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Check customer exists

        cursor.execute(
            """
            SELECT id
            FROM customers
            WHERE id = %s
        """,
            (customer_id,),
        )

        customer = cursor.fetchone()

        if not customer:

            return jsonify({"success": False, "message": "Customer not found."}), 404

        # Update customer

        cursor.execute(
            """
            UPDATE customers
            SET
                customer_name = %s,
                phone = %s,
                email = %s,
                address = %s
            WHERE id = %s
        """,
            (customer_name, phone, email, address, customer_id),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Customer updated successfully."}),
            200,
        )

    except mysql.connector.Error as error:

        if db:
            db.rollback()

        print("Update customer error:", error)

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# =========================
# DELETE CUSTOMER
# =========================


@app.route("/api/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Check customer exists

        cursor.execute(
            """
            SELECT id
            FROM customers
            WHERE id = %s
        """,
            (customer_id,),
        )

        customer = cursor.fetchone()

        if not customer:

            return jsonify({"success": False, "message": "Customer not found."}), 404

        # Delete customer

        cursor.execute(
            """
            DELETE FROM customers
            WHERE id = %s
        """,
            (customer_id,),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Customer deleted successfully."}),
            200,
        )

    except mysql.connector.IntegrityError:

        if db:
            db.rollback()

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Customer cannot be deleted because it is being used by a sale.",
                }
            ),
            409,
        )

    except mysql.connector.Error as error:

        if db:
            db.rollback()

        print("Delete customer error:", error)

        return jsonify({"success": False, "message": str(error)}), 500

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# sales page
@app.route("/sales")
def sales():
    if "user_id" not in session:
        return redirect(url_for("home"))
    full_name = session["username"]
    return render_template("sales.html", full_name=full_name)


# Create sale
@app.route("/api/sales", methods=["POST"])
def create_sale():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No sale data received."}), 400
    customer_id = data.get("customer_id")
    total_amount = data.get("total_amount", 0)
    discount = data.get("discount", 0)
    final_amount = data.get("final_amount", 0)
    items = data.get("items", [])
    # validation
    if not items:
        return (
            jsonify(
                {"success": False, "message": "Sale must contain at least one product."}
            ),
            400,
        )
    try:
        total_amount = float(total_amount)
        discount = float(discount)
        final_amount = float(final_amount)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid sale amount."}), 400
    if total_amount < 0 or discount < 0 or final_amount < 0:
        return (
            jsonify({"success": False, "message": "Sale amounts cannot be negative."}),
            400,
        )
    if discount > total_amount:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Discount cannot be greater than subtotal.",
                }
            ),
            400,
        )
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Check customers
        if customer_id:
            cursor.execute(
                """
                SELECT id
                FROM customers
                WHERE id = %s
                """,
                (customer_id,),
            )
            customer = cursor.fetchone()

            if not customer:
                return (
                    jsonify({"success": False, "message": "Customer not found."}),
                    404,
                )

        checked_items = []
        calculated_total = 0

        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity")

            if not product_id or not quantity:
                db.rollback()
                return (
                    jsonify({"success": False, "message": "Invalid sale item."}),
                    400,
                )
            try:
                product_id = int(product_id)
                quantity = int(quantity)

            except (TypeError, ValueError):
                db.rollback()
                return (
                    jsonify(
                        {"success": False, "message": "Invalid product or quantity."}
                    ),
                    400,
                )
            if quantity <= 0:
                db.rollback()
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Quantity must be greater than zero.",
                        }
                    ),
                    400,
                )
            cursor.execute(
                """
                SELECT
                    id,
                    product_name,
                    selling_price,
                    stock_quantity
                FROM products
                WHERE id = %s
                FOR UPDATE
                """,
                (product_id,),
            )
            product = cursor.fetchone()
            if not product:
                db.rollback()
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Product with ID {product_id} not found.",
                        }
                    ),
                    404,
                )
            available_stock = int(product["stock_quantity"] or 0)
            if quantity > available_stock:
                db.rollback()
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Only {available_stock} units of "
                            f"{product['product_name']} are available.",
                        }
                    ),
                    400,
                )
            unit_price = float(product["selling_price"] or 0)
            subtotal = unit_price * quantity
            calculated_total += subtotal

            checked_items.append(
                {
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                }
            )

        calculated_final = calculated_total - discount
        if abs(calculated_final - final_amount) > 0.01:
            db.rollback()
            return (
                jsonify({"success": False, "message": "Sale total is invalid."}),
                400,
            )

        # Create sale
        cursor.execute(
            """
            INSERT INTO sales
                (
                    customer_id,
                    total_amount,
                    discount,
                    final_amount
                )
            VALUES
                (%s, %s, %s, %s)
            """,
            (
                customer_id,
                calculated_total,
                discount,
                calculated_final,
            ),
        )

        sale_id = cursor.lastrowid

        # CREATE SALE ITEMS
        for item in checked_items:
            cursor.execute(
                """
                INSERT INTO sale_items
                    (
                        sale_id,
                        product_id,
                        quantity,
                        unit_price,
                        subtotal
                    )
                VALUES
                    (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    item["product_id"],
                    item["quantity"],
                    item["unit_price"],
                    item["subtotal"],
                ),
            )
            # Deduct stock
            cursor.execute(
                """
                UPDATE products
                SET stock_quantity =
                    stock_quantity - %s
                WHERE id = %s
                """,
                (
                    item["quantity"],
                    item["product_id"],
                ),
            )
        db.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Sale completed successfully.",
                    "sale_id": sale_id,
                }
            ),
            201,
        )
    except mysql.connector.Error as error:
        if db:
            db.rollback()
        print("Create sale database error:", error)
        return (
            jsonify(
                {"success": False, "message": "Database error while creating sale."}
            ),
            500,
        )
    except Exception as error:
        if db:
            db.rollback()

        print("Create sale error:", error)
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Something went wrong while creating the sale.",
                }
            ),
            500,
        )
    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()


# Sales History Page
@app.route("/sales-history")
def sales_history():
    if "user_id" not in session:
        return redirect(url_for("home"))

    full_name = session["username"]

    return render_template("sales-history.html", full_name=full_name)


# Get All Sales
@app.route("/api/sales", methods=["GET"])
def get_sales():

    # Check login
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    db = None
    cursor = None

    try:
        # Connect database
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Get sales with customer names
        cursor.execute("""
            SELECT
                s.id,
                s.customer_id,
                COALESCE(c.customer_name, 'Walk-in Customer') AS customer_name,
                s.total_amount,
                s.discount,
                s.final_amount,
                s.created_at
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            ORDER BY s.created_at DESC
        """)

        sales = cursor.fetchall()

        return jsonify({"success": True, "sales": sales}), 200

    # Database error
    except mysql.connector.Error as error:
        print("Sales history database error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while loading sales history.",
                }
            ),
            500,
        )

    # Other error
    except Exception as error:
        print("Sales history error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Something went wrong while loading sales history.",
                }
            ),
            500,
        )

    # Close database
    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()


# Get Sale Details
@app.route("/api/sales/<int:sale_id>", methods=["GET"])
def get_sale_details(sale_id):

    # Check login
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    db = None
    cursor = None

    try:
        # Connect database
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Get sale information
        cursor.execute(
            """
            SELECT
                s.id,
                s.customer_id,
                COALESCE(c.customer_name, 'Walk-in Customer') AS customer_name,
                s.total_amount,
                s.discount,
                s.final_amount,
                s.created_at
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = %s
        """,
            (sale_id,),
        )

        sale = cursor.fetchone()

        if not sale:
            return jsonify({"success": False, "message": "Sale not found."}), 404

        # Get sale products
        cursor.execute(
            """
            SELECT
                si.id,
                si.product_id,
                p.product_name,
                p.sku,
                si.quantity,
                si.unit_price,
                si.subtotal
            FROM sale_items si
            INNER JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
            ORDER BY si.id ASC
        """,
            (sale_id,),
        )

        items = cursor.fetchall()

        return jsonify({"success": True, "sale": sale, "items": items}), 200

    # Database error
    except mysql.connector.Error as error:
        print("Sale details database error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while loading sale details.",
                }
            ),
            500,
        )

    # Other error
    except Exception as error:
        print("Sale details error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Something went wrong while loading sale details.",
                }
            ),
            500,
        )

    # Close database
    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()


# SETTINGS PAGE
@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect(url_for("home"))

    full_name = session.get("full_name") or session.get("username", "Admin")

    return render_template("settings.html", full_name=full_name)


# GET PROFILE
@app.route("/api/settings/profile", methods=["GET"])
def get_settings_profile():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, fullname, username, email, phone
            FROM users
            WHERE id = %s
        """,
            (session["user_id"],),
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found."}), 404

        return jsonify({"success": True, "user": user}), 200

    except mysql.connector.Error as error:
        print("Profile loading error:", error)

        return (
            jsonify(
                {"success": False, "message": "Database error while loading profile."}
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()



# UPDATE PROFILE
@app.route("/api/settings/profile", methods=["PUT"])
def update_settings_profile():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    full_name = data.get("fullName", "").strip()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()

    if not full_name or not username or not email:
        return jsonify({
            "success": False,
            "message": "Full name, username and email are required."
        }), 400

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM users
            WHERE (username = %s OR email = %s)
              AND id != %s
            LIMIT 1
        """, (username, email, session["user_id"]))

        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Username or email is already in use."
            }), 409

        cursor.execute("""
            UPDATE users
            SET fullname = %s,
                username = %s,
                email = %s,
                phone = %s
            WHERE id = %s
        """, (
            full_name,
            username,
            email,
            phone,
            session["user_id"]
        ))

        db.commit()

        session["username"] = username
        session["full_name"] = full_name

        return jsonify({
            "success": True,
            "message": "Profile updated successfully."
        }), 200

    except mysql.connector.Error as error:
        if db:
            db.rollback()

        print("Profile update database error:", error)

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500

    except Exception as error:
        if db:
            db.rollback()

        print("Profile update error:", error)

        return jsonify({
            "success": False,
            "message": "An unexpected error occurred while updating the profile."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# CHANGE PASSWORD
@app.route("/api/settings/password", methods=["PUT"])
def change_password():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    data = request.get_json(silent=True) or {}

    current_password = data.get("currentPassword", "")
    new_password = data.get("newPassword", "")
    confirm_password = data.get("confirmPassword", "")

    if not current_password or not new_password or not confirm_password:
        return (
            jsonify({"success": False, "message": "All password fields are required."}),
            400,
        )

    if new_password != confirm_password:
        return (
            jsonify({"success": False, "message": "New passwords do not match."}),
            400,
        )

    if (
        len(new_password) < 8
        or not re.search(r"[a-zA-Z]", new_password)
        or not re.search(r"[0-9]", new_password)
        or not re.search(r"[^a-zA-Z0-9]", new_password)
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "Use at least 8 characters, including a letter, "
                        "a number and a special character."
                    ),
                }
            ),
            400,
        )

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT password
            FROM users
            WHERE id = %s
        """,
            (session["user_id"],),
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found."}), 404

        if not check_password_hash(user["password"], current_password):
            return (
                jsonify(
                    {"success": False, "message": "Current password is incorrect."}
                ),
                401,
            )

        if check_password_hash(user["password"], new_password):
            return (
                jsonify(
                    {"success": False, "message": "Choose a different new password."}
                ),
                400,
            )

        password_hash = generate_password_hash(new_password)

        cursor.execute(
            """
            UPDATE users
            SET password = %s
            WHERE id = %s
        """,
            (password_hash, session["user_id"]),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Password changed successfully."}),
            200,
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()

        print("Password change error:", error)

        return (
            jsonify(
                {"success": False, "message": "Database error while changing password."}
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# GET BUSINESS SETTINGS
@app.route("/api/settings/business", methods=["GET"])
def get_business_settings():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, business_name, business_phone,
                   business_email, currency, business_address
            FROM business_settings
            ORDER BY id ASC
            LIMIT 1
        """)

        business = cursor.fetchone()

        if not business:
            return (
                jsonify({"success": False, "message": "Business settings not found."}),
                404,
            )

        return jsonify({"success": True, "business": business}), 200

    except mysql.connector.Error as error:
        print("Business settings loading error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while loading business settings.",
                }
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# UPDATE BUSINESS SETTINGS
@app.route("/api/settings/business", methods=["PUT"])
def update_business_settings():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    data = request.get_json(silent=True) or {}

    business_name = data.get("businessName", "").strip()
    business_phone = data.get("businessPhone", "").strip()
    business_email = data.get("businessEmail", "").strip()
    currency = data.get("currency", "PKR").strip()
    business_address = data.get("businessAddress", "").strip()

    if not business_name:
        return jsonify({"success": False, "message": "Business name is required."}), 400

    if business_email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", business_email):
        return (
            jsonify(
                {"success": False, "message": "Please enter a valid business email."}
            ),
            400,
        )

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT id
            FROM business_settings
            ORDER BY id ASC
            LIMIT 1
        """)

        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE business_settings
                SET business_name = %s,
                    business_phone = %s,
                    business_email = %s,
                    currency = %s,
                    business_address = %s
                WHERE id = %s
            """,
                (
                    business_name,
                    business_phone,
                    business_email,
                    currency,
                    business_address,
                    existing[0],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO business_settings (
                    business_name, business_phone,
                    business_email, currency, business_address
                )
                VALUES (%s, %s, %s, %s, %s)
            """,
                (
                    business_name,
                    business_phone,
                    business_email,
                    currency,
                    business_address,
                ),
            )

        db.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Business information updated successfully.",
                }
            ),
            200,
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()

        print("Business settings update error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while saving business settings.",
                }
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# GET USER PREFERENCES
@app.route("/api/settings/preferences", methods=["GET"])
def get_settings_preferences():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT low_stock_alerts, sales_notifications, date_format
            FROM settings_preferences
            WHERE user_id = %s
        """,
            (session["user_id"],),
        )

        preferences = cursor.fetchone()

        if not preferences:
            preferences = {
                "low_stock_alerts": 1,
                "sales_notifications": 1,
                "date_format": "DD/MM/YYYY",
            }

        return jsonify({"success": True, "preferences": preferences}), 200

    except mysql.connector.Error as error:
        print("Preferences loading error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while loading preferences.",
                }
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# UPDATE USER PREFERENCES
@app.route("/api/settings/preferences", methods=["PUT"])
def update_settings_preferences():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first."}), 401

    data = request.get_json(silent=True) or {}

    low_stock_alerts = 1 if data.get("low_stock_alerts") else 0
    sales_notifications = 1 if data.get("sales_notifications") else 0
    date_format = data.get("date_format", "DD/MM/YYYY")

    allowed_formats = {"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"}

    if date_format not in allowed_formats:
        return jsonify({"success": False, "message": "Invalid date format."}), 400

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO settings_preferences (
                user_id, low_stock_alerts,
                sales_notifications, date_format
            )
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                low_stock_alerts = VALUES(low_stock_alerts),
                sales_notifications = VALUES(sales_notifications),
                date_format = VALUES(date_format)
        """,
            (session["user_id"], low_stock_alerts, sales_notifications, date_format),
        )

        db.commit()

        return (
            jsonify({"success": True, "message": "Preferences saved successfully."}),
            200,
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()

        print("Preferences update error:", error)

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Database error while saving preferences.",
                }
            ),
            500,
        )

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


if __name__ == "__main__":
    app.run(debug=True)
