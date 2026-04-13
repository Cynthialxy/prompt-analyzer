.PHONY: backend frontend dev stop logs help

BACKEND_PORT ?= 5000
FRONTEND_PORT ?= 3000

# ── 启动 ──────────────────────────────────────────────────────────────

backend:
	@echo "Starting backend on :$(BACKEND_PORT)..."
	cd backend && python3 -m flask --app app run --port $(BACKEND_PORT)

frontend:
	@echo "Starting frontend on :$(FRONTEND_PORT)..."
	cd frontend && npm run dev

# 同时启动前后端（各占一个 shell，Ctrl-C 全部退出）
dev:
	@echo "Starting backend (:$(BACKEND_PORT)) and frontend (:$(FRONTEND_PORT))..."
	@trap 'kill 0' INT; \
	cd backend && python3 -m flask --app app run --port $(BACKEND_PORT) & \
	cd frontend && npm run dev & \
	wait

# ── 停止 ──────────────────────────────────────────────────────────────

stop:
	@echo "Stopping services on ports $(BACKEND_PORT) and $(FRONTEND_PORT)..."
	-lsof -ti:$(BACKEND_PORT) | xargs kill -9 2>/dev/null || true
	-lsof -ti:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null || true
	@echo "Done."

# ── 日志 ──────────────────────────────────────────────────────────────

logs:
	@echo "=== Backend ===" && cat /tmp/backend.log 2>/dev/null || echo "(no log)"
	@echo "=== Frontend ===" && cat /tmp/frontend.log 2>/dev/null || echo "(no log)"

# ── 帮助 ──────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  make backend     启动后端 (Flask :5000)"
	@echo "  make frontend    启动前端 (Vite  :3000)"
	@echo "  make dev         同时启动前后端"
	@echo "  make stop        停止所有服务"
	@echo "  make logs        查看日志"
	@echo ""
	@echo "  可覆盖端口: make dev BACKEND_PORT=5001 FRONTEND_PORT=3001"
	@echo ""
