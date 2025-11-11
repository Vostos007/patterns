#!/usr/bin/env python3

import os
import sys

# Добавляем текущую директорию в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import create_app

# Создаем приложение с CORS для localhost:3050
app = create_app(
    cors_origins=["http://localhost:3050", "http://127.0.0.1:3050"],
    auto_start_jobs=True
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
