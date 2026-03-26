#!/usr/bin/env bash
# seed_demo_data.sh — Populate Forge with a demo tenant, database, tables, and sample data
#
# Usage:
#   ./scripts/seed_demo_data.sh
#
# Prerequisites:
#   - kubectl configured with access to the cluster
#   - forge-platform running in forge-platform namespace
#   - Admin API key stored in K8s Secret forge-admin-key
#
# This script creates:
#   - Tenant: "acme-corp" (Acme Corporation)
#   - Database: "crm"
#   - Tables: customers, contacts, products, orders, order_items
#   - Sample data: 5 customers, 10 contacts, 6 products, 8 orders, 15 order items
#   - Tenant API key for portal access
#
# Output: prints the tenant API key at the end for portal login

set -euo pipefail

POD=$(kubectl get pod -n forge-platform -l app.kubernetes.io/name=forge-platform -o jsonpath='{.items[0].metadata.name}')
KEY=$(kubectl get secret forge-admin-key -n forge-platform -o jsonpath='{.data.api-key}' | base64 -d)

API="http://localhost:8000"

run() {
  kubectl exec -n forge-platform "$POD" -- curl -s -X "$1" "${API}$2" \
    -H "X-API-Key: $KEY" \
    -H "Content-Type: application/json" \
    ${3:+-d "$3"}
}

extract_id() {
  python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"
}

echo "=== Creating tenant ==="
TID=$(run POST /tenants '{"name":"acme-corp","display_name":"Acme Corporation"}' | extract_id)
echo "Tenant: $TID"

echo "=== Creating database ==="
DID=$(run POST "/tenants/$TID/databases" '{"name":"crm"}' | extract_id)
echo "Database: $DID"

TB="/tenants/$TID/databases/$DID/tables"

echo "=== Creating tables ==="

# Customers
run POST "$TB" '{"name":"customers","display_field":"company_name","columns":[
  {"name":"company_name","type":"text","nullable":false},
  {"name":"industry","type":"text","nullable":true},
  {"name":"website","type":"text","nullable":true},
  {"name":"annual_revenue","type":"decimal","nullable":true},
  {"name":"is_active","type":"boolean","nullable":false,"default":"true"}
]}'
echo " -> customers"

# Contacts (references customers)
run POST "$TB" '{"name":"contacts","display_field":"full_name","columns":[
  {"name":"full_name","type":"text","nullable":false},
  {"name":"email","type":"text","nullable":false,"unique":true},
  {"name":"phone","type":"text","nullable":true},
  {"name":"job_title","type":"text","nullable":true},
  {"name":"customer_id","type":"reference","reference_table":"customers"}
]}'
echo " -> contacts"

# Products
run POST "$TB" '{"name":"products","display_field":"product_name","columns":[
  {"name":"product_name","type":"text","nullable":false},
  {"name":"sku","type":"text","nullable":false,"unique":true},
  {"name":"price","type":"decimal","nullable":false},
  {"name":"category","type":"text","nullable":true},
  {"name":"in_stock","type":"boolean","nullable":false,"default":"true"}
]}'
echo " -> products"

# Orders (references customers)
run POST "$TB" '{"name":"orders","columns":[
  {"name":"order_date","type":"date","nullable":false},
  {"name":"status","type":"text","nullable":false},
  {"name":"total_amount","type":"decimal","nullable":true},
  {"name":"customer_id","type":"reference","reference_table":"customers"}
]}'
echo " -> orders"

# Order Items (references orders and products)
run POST "$TB" '{"name":"order_items","columns":[
  {"name":"quantity","type":"integer","nullable":false},
  {"name":"unit_price","type":"decimal","nullable":false},
  {"name":"order_id","type":"reference","reference_table":"orders"},
  {"name":"product_id","type":"reference","reference_table":"products"}
]}'
echo " -> order_items"

echo ""
echo "=== Inserting sample data ==="

R="/tenants/$TID/databases/$DID/tables"

# Customers
run POST "$R/customers/rows/batch" '{"rows":[
  {"company_name":"Globex Corporation","industry":"Manufacturing","website":"globex.com","annual_revenue":5000000,"is_active":true},
  {"company_name":"Initech","industry":"Technology","website":"initech.com","annual_revenue":2500000,"is_active":true},
  {"company_name":"Umbrella Corp","industry":"Pharmaceuticals","website":"umbrella.co","annual_revenue":12000000,"is_active":true},
  {"company_name":"Stark Industries","industry":"Defense","website":"stark.com","annual_revenue":50000000,"is_active":true},
  {"company_name":"Dunder Mifflin","industry":"Paper","website":"dundermifflin.com","annual_revenue":800000,"is_active":false}
]}'
echo " -> 5 customers"

# Contacts
run POST "$R/contacts/rows/batch" '{"rows":[
  {"full_name":"Hank Scorpio","email":"hank@globex.com","phone":"555-0101","job_title":"CEO","customer_id":1},
  {"full_name":"Frank Grimes","email":"frank@globex.com","phone":"555-0102","job_title":"Engineer","customer_id":1},
  {"full_name":"Bill Lumbergh","email":"bill@initech.com","phone":"555-0201","job_title":"VP","customer_id":2},
  {"full_name":"Peter Gibbons","email":"peter@initech.com","phone":"555-0202","job_title":"Developer","customer_id":2},
  {"full_name":"Albert Wesker","email":"wesker@umbrella.co","phone":"555-0301","job_title":"Director","customer_id":3},
  {"full_name":"Jill Valentine","email":"jill@umbrella.co","phone":"555-0302","job_title":"Agent","customer_id":3},
  {"full_name":"Tony Stark","email":"tony@stark.com","phone":"555-0401","job_title":"CEO","customer_id":4},
  {"full_name":"Pepper Potts","email":"pepper@stark.com","phone":"555-0402","job_title":"COO","customer_id":4},
  {"full_name":"Michael Scott","email":"michael@dundermifflin.com","phone":"555-0501","job_title":"Regional Manager","customer_id":5},
  {"full_name":"Dwight Schrute","email":"dwight@dundermifflin.com","phone":"555-0502","job_title":"Assistant to the RM","customer_id":5}
]}'
echo " -> 10 contacts"

# Products
run POST "$R/products/rows/batch" '{"rows":[
  {"product_name":"Widget Pro","sku":"WGT-001","price":49.99,"category":"Widgets","in_stock":true},
  {"product_name":"Widget Basic","sku":"WGT-002","price":19.99,"category":"Widgets","in_stock":true},
  {"product_name":"Gizmo Deluxe","sku":"GZM-001","price":149.99,"category":"Gizmos","in_stock":true},
  {"product_name":"Gizmo Lite","sku":"GZM-002","price":79.99,"category":"Gizmos","in_stock":false},
  {"product_name":"Doohickey Standard","sku":"DHK-001","price":9.99,"category":"Accessories","in_stock":true},
  {"product_name":"Thingamajig XL","sku":"THG-001","price":299.99,"category":"Premium","in_stock":true}
]}'
echo " -> 6 products"

# Orders
run POST "$R/orders/rows/batch" '{"rows":[
  {"order_date":"2026-01-15","status":"delivered","total_amount":249.95,"customer_id":1},
  {"order_date":"2026-02-01","status":"delivered","total_amount":149.99,"customer_id":2},
  {"order_date":"2026-02-20","status":"shipped","total_amount":399.97,"customer_id":1},
  {"order_date":"2026-03-01","status":"shipped","total_amount":79.99,"customer_id":3},
  {"order_date":"2026-03-10","status":"pending","total_amount":599.98,"customer_id":4},
  {"order_date":"2026-03-15","status":"pending","total_amount":49.99,"customer_id":2},
  {"order_date":"2026-03-20","status":"pending","total_amount":329.97,"customer_id":5},
  {"order_date":"2026-03-25","status":"cancelled","total_amount":19.99,"customer_id":3}
]}'
echo " -> 8 orders"

# Order Items
run POST "$R/order_items/rows/batch" '{"rows":[
  {"quantity":5,"unit_price":49.99,"order_id":1,"product_id":1},
  {"quantity":1,"unit_price":149.99,"order_id":2,"product_id":3},
  {"quantity":2,"unit_price":149.99,"order_id":3,"product_id":3},
  {"quantity":1,"unit_price":99.99,"order_id":3,"product_id":1},
  {"quantity":1,"unit_price":79.99,"order_id":4,"product_id":4},
  {"quantity":2,"unit_price":299.99,"order_id":5,"product_id":6},
  {"quantity":1,"unit_price":49.99,"order_id":6,"product_id":1},
  {"quantity":3,"unit_price":9.99,"order_id":7,"product_id":5},
  {"quantity":1,"unit_price":299.99,"order_id":7,"product_id":6},
  {"quantity":1,"unit_price":19.99,"order_id":8,"product_id":2},
  {"quantity":2,"unit_price":49.99,"order_id":1,"product_id":1},
  {"quantity":1,"unit_price":9.99,"order_id":2,"product_id":5},
  {"quantity":3,"unit_price":19.99,"order_id":5,"product_id":2},
  {"quantity":1,"unit_price":79.99,"order_id":7,"product_id":4},
  {"quantity":2,"unit_price":9.99,"order_id":3,"product_id":5}
]}'
echo " -> 15 order items"

echo ""
echo "=== Creating tenant API key ==="
TENANT_KEY=$(run POST /auth/keys "{\"name\":\"Portal Access\",\"role\":\"tenant\",\"tenant_id\":\"$TID\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")

echo ""
echo "============================================"
echo "  Demo data seeded successfully!"
echo "============================================"
echo ""
echo "  Tenant:    Acme Corporation (acme-corp)"
echo "  Database:  crm"
echo "  Tables:    customers, contacts, products, orders, order_items"
echo ""
echo "  Portal URL: https://forge-portal.lucas.engineering"
echo "  API Key:    $TENANT_KEY"
echo ""
echo "  Use this key to log into the tenant portal."
echo "============================================"
