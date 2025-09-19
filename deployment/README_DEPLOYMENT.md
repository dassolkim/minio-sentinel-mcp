# MinIO MCP Server - 배포 가이드

## 🚀 배포 방법 개요

현재 STDIO 방식의 한계를 극복하고 안정적인 프로덕션 환경을 위한 다양한 배포 옵션을 제공합니다.

### 🔄 기존 STDIO 방식의 한계

```python
# 기존 방식 - STDIO only
if __name__ == "__main__":
    mcp = create_mcp_server()
    mcp.run()  # 외부 접근 불가, 단일 클라이언트만 지원
```

### ✨ 새로운 HTTP Transport 방식

```python
# 새로운 방식 - HTTP + SSE 지원
async def main():
    app = create_http_app()
    await uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 📋 배포 옵션 비교

| 방식 | 장점 | 단점 | 사용 시나리오 |
|------|------|------|---------------|
| **STDIO** | 간단한 설정 | 외부 접근 불가, 확장성 제한 | 로컬 개발, 테스트 |
| **HTTP Transport** | 외부 접근 가능, REST API | 추가 설정 필요 | 단일 서버 배포 |
| **Docker** | 환경 일관성, 쉬운 배포 | Docker 지식 필요 | 컨테이너 환경 |
| **Docker Compose** | 멀티 서비스 관리 | 복잡한 설정 | 개발/스테이징 환경 |
| **Kubernetes** | 고가용성, 자동 확장 | 복잡한 운영 | 프로덕션 환경 |

## 🛠️ 배포 방법별 상세 가이드

### 1. HTTP Transport 직접 배포

#### 설치 및 실행
```bash
# 의존성 추가 설치
pip install uvicorn[standard] fastapi prometheus-client psutil

# HTTP 서버 실행
python minio_mcp_http_server.py
```

#### 특징
- **포트**: 8000 (HTTP)
- **SSE 지원**: `/sse` 엔드포인트
- **메트릭스**: `/metrics` (Prometheus)
- **API 문서**: `/docs` (Swagger UI)

#### 접근 방법
```bash
# Health Check
curl http://localhost:8000/health

# SSE 연결 테스트
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse

# MCP 요청 (JSON-RPC)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```

### 2. Docker 배포

#### 빌드 및 실행
```bash
# 이미지 빌드
docker build -t minio-mcp-server:1.0.0 .

# 컨테이너 실행
docker run -d \
  --name minio-mcp-server \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  minio-mcp-server:1.0.0
```

#### 자동 배포 스크립트
```bash
# 전체 배포 프로세스 자동화
./deploy.sh deploy-docker
```

### 3. Docker Compose 배포

#### 기본 배포
```bash
# 환경 설정
cp production.env .env

# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f minio-mcp-server
```

#### Nginx와 함께 배포 (SSL 지원)
```bash
# SSL 인증서 준비 (자체 서명 또는 Let's Encrypt)
mkdir -p ssl

# Nginx 프로필로 배포
docker-compose --profile with-nginx up -d

# HTTPS 접근
curl -k https://localhost/health
```

#### Redis 캐싱 포함 배포
```bash
# Redis 프로필 추가
docker-compose --profile with-redis up -d
```

### 4. Kubernetes 배포

#### 사전 준비
```bash
# 네임스페이스 및 시크릿 설정
kubectl create namespace minio-mcp
kubectl create secret generic minio-mcp-secrets \
  --from-literal=KEYCLOAK_CLIENT_SECRET=your-secret \
  --from-literal=SECRET_KEY=your-super-secret-key \
  -n minio-mcp
```

#### 배포 실행
```bash
# Kubernetes 리소스 배포
kubectl apply -f kubernetes.yaml

# 배포 상태 확인
kubectl get all -n minio-mcp

# 로그 확인
kubectl logs -f deployment/minio-mcp-server -n minio-mcp
```

#### 자동 스케일링 설정
```yaml
# HPA가 자동으로 적용됨
# CPU 70% 이상 시 자동 확장 (최대 10개 파드)
```

## 🔐 보안 설정

### 1. API 키 인증
```python
# API 키 생성 및 사용
from security import security_manager

api_key = security_manager.api_key_manager.generate_api_key(
    user_id="admin",
    permissions=["read", "write", "admin"]
)

# 요청 시 헤더에 추가
curl -H "X-API-Key: your-api-key" http://localhost:8000/mcp
```

### 2. Rate Limiting
- **분당 요청 제한**: 기본 100회
- **시간당 요청 제한**: 기본 2000회
- **IP 기반 제한**: 자동 적용

### 3. SSL/TLS 설정
```bash
# 자체 서명 인증서 생성
openssl req -x509 -newkey rsa:4096 -nodes \
  -out ssl/cert.pem -keyout ssl/key.pem -days 365

# Let's Encrypt 사용 (권장)
certbot certonly --standalone -d your-domain.com
```

## 📊 모니터링 및 메트릭스

### 1. Prometheus 메트릭스
```bash
# 메트릭스 확인
curl http://localhost:8000/metrics

# 주요 메트릭스
# - mcp_requests_total: 총 요청 수
# - mcp_request_duration_seconds: 요청 처리 시간
# - mcp_active_connections: 활성 SSE 연결 수
# - mcp_tool_calls_total: 도구 호출 수
```

### 2. Health Check
```bash
# 간단한 상태 확인
curl http://localhost:8000/health

# 상세한 상태 확인
curl http://localhost:8000/health/detailed
```

### 3. 시스템 메트릭스
- CPU 사용률
- 메모리 사용률
- 디스크 사용률
- 네트워크 I/O

## 🚀 성능 최적화

### 1. 워커 프로세스 설정
```bash
# Gunicorn을 사용한 멀티 워커
gunicorn minio_mcp_http_server:create_http_app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 2. 캐싱 전략
- Redis를 통한 세션 캐싱
- JWT 토큰 캐싱
- API 응답 캐싱

### 3. 로드 밸런싱
```nginx
# Nginx 로드 밸런싱 설정
upstream minio_mcp_backend {
    server minio-mcp-server-1:8000;
    server minio-mcp-server-2:8000;
    server minio-mcp-server-3:8000;
}
```

## 🔧 배포 스크립트 사용법

### 자동 배포 스크립트
```bash
# 사용 가능한 옵션 확인
./deploy.sh help

# Docker 빌드 및 배포
./deploy.sh deploy-docker

# Docker Compose 배포
./deploy.sh deploy-compose

# Nginx 포함 배포
./deploy.sh deploy-compose-nginx

# Kubernetes 배포
./deploy.sh deploy-k8s

# 배포 상태 확인
./deploy.sh status

# 로그 확인
./deploy.sh logs

# 정리
./deploy.sh cleanup
```

## 🌐 외부 LLM 연동

### 1. OpenAI API 연동
```python
import openai

# MCP 서버를 통한 MinIO 작업
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You have access to MinIO MCP tools"},
        {"role": "user", "content": "List all buckets in MinIO"}
    ],
    tools=[
        # MCP 도구 정의
    ]
)
```

### 2. Anthropic Claude 연동
```python
import anthropic

client = anthropic.Anthropic()

# SSE를 통한 실시간 스트리밍
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1000,
    stream=True,
    messages=[...]
)
```

### 3. 커스텀 LLM 클라이언트
```python
import httpx

async def call_mcp_tool(tool_name: str, parameters: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://your-mcp-server:8000/mcp",
            json={
                "jsonrpc": "2.0",
                "method": f"tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                },
                "id": 1
            }
        )
        return response.json()
```

## 📝 트러블슈팅

### 일반적인 문제들

1. **포트 충돌**
   ```bash
   # 포트 사용 확인
   sudo netstat -tlnp | grep :8000
   
   # 다른 포트 사용
   export MCP_SERVER_PORT=8001
   ```

2. **권한 문제**
   ```bash
   # Docker 권한 확인
   sudo usermod -aG docker $USER
   
   # 로그 디렉토리 권한
   sudo chown -R $USER:$USER logs/
   ```

3. **메모리 부족**
   ```bash
   # 시스템 리소스 확인
   free -h
   df -h
   
   # Docker 메모리 제한
   docker update --memory=512m minio-mcp-server
   ```

### 로그 분석
```bash
# 애플리케이션 로그
tail -f logs/minio-mcp-server.log

# Docker 로그
docker logs -f minio-mcp-server

# Kubernetes 로그
kubectl logs -f deployment/minio-mcp-server -n minio-mcp
```

## 🎯 권장 배포 전략

### 개발 환경
- HTTP Transport 직접 실행
- 로컬 개발 및 테스트

### 스테이징 환경
- Docker Compose + Nginx
- SSL 인증서 적용
- 모니터링 설정

### 프로덕션 환경
- Kubernetes 배포
- 자동 스케일링 활성화
- 완전한 보안 설정
- 백업 및 복구 계획

이 가이드를 통해 STDIO 방식의 한계를 극복하고 안정적이고 확장 가능한 MCP 서버를 배포할 수 있습니다.
