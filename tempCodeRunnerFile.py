from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import config
from dotenv import load_dotenv
import os

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


@app.route("/login" ,  methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data["username"]
    password = data["password"]

    # cursor......it is a readymade function and its purpose is to connect db and mysql
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT * FROM users
        WHERE username = %s OR email = %s
        """,
        (username, username),
        # SELECT * FROM users WHERE username = anaya OR email = anaya@gmail.com
    )

    user = cursor.fetchone()
    cursor.close()

    if user:
        if check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            # username["password"]..signup page password
            # password.....login page password
            return jsonify({"success": True, "message": "Login successful."})

    return jsonify({"success": False, "message": "Invalid Credentials."})


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


# # categories page flask code
# @app.route("/categories")
# def categories():
#     return render_template("categories.html")


# # Get all categories
# @app.route("/api/categories", methods=["GET"])
# def get_categories():
#     # This route is responsible for retrieving all categories from the database.
# db = get_db_connection()
# cursor = db.cursor(dictionary=True)

#     try:
#         cursor.execute("""
#             SELECT
#                 id,
#                 name,
#                 description,
#                 status,
#                 created_at,
#                 updated_at
#             FROM categories
#             ORDER BY id DESC
#             """)

#         # DESC means order the results in descending order
#         categories = cursor.fetchall()

#         return jsonify({"success": True, "categories": categories}), 200
#         # 200 means OK

#     except mysql.connector.Error as error:
#         return jsonify({"success": False, "message": str(error)}), 500
#         # 500 means internal server error

#     finally:
#         cursor.close()
#         db.close()


# # Get one category
# @app.route("/api/categories/<int:category_id>", methods=["GET"])
# def get_category(category_id):
#     db = get_db_connection()
#     cursor = db.cursor(dictionary=True)

#     try:
#         cursor.execute(
#             """
#             SELECT
#                 id,
#                 name,
#                 description,
#                 status,
#                 created_at,
#                 updated_at
#             FROM categories
#             WHERE id = %s
#             """,
#             (category_id,),
#         )

#         # The comma makes it a Python tuple containing one value.
#         category = cursor.fetchone()

#         if not category:
#             return jsonify({"success": False, "message": "Category not found."}), 404

#         # 404 means not found

#         return jsonify({"success": True, "category": category}), 200

#     except mysql.connector.Error as error:
#         return jsonify({"success": False, "message": str(error)}), 500

#     finally:
#         cursor.close()
#         db.close()


# # Create Category
# @app.route("/api/categories", methods=["POST"])
# def create_category():
#     data = request.get_json()

#     name = data.get("name", "").strip()
#     description = data.get("description", "").strip()
#     status = data.get("status", "active")

#     if not name:
#         return jsonify({"success": False, "message": "Category name is required."}), 400

#         # 400 means bad request

#     db = get_db_connection()
#     cursor = db.cursor()

#     try:
#         cursor.execute(
#             """
#             SELECT id
#             FROM categories
#             WHERE LOWER(name) = LOWER(%s)
#             """,
#             (name,),
#         )
#         # This checks whether a category with the same name already exists.

#         existing_category = cursor.fetchone()

#         # The database returns one matching record if it exists.
#         if existing_category:

#             return (
#                 jsonify({"success": False, "message": "Category already exists."}),
#                 409,
#             )

#             # 409 means conflict

#         # Insert Category
#         cursor.execute(
#             """
#             INSERT INTO categories
#                 (name, description, status)
#             VALUES
#                 (%s, %s, %s)
#             """,
#             (name, description, status),
#         )

#         db.commit()
#         # commit() permanently saves the database changes.

#         # Successful create response
#         return (
#             jsonify(
#                 {
#                     "success": True,
#                     "message": "Category created successfully.",
#                     "category_id": cursor.lastrowid,
#                 }
#             ),
#             201,
#         )

#         # 201 means created

#     except mysql.connector.Error as error:
#         db.rollback()
#         return jsonify({"success": False, "message": str(error)}), 500

#     finally:
#         cursor.close()
#         db.close()


# # update category
# @app.route("/api/categories/<int:category_id>", methods=["PUT"])
# def update_category(category_id):
#     # PUT is used when we want to update existing data.
#     data = request.get_json()

#     name = data.get("name", "").strip()
#     description = data.get("description", "").strip()
#     status = data.get("status", "active")

#     if not name:
#         return jsonify({"success": False, "message": "Category name is required."}), 400

#     db = get_db_connection()
#     cursor = db.cursor(dictionary=True)

#     try:
#         cursor.execute(
#             """
#             SELECT id
#             FROM categories
#             WHERE id = %s
#             """,
#             (category_id,),
#         )

#         category = cursor.fetchone()

#         if not category:
#             return jsonify({"success": False, "message": "Category not found."}), 404

#         cursor.execute(
#             """
#             SELECT id
#             FROM categories
#             WHERE LOWER(name) = LOWER(%s)
#             AND id != %s
#             """,
#             (name, category_id),
#         )

#         duplicate = cursor.fetchone()

#         if duplicate:
#             # The API returns:
#             return (
#                 jsonify(
#                     {
#                         "success": False,
#                         "message": "Another category with this name already exists.",
#                     }
#                 ),
#                 409,
#             )

#         cursor.execute(
#             """
#             UPDATE categories
#             SET
#                 name = %s,
#                 description = %s,
#                 status = %s
#             WHERE id = %s
#             """,
#             (name, description, status, category_id),
#         )

#         db.commit()

#         return (
#             jsonify({"success": True, "message": "Category updated successfully."}),
#             200,
#         )

#     except mysql.connector.Error as error:
#         db.rollback()
#         return jsonify({"success": False, "message": str(error)}), 500

#     finally:
#         cursor.close()
#         db.close()


# # 58. DELETE CATEGORY
# @app.route("/api/categories/<int:category_id>", methods=["DELETE"])
# def delete_category(category_id):
#     db = get_db_connection()
#     cursor = db.cursor()

#     try:
#         cursor.execute(
#             """
#             SELECT id
#             FROM categories
#             WHERE id = %s
#             """,
#             (category_id,),
#         )

#         category = cursor.fetchone()

#         if not category:
#             return jsonify({"success": False, "message": "Category not found."}), 404

#         cursor.execute(
#             """
#             DELETE FROM categories
#             WHERE id = %s
#             """,
#             (category_id,),
#         )

#         db.commit()

#         return (
#             jsonify({"success": True, "message": "Category deleted successfully."}),
#             200,
#         )

#     except mysql.connector.IntegrityError:

#         db.rollback()

#         return (
#             jsonify(
#                 {
#                     "success": False,
#                     "message": "Category cannot be deleted because it is being used by a product.",
#                 }
#             ),
#             409,
#         )

#     except mysql.connector.Error as error:
#         return (
#             jsonify(
#                 {
#                     "success": False,
#                     "message": str(error),
#                 }
#             ),
#             500,
#         )

#     finally:

#         cursor.close()
#         db.close()


if __name__ == "__main__":
    app.run(debug=True)
