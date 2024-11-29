curl -X POST http://localhost:8080/items \
     -H "Content-Type: application/json" \
     -d '{"name": "Sample Item", "description": "This is a sample item."}'


curl http://localhost:8080/items

curl http://localhost:8080/items/1


curl -X PUT http://localhost:8080/items/1 \
     -H "Content-Type: application/json" \
     -d '{"name": "Updated Item", "description": "This item has been updated."}'


curl -X DELETE http://localhost:8080/items/1