import os
from google.cloud import bigquery
from flask import Flask, jsonify, request

client = bigquery.Client(project=os.environ.get("PROJECT_ID"))

app = Flask(__name__)

def router(request):
    token = request.headers.get("X-Auth-Token")
    page = request.args.get('page', default=1, type=int)
    date_from = request.args.get('date_from', default='2022-01-01')
    date_to = request.args.get('date_to', default='2022-01-01')
    partner = request.args.get('partner', default='')
    customer_id = request.args.get("customer_id")

    depot_assignment = {
        "Tala": "('Syokimau','Embakasi')",
        "AIB": "('Rongai','Machakos')",
        "Nationa": "('Kiambu','Kahawa','Thika Town')" 
    }
    depot = depot_assignment.get(partner, None)

    # Exception 
    if depot is None:
        return jsonify({"message": "Missing Partner Details"}), 400
    if token is None or token not in os.environ.get("AUTH_TOKEN"):
        return jsonify({"message": "Invalid Authentication"}), 401

    # endpoints
    if request.path == "/payments":
        return get_payments(depot, date_from, date_to, page)
    elif request.path == "/deliveries":
        return get_deliveries(depot, date_from, date_to, page, customer_id)
    elif request.path == "/customers":
        return get_customers(depot, customer_id)
    elif request.path == "/repayments":
        return get_repayments(depot, date_from, date_to, page, customer_id)
    elif request.path == "/":
        return jsonify({"message": "Credit Scoring Integration Platform"}), 200
    else:
        return jsonify({"message": "Page Not Found"}), 404

# Payments
@app.route("/payments", methods=["GET"])
def get_payments(depot, date_from, date_to, page):
    try:
        page_limit = 2000
        query = '''
            WITH q AS (
                SELECT delivery_date, delivery_id, payment_date, amount_paid, payment_mode,
                CEILING(SAFE_DIVIDE(row_number() OVER (ORDER BY delivery_date, delivery_id, payment_date, amount_paid, payment_mode), @page_limit)) page
                FROM `credit_scoring.delivery_payments`
                WHERE depot_name IN UNNEST(@depot)
                AND delivery_date >= @date_from
                AND delivery_date <= @date_to
            )
            SELECT * EXCEPT(page)
            FROM q
            WHERE page = @page
        '''
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("depot", "STRING", depot),
                bigquery.ScalarQueryParameter("date_from", "STRING", date_from),
                bigquery.ScalarQueryParameter("date_to", "STRING", date_to),
                bigquery.ScalarQueryParameter("page", "INT64", page),
                bigquery.ScalarQueryParameter("page_limit", "INT64", page_limit)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        results = list(query_job.result())

        last_page = len(results) < page_limit

        data = {
            "page_number": page,
            "total_records": len(results),
            "last_page": last_page,
            "data": [dict(row) for row in results]
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Deliveries
@app.route("/deliveries", methods=["GET"])
def get_deliveries(depot, date_from, date_to, page, customer_id=None):
    page_limit = 2000
    query = '''
        WITH q as (
            SELECT 
                delivery_date, country_name, region_name, area_name, depot_id, depot_name, 
                route_id, route_name, route_plan_id, product_item_id, product_name, 
                product_type, product_category, product_item_name, product_item_segment, 
                Unique_Stalls shop_id, customer_id, shop_type, delivery_order_id order_id, 
                delivery_id, delivery_number, date_created, UoM_name, conversion_ratio, 
                uom_count, weight, amount delivery_amount,
                CEILING(SAFE_DIVIDE(row_number() OVER (ORDER BY delivery_id), {page_limit})) page
            FROM 
                `cache_finance_deliveries`
            WHERE 
                depot_name IN {depot}
                AND delivery_date >= '{date_from}'
                AND delivery_date <= '{date_to}'
    '''.format(page_limit=page_limit, depot=depot, date_from=date_from, date_to=date_to)
    
    if customer_id:
        query += "AND customer_id = '{}'".format(customer_id)
    
    query += '''
        )             
        SELECT DISTINCT
            delivery_date, country_name, region_name, area_name, depot_id, depot_name, 
            route_id, route_name, route_plan_id, product_item_id, product_name, 
            product_type, product_category, product_item_name, product_item_segment, 
            shop_id, customer_id, shop_type, order_id, 
            delivery_id, delivery_number, date_created, UoM_name, conversion_ratio, 
            uom_count, weight, delivery_amount
        FROM q
        WHERE page = {page}
    '''.format(page=page)

    query_job = client.query(query)
    results = list(query_job.result())  
    total_records = len(results)
    
    last_page = False
    if total_records < page_limit:
        last_page = True

    total_pages_query = '''
        SELECT CEILING(COUNT(*) / {page_limit}) AS total_pages
        FROM `cache_finance_deliveries`
        WHERE depot_name IN {depot}
            AND delivery_date >= '{date_from}'
            AND delivery_date <= '{date_to}'
    '''.format(page_limit=page_limit, depot=depot, date_from=date_from, date_to=date_to)

    total_pages_job = client.query(total_pages_query)
    total_pages_result = total_pages_job.result()
    total_pages = next(total_pages_result)['total_pages']

    data = {
        "page_number": page,
        "total_records": total_records,
        "total_pages": total_pages,
        "last_page": last_page,
        "data": [dict(row) for row in results]
    }
    return jsonify(data)

# customers
@app.route("/customers", methods=["GET"])
def get_customers(depot, customer_id=None):
    query = f"""
        SELECT 
            customer_id, customer_name, phone_number, latitude, longitude, depot_name
        FROM `cache_customer`
        WHERE depot_name IN {depot}
    """

    if customer_id:
        query += f" AND customer_id = '{customer_id}'"

    try:
        query_job = client.query(query)
        results = list(query_job.result())

        data = {
            "total_records": len(results),
            "data": [dict(row) for row in results]
        }

        # response
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Repayments
@app.route("/repayments", methods=["GET"])
def get_repayments(depot, date_from, date_to, page, customer_id=None):
    page_limit = 1500
    query = '''
        WITH q AS (
            SELECT 
                date_created, depot_name, route_name, shop_id, customer_id, phone_number, document_no, legal_name, 
                product_item_segment, active, rejection_reason_code, loan_type, interest_type, interest_rate, penalty_commencement_date,
                balance, repaid_amount, description, amount_paid, last_repayment_date, delivery_id, delivery_amount 
                FROM `cache_loans_mashup` 
            WHERE loan_request_id is not null and
                 depot_name IN {depot}
                AND date >= '{date_from}'
                AND date <= '{date_to}'
    '''.format(page_limit=page_limit, depot=depot, date_from=date_from, date_to=date_to)

    if customer_id:
        query += "AND customer_id = '{}' ".format(customer_id)

    query += '''
        )
        SELECT DISTINCT * FROM q ORDER BY date_created DESC
        LIMIT {} OFFSET {}
    '''.format(page_limit, (page - 1) * page_limit)

    query_job = client.query(query)
    results = list(query_job.result())
    total_records = len(results)

    last_page = False
    if total_records < page_limit:
        last_page = True

    total_pages_query = '''
    SELECT CEILING(COUNT(*) / {page_limit}) AS total_pages
        FROM `cache_lms_loans_mashup` 
    WHERE 
        depot_name IN {depot}
        AND date >= '{date_from}'
        AND date <= '{date_to}'
'''.format(page_limit=page_limit, depot=depot, date_from=date_from, date_to=date_to)

    total_pages_job = client.query(total_pages_query)
    total_pages_result = total_pages_job.result()
    total_pages = int(next(total_pages_result)['total_pages'])

    data = {
        "page_number": page,
        "total_records": total_records,
        "total_pages": total_pages,
        "last_page": last_page,
        "data": [dict(row) for row in results]
    }
    return jsonify(data)

# Bind the router function to handle requests
@app.before_request
def before_request():
    return router(request)

if __name__ == "__main__":
    app.run(debug=True)