import asyncio
import csv
import json
import os
import socket
import ssl
from datetime import datetime
from io import StringIO

import httpx
import uvicorn
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

LOG_DIR = "logs"
CSV_LOG_DIR = os.path.join(LOG_DIR, "csv")
JSON_LOG_DIR = os.path.join(LOG_DIR, "json")
os.makedirs(CSV_LOG_DIR, exist_ok=True)
os.makedirs(JSON_LOG_DIR, exist_ok=True)

CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_USER = os.getenv("CLICKHOUSE_USER", "default")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))

CH_URL = f"http://{CH_HOST}:{CH_PORT}"

app = FastAPI()
auto_push_is_running = True
main_data_queue = asyncio.Queue()


async def execute_query(query, data=None):
    url = f"http://{CH_HOST}:{CH_PORT}/"
    params = {"query": query.strip()}
    auth = (CH_USER, CH_PASSWORD) if CH_USER and CH_PASSWORD else None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, data=data, auth=auth)
            response.raise_for_status()
            return response, None
    except httpx.HTTPStatusError as e:
        return None, {
            "error": f"HTTP error: {e.response.status_code} {e.response.text}"
        }
    except httpx.RequestError as e:
        return None, {"error": f"Request error: {str(e)}"}


async def auto_insert_data():
    while auto_push_is_running:
        await asyncio.sleep(1)
        if not main_data_queue.empty():
            queue_data = []
            while not main_data_queue.empty():
                queue_data.append(await main_data_queue.get())
            for tab_n, file, data_format in queue_data:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = f.readlines()
                    if data_format == "list":
                        data = list_req_format(data)
                        query = f"INSERT INTO {tab_n} FORMAT CSV"
                        data = "\n".join([",".join(map(str, row)) for row in data])
                    else:
                        data = json_req_format(data)
                        query = f"INSERT INTO {tab_n} FORMAT JSONEachRow"
                        data = "\n".join([json.dumps(row) for row in data])
                    resp, resp_error = await execute_query(query, data)
                    if resp_error:
                        await main_data_queue.put((tab_n, file, data_format))
                        continue
                    os.remove(file)
                except Exception as e:
                    await main_data_queue.put((tab_n, file, data_format))


@app.post("/write_log")
async def write_log(request: Request):
    body = await request.json()
    data_error, res = "", []
    for log_entry in body:
        req_table = log_entry["table_name"]
        rows = log_entry["rows"]
        file_format = log_entry.get("format")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_flag, data_error = True, ""
        file_path = ''
        if file_format == "list":
            if good_list_request(rows):
                file_path = os.path.join(CSV_LOG_DIR, f"{req_table}_{timestamp}.csv")
                with open(file_path, "w", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            else:
                data_error, main_flag = 'Invalid CSV', False
        elif file_format == "json":
            if good_json_request(rows):
                file_path = os.path.join(JSON_LOG_DIR, f"{req_table}_{timestamp}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    for row in rows:
                        f.write(json.dumps(row) + "\n")
            else:
                data_error, main_flag = 'Invalid JSON', False
        if main_flag:
            if file_path:
                await main_data_queue.put((req_table, file_path, file_format))
                res.append({"file_path": file_path})
        else:
            break
    if data_error:
        return JSONResponse(content=[{data_error}], status_code=400)
    return JSONResponse(content=res, status_code=201)


def check_old_data():
    for i in os.listdir(JSON_LOG_DIR):
        if i.endswith(".json"):
            tab_n = i.split("_")[0]
            path = os.path.join(JSON_LOG_DIR, i)
            asyncio.create_task(main_data_queue.put((tab_n, path, "json")))

    for i in os.listdir(CSV_LOG_DIR):
        if i.endswith(".csv"):
            tab_n = i.split("_")[0]
            path = os.path.join(CSV_LOG_DIR, i)
            asyncio.create_task(main_data_queue.put((tab_n, path, "list")))


@app.get("/select/{table_name}")
async def select_from_clickhouse(table_name: str):
    query = f"SELECT * FROM default.{table_name} FORMAT JSON"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CH_URL}/?query={query}", auth=(CH_USER, CH_PASSWORD))
            response.raise_for_status()
            return {"status": "ok", "data": response.json()["data"]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.on_event("shutdown")
async def shutdown_event():
    global auto_push_is_running
    auto_push_is_running = False
    await asyncio.sleep(1)
    await auto_insert_data()


@app.on_event("startup")
async def startup_event():
    check_old_data()
    asyncio.create_task(auto_insert_data())


@app.get("/healthcheck")
async def healthcheck():
    return Response(content="Ok", media_type="text/plain")


def good_list_request(data):
    if isinstance(data, list):
        for i in data:
            if not ((isinstance(i, list)) and (1 <= len(i) <= 2) and (isinstance(i[0], int))):
                return False
        return True
    return False


def good_json_request(data):
    if isinstance(data, list):
        for i in data:
            if not ((isinstance(i, dict)) and ("a" in i) and (isinstance(i["a"], int))):
                return False
        return True
    return False


def json_req_format(data):
    resp = []
    for i in data:
        try:
            resp.append(json.loads(i.strip()))
        except json.JSONDecodeError as e:
            pass
    return resp


def list_req_format(data):
    resp, r = [], csv.reader(StringIO("\n".join(data)))
    for i in r:
        try:
            if len(i) > 1:
                resp.append([int(i[0]), i[1]])
        except ValueError as e:
            pass
    return resp


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
