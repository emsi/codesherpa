"""
A local server script to handle REPL and command execution requests.
"""


import sys
import subprocess
import shutil
import signal
import json
import textwrap
from typing import List

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn

from models.api import CodeExecutionRequest, CommandExecutionRequest
from executors.executor import PythonExecutor, CppExecutor, RustExecutor
from utils.plugin import load_manifest

logger.configure(
    handlers=[
        {
            "sink": sys.stderr,
            "format": "<green>{time}</green> <level>{message}</level>",
            "colorize": True,
        }
    ]
)

app = FastAPI(
  title="codesherpa",
  version="0.1.0",
  description=
  "A REPL for your chat. Write and execute code, upload files for data analysis, and more.",
)

executors = {
    "python": PythonExecutor(),
    "c++": CppExecutor(),
    "rust": RustExecutor(),
}

PORT = 3333

origins = [
    f"http://localhost:{PORT}",
    "http://localhost:3001",
    "https://chat.openai.com",
]

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/.well-known/logo.png")
async def get_logo():
    """
    Endpoint to serve the logo file.
    """
    file_path = "./localserver/logo.png"
    return FileResponse(file_path, media_type="text/json")


@app.get("/.well-known/ai-plugin.json")
async def get_manifest():
    """
    Endpoint to serve the manifest file.
    """
    manifest = load_manifest()
    return manifest


@app.get("/.well-known/openapi.json")
async def get_openapi():
    """
    Endpoint to serve the openapi specification file.
    """
    return app.openapi()

@app.get("/upload")
async def upload_page(request: Request):
    return HTMLResponse(content=open("templates/upload.html", "r").read(), status_code=200)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file.

    Args:
        file (UploadFile): The uploaded file.

    Returns:
        dict: The result of the file upload process.
    """
    try:
        file_location = f"static/uploads/{file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"File uploaded: {file.filename}")

        # Construct the URL of the uploaded file
        url = f"http://localhost:{PORT}/{file_location}"

        return {"message": "File uploaded successfully", "url": url}
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return {"error": str(e)}


@app.post("/repl")
def repl(request: CodeExecutionRequest):
    """
    Exexute code. 
    Note: This endpoint current supports a REPL-like environment for Python only.
    
    Args:
        request (CodeExecutionRequest): The request object containing the code to execute.

    Returns:
        dict: The result of the code execution.
    """
    logger.info(f"Received request for REPL execution: {request}")

    executor = executors.get(request.language)
    if executor is None:
        return {"error": "Language not supported"}

    try:
        code_output = executor.execute(request.code)
        logger.info(f"REPL execution result: {code_output}")
        response = {"result": code_output.strip()}
    except Exception as e:
        logger.error(f"Error in REPL execution: {e}")
        response = {"error": str(e)}
        return response

    return response



async def execute_command(command: str) -> str:
    """
    Executes the given command in a shell and returns the result.

    Args:
        command (str): The command to execute.

    Returns:
        str: The result of the command execution.
    """
    try:
        result = subprocess.run(command.split(), capture_output=True, text=True)
        return f"Result:\n{result.stdout}"
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Error executing command: {e}. Return code: {e.returncode}. Output: {e.output}"
        )
        return f"Error executing command: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"Error executing command: {str(e)}"


@app.post("/command")
async def command_endpoint(command_request: CommandExecutionRequest):
    """
    Run commands.

    Args:
        command_request (CommandExecutionRequest): The request object containing the command to execute.

    Returns:
        dict: The result of the command execution.
    """
    logger.info(f"Executing command with request: {command_request}")
    try:
        command_result = await execute_command(command_request.command)
        logger.info(f"Command execution result: {command_result}")
        return {"result": command_result}
    except Exception as e:
        logger.error(f"Error in command execution: {e}")
        return {"error": str(e)}


def start():
    """
    Starts the FastAPI server.
    """

    def shutdown():
        logger.info("Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda signum, frame: shutdown())

    uvicorn.run("localserver.main:app", host="0.0.0.0", port=PORT, reload=False)

def dev():
    """
    Starts the FastAPI dev server.
    """

    def shutdown():
        logger.info("Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda signum, frame: shutdown())

    uvicorn.run("localserver.main:app", host="0.0.0.0", port=PORT, reload=True)