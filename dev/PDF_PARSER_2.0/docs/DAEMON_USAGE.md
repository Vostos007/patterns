# Document Processing Daemon - Usage Guide

**Version:** 1.0
**Date:** 2025-11-11

---

## Overview

DocumentDaemon автоматически мониторит папку `inbox/` и обрабатывает новые документы через UnifiedPipeline без ручного вмешательства.

**Основные возможности:**
- ✅ Автоматический мониторинг папки
- ✅ Hash-based deduplication (не обрабатывает дубликаты)
- ✅ Поддержка multiple languages
- ✅ Graceful error handling
- ✅ Detailed logging
- ✅ Statistics tracking

---

## Quick Start

### 1. Базовое использование

```bash
# Запустить daemon с настройками по умолчанию
python -m kps.cli daemon

# Или через entry point (если установлен)
kps daemon
```

**Настройки по умолчанию:**
- Inbox: `./inbox`
- Output: `./output`
- Languages: `en, fr`
- Interval: `300s` (5 минут)

### 2. Настроенный запуск

```bash
# Указать свои папки и языки
kps daemon \
  --inbox ./my_documents \
  --output ./translations \
  --lang en,fr,de \
  --interval 180

# С подробным логированием
kps daemon --log-level DEBUG

# Запустить один раз (для тестирования)
kps daemon --once
```

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Document Workflow                            │
└─────────────────────────────────────────────────────────────────────┘

1. User adds document to inbox/
         ↓
   pattern.pdf
         ↓

2. Daemon detects new file (hash check)
         ↓
   SHA256: a1b2c3d4...
         ↓

3. UnifiedPipeline processes
         ↓
   Extract → Segment → Translate → Export
         ↓

4. Results saved to output/
         ↓
   pattern_en.idml
   pattern_fr.idml
         ↓

5. File moved to inbox/processed/
         ↓
   inbox/processed/pattern.pdf
         ↓

6. Hash saved to state file
         ↓
   data/daemon_state.txt

[Cycle repeats every 5 minutes]
```

---

## Directory Structure

```
project/
├── inbox/                      # Drop documents here
│   ├── pattern1.pdf           # New document
│   ├── pattern2.docx          # New document
│   ├── processed/             # Successfully processed
│   │   └── old_pattern.pdf
│   └── failed/                # Failed to process
│       └── corrupted.pdf
│
├── output/                     # Translation results
│   ├── pattern1_en.idml
│   ├── pattern1_fr.idml
│   └── pattern2_en.idml
│
└── data/
    └── daemon_state.txt        # Processed file hashes
```

---

## Configuration Options

### Command Line Arguments

| Option | Default | Description |
|--------|---------|-------------|
| `--inbox` | `inbox` | Directory to monitor |
| `--output` | `output` | Output directory for translations |
| `--lang` | `en,fr` | Target languages (comma-separated) |
| `--interval` | `300` | Check interval in seconds |
| `--log-level` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `--once` | `False` | Run once and exit (testing mode) |

### Supported File Types

- ✅ **PDF** (.pdf)
- ✅ **Word Documents** (.docx, .doc)
- 🔜 HTML, Markdown (coming soon)

---

## Examples

### Example 1: Basic Daemon

```bash
# Start monitoring inbox/ with default settings
kps daemon
```

**Output:**
```
2025-11-11 14:30:00 [INFO] DocumentDaemon initialized
2025-11-11 14:30:00 [INFO]   Inbox: /path/to/inbox
2025-11-11 14:30:00 [INFO]   Output: /path/to/output
2025-11-11 14:30:00 [INFO]   Languages: en, fr
2025-11-11 14:30:00 [INFO]   Check interval: 300s
2025-11-11 14:30:00 [INFO] Starting DocumentDaemon
2025-11-11 14:30:00 [INFO] Monitoring: /path/to/inbox
2025-11-11 14:30:00 [INFO] Press Ctrl+C to stop
```

### Example 2: Custom Configuration

```bash
# Monitor specific folder, translate to 3 languages, check every 2 minutes
kps daemon \
  --inbox /mnt/documents/incoming \
  --output /mnt/documents/translated \
  --lang en,fr,de \
  --interval 120 \
  --log-level DEBUG
```

### Example 3: Test Run

```bash
# Run once to test configuration
kps daemon --once
```

This will:
1. Check inbox for new documents
2. Process any found documents
3. Exit immediately

Perfect for testing before running continuously.

---

## Monitoring & Logging

### Log Levels

**INFO** (default):
```
2025-11-11 14:35:00 [INFO] Found new document: pattern.pdf (hash=a1b2c3d4...)
2025-11-11 14:35:05 [INFO] ✓ Successfully processed pattern.pdf
2025-11-11 14:35:05 [INFO]   Duration: 5.2s
2025-11-11 14:35:05 [INFO]   Languages: 2
2025-11-11 14:35:05 [INFO]   Segments: 45
2025-11-11 14:35:05 [INFO]   Cache hit rate: 60%
```

**DEBUG**:
```
2025-11-11 14:35:00 [DEBUG] Checking for new documents...
2025-11-11 14:35:00 [DEBUG] Scanning: /path/to/inbox/*.pdf
2025-11-11 14:35:00 [DEBUG] Scanning: /path/to/inbox/*.docx
2025-11-11 14:35:00 [INFO] Found new document: pattern.pdf
2025-11-11 14:35:01 [DEBUG] Computing file hash...
2025-11-11 14:35:01 [DEBUG] Hash: a1b2c3d4e5f6...
2025-11-11 14:35:01 [DEBUG] Starting pipeline...
```

### Statistics

При остановке daemon (Ctrl+C):

```
============================================================
Daemon stopped by user
Runtime: 2:30:15
Documents processed: 15
Errors encountered: 1
Success rate: 93.8%
============================================================
```

---

## Error Handling

### 1. Processing Errors

Если документ не удается обработать:

```
✗ Failed to process: corrupted.pdf
  Error: Extraction failed: PDF is corrupted
```

**Действия:**
- Файл перемещается в `inbox/failed/`
- Ошибка логируется
- Daemon продолжает работу

### 2. File Access Errors

Если файл заблокирован другим процессом:

```
Failed to compute hash for document.pdf: Permission denied
```

**Действия:**
- Файл пропускается в этой итерации
- Будет обработан в следующей итерации

### 3. Pipeline Errors

Если pipeline падает:

```
Error in daemon loop: UnifiedPipeline crashed
```

**Действия:**
- Ошибка логируется с full traceback
- Daemon продолжает работу (не падает)

---

## State Management

### Hash-Based Deduplication

Daemon использует SHA256 hash для определения уникальности файлов:

```python
# Пример: data/daemon_state.txt
a1b2c3d4e5f6789...  # pattern1.pdf
b2c3d4e5f6789...    # pattern2.docx
c3d4e5f6789...      # pattern3.pdf
```

**Преимущества:**
- Одинаковые файлы с разными именами не обрабатываются повторно
- Переименование не вызывает повторную обработку
- Изменение содержимого → новый hash → обработка

### State File Location

```bash
data/daemon_state.txt
```

**Backup:**
```bash
# Создать backup состояния
cp data/daemon_state.txt data/daemon_state.backup.txt

# Восстановить из backup
cp data/daemon_state.backup.txt data/daemon_state.txt
```

**Reset:**
```bash
# Удалить состояние (все файлы будут обработаны заново)
rm data/daemon_state.txt
```

---

## Production Deployment

### Option 1: Systemd Service (Linux)

**1. Создать service file:**

```ini
# /etc/systemd/system/kps-daemon.service
[Unit]
Description=KPS Document Processing Daemon
After=network.target

[Service]
Type=simple
User=kps
WorkingDirectory=/opt/kps
Environment="PATH=/opt/kps/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/kps/.venv/bin/python -m kps.cli daemon \
  --inbox /mnt/documents/inbox \
  --output /mnt/documents/output \
  --lang en,fr,de \
  --interval 300 \
  --log-level INFO
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Включить и запустить:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable kps-daemon
sudo systemctl start kps-daemon

# Проверить status
sudo systemctl status kps-daemon

# Логи
journalctl -u kps-daemon -f
```

### Option 2: Docker

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p inbox output data

# Run daemon
CMD ["python", "-m", "kps.cli", "daemon", \
     "--inbox", "/app/inbox", \
     "--output", "/app/output", \
     "--lang", "en,fr"]
```

**Run:**

```bash
docker build -t kps-daemon .

docker run -d \
  --name kps-daemon \
  --restart unless-stopped \
  -v /mnt/documents:/app/inbox \
  -v /mnt/output:/app/output \
  -v /mnt/data:/app/data \
  kps-daemon
```

### Option 3: Supervisor

```ini
[program:kps-daemon]
command=/opt/kps/.venv/bin/python -m kps.cli daemon
directory=/opt/kps
user=kps
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/kps/daemon.log
```

---

## Monitoring

### Check Daemon Status

```bash
# Проверить, работает ли daemon
ps aux | grep "kps.cli daemon"

# Проверить последние логи
tail -f /var/log/kps/daemon.log
```

### Metrics to Monitor

1. **Processing Rate**
   - Документов в час
   - Средняя длительность обработки

2. **Error Rate**
   - % успешных обработок
   - Частота ошибок

3. **Cache Hit Rate**
   - % переводов из кэша
   - Экономия токенов

4. **Disk Space**
   - Размер output/
   - Размер inbox/processed/

### Prometheus Integration (Optional)

```python
# Future enhancement
from prometheus_client import Counter, Gauge, Histogram

documents_processed = Counter('kps_documents_processed_total', 'Total documents processed')
processing_duration = Histogram('kps_processing_duration_seconds', 'Time to process document')
cache_hit_rate = Gauge('kps_cache_hit_rate', 'Translation cache hit rate')
```

---

## Troubleshooting

### Problem: Daemon not detecting new files

**Solution:**
```bash
# Check permissions
ls -la inbox/

# Check daemon logs
kps daemon --once --log-level DEBUG
```

### Problem: Files stuck in inbox

**Solution:**
```bash
# Check for processing errors
cat /var/log/kps/daemon.log | grep ERROR

# Check file permissions
ls -la inbox/*.pdf
```

### Problem: High memory usage

**Solution:**
```bash
# Reduce interval (process fewer documents concurrently)
kps daemon --interval 600  # 10 minutes

# Or restart daemon periodically via cron
0 */6 * * * systemctl restart kps-daemon
```

### Problem: State file corrupted

**Solution:**
```bash
# Backup current state
cp data/daemon_state.txt data/daemon_state.corrupted.txt

# Remove invalid lines (non-hex)
grep -E '^[a-f0-9]{64}$' data/daemon_state.corrupted.txt > data/daemon_state.txt

# Or reset completely
rm data/daemon_state.txt
```

---

## FAQ

### Q: Can I process the same file twice?

**A:** No (by design). Daemon uses file hash to prevent duplicate processing. To reprocess:
1. Modify the file content (even slightly)
2. Or remove its hash from `data/daemon_state.txt`

### Q: What happens if daemon crashes?

**A:** When restarted, it will resume from the saved state. No documents are lost or reprocessed.

### Q: Can I run multiple daemons?

**A:** Yes, but use different inbox/output directories and state files for each instance.

### Q: How to add new languages after daemon is running?

**A:** Stop daemon, restart with new `--lang` parameter. Existing translations are preserved.

### Q: Does daemon support subdirectories?

**A:** Currently no. Only files directly in `inbox/` are monitored. Subdirectories are ignored.

---

## Best Practices

1. **Keep inbox clean**: Move processed files to separate storage periodically
2. **Monitor disk space**: Set up alerts when output/ exceeds threshold
3. **Regular backups**: Backup `data/daemon_state.txt` and output/
4. **Use systemd**: For production, always use systemd or equivalent process manager
5. **Set appropriate intervals**: Balance between responsiveness and resource usage
6. **Enable logging**: Always keep logs for troubleshooting

---

## Next Steps

After setting up daemon, consider:

1. **Term Validator** (P2): Ensure 100% glossary compliance
2. **Pandoc Export** (P3): Add DOCX/PDF export formats
3. **Monitoring**: Set up Prometheus metrics
4. **Webhooks**: Notify external systems when documents are processed

See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for details.

---

## Support

- **Documentation**: [README.md](../README.md)
- **Architecture**: [GAP_ANALYSIS.md](./GAP_ANALYSIS.md)
- **Issues**: Create GitHub issue with logs and configuration

---

**Status:** Production Ready
**Last Updated:** 2025-11-11
