import os
import json
import asyncio
from sanic import Sanic, response
from sanic.exceptions import NotFound
from models import Item
from tortoise import Tortoise
from tortoise.contrib.sanic import register_tortoise
import redis.asyncio as redis

# Initialize Sanic app
app = Sanic("ItemService")

# Get environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://user:password@localhost:5432/mydb")

# Initialize Redis client (to be set in startup event)
redis_client = None

@app.listener('before_server_start')
async def setup_db_and_redis(app, loop):
    global redis_client
    # Initialize Redis client
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    
    # Wait for 5 seconds to ensure PostgreSQL is ready
    print("Waiting for 5 seconds to ensure PostgreSQL is ready...")
    await asyncio.sleep(5)
    
    # Initialize Tortoise ORM
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas()

@app.listener('after_server_stop')
async def close_db_and_redis(app, loop):
    global redis_client
    # Close Redis client
    if redis_client:
        await redis_client.close()
    
    # Close Tortoise ORM connections
    await Tortoise.close_connections()

@app.route("/items/<id:int>", methods=["GET"])
async def get_item(request, id):
    cached_item = await redis_client.get(f"item:{id}")

    if cached_item:
        return response.json({"data": json.loads(cached_item)}, status=200)

    item = await Item.get_or_none(id=id)
    if item:
        item_data = {"id": item.id, "name": item.name, "description": item.description}
        await redis_client.set(f"item:{id}", json.dumps(item_data))
        return response.json({"data": item_data}, status=200)

    return response.json({"error": "Item not found"}, status=404)

@app.route("/items", methods=["GET"])
async def get_all_items(request):
    cached_items = await redis_client.get("items:all")
    if cached_items:
        return response.json({"data": json.loads(cached_items)}, status=200)

    items = await Item.all().values("id", "name", "description")
    items_list = list(items)
    await redis_client.set("items:all", json.dumps(items_list))

    return response.json({"data": items_list}, status=200)

@app.route("/items", methods=["POST"])
async def create_item(request):
    try:
        data = request.json
        if not data or "name" not in data or "description" not in data:
            return response.json({"error": "Invalid input"}, status=400)
        
        item = await Item.create(name=data["name"], description=data["description"])
        await redis_client.delete("items:all")
        return response.json({"id": item.id, "name": item.name}, status=201)
    except Exception as e:
        return response.json({"error": str(e)}, status=500)

@app.route("/items/<id:int>", methods=["PUT"])
async def update_item(request, id):
    try:
        data = request.json
        if not data or "name" not in data or "description" not in data:
            return response.json({"error": "Invalid input"}, status=400)
        
        item = await Item.get_or_none(id=id)

        if not item:
            return response.json({"error": "Item not found"}, status=404)

        item.name = data["name"]
        item.description = data["description"]
        await item.save()
        item_data = {"id": item.id, "name": item.name, "description": item.description}
        await redis_client.set(f"item:{id}", json.dumps(item_data))
        await redis_client.delete("items:all")

        return response.json({"message": "Item updated"}, status=200)
    except Exception as e:
        return response.json({"error": str(e)}, status=500)

@app.route("/items/<id:int>", methods=["DELETE"])
async def delete_item(request, id):
    try:
        item = await Item.get_or_none(id=id)

        if not item:
            return response.json({"error": "Item not found"}, status=404)

        await item.delete()
        await redis_client.delete(f"item:{id}")
        await redis_client.delete("items:all")

        return response.json({"message": "Item deleted"}, status=200)
    except Exception as e:
        return response.json({"error": str(e)}, status=500)

if __name__ == "__main__":
    # Register Tortoise ORM with Sanic
    register_tortoise(
        app,
        db_url=DATABASE_URL,
        modules={"models": ["models"]},
        generate_schemas=False,  # Already handled in startup
    )
    
    # Run Sanic app
    app.run(host="0.0.0.0", port=8080, workers=1)