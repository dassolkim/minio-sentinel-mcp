# MinIO MCP SSE Server - 배포 가이드

## 🎯 개요

MinIO MCP SSE Server는 표준 MCP(Model Context Protocol) SSE(Server-Sent Events) 전송 방식을 사용하여 Langflow, Claude Desktop 등의 MCP 클라이언트와 호환되는 서버입니다.

## 🚀 빠른 시작

### 1. 서버 실행
```bash
cd /home/csle/minio/mcp-server/deployment
./run_minio_mcp_sse.sh
```

### 2. 연결 URL
- **로컬**: `http://127.0.0.1:8765`
- **외부**: `http://[서버IP]:8765`

## 🔧 서버 구성

### 포트 설정
- **기본 포트**: 8765
- **설정 파일**: `deployment/.env`
- **환경 변수**: `MCP_SSE_PORT=8765`

### 외부 접근 설정
서버는 `0.0.0.0:8765`에 바인딩되어 외부에서 접근 가능합니다.

## 🔐 방화벽 설정

외부에서 접근하려면 방화벽에서 8765 포트를 열어야 합니다:

### Ubuntu/Debian (ufw)
```bash
sudo ufw allow 8765
sudo ufw reload
```

### CentOS/RHEL (firewalld)
```bash
sudo firewall-cmd --permanent --add-port=8765/tcp
sudo firewall-cmd --reload
```

### 직접 iptables
```bash
sudo iptables -A INPUT -p tcp --dport 8765 -j ACCEPT
sudo iptables-save
```

## 🔍 연결 테스트

### 1. 포트 확인
```bash
# 서버가 실행 중인지 확인
lsof -i :8765

# 외부에서 접근 가능한지 확인
nmap -p 8765 [서버IP]
```

### 2. 네트워크 테스트
```bash
# 다른 서버에서 텔넷으로 연결 테스트
telnet [서버IP] 8765
```

## 🛠️ MCP 클라이언트 연결

### Langflow
1. MCP 컴포넌트 추가
2. URL: `http://[서버IP]:8765`
3. 연결 테스트

### Claude Desktop
```json
{
  "mcpServers": {
    "minio": {
      "command": "curl",
      "args": ["-N", "http://[서버IP]:8765"]
    }
  }
}
```

## 📋 사용 가능한 도구

### 인증 도구 (4개)
- `minio_login` - 사용자 인증
- `minio_refresh_token` - 토큰 갱신
- `minio_get_user_info` - 사용자 정보
- `minio_check_auth_status` - 인증 상태 확인

### 헬스체크 도구 (4개)
- `minio_health_check` - 기본 상태 확인
- `minio_ready_check` - 준비 상태 확인
- `minio_live_check` - 활성 상태 확인
- `minio_detailed_health` - 상세 상태 확인

### 버킷 관리 도구 (6개)
- `minio_list_buckets` - 버킷 목록
- `minio_create_bucket` - 버킷 생성
- `minio_get_bucket_info` - 버킷 정보
- `minio_delete_bucket` - 버킷 삭제
- `minio_get_bucket_policy` - 버킷 정책 조회
- `minio_set_bucket_policy` - 버킷 정책 설정

### 객체 작업 도구 (8개)
- `minio_list_objects` - 객체 목록
- `minio_upload_object` - 객체 업로드
- `minio_download_object` - 객체 다운로드
- `minio_get_object_info` - 객체 정보
- `minio_delete_object` - 객체 삭제
- `minio_copy_object` - 객체 복사
- `minio_bulk_delete` - 일괄 삭제
- `minio_generate_presigned` - 임시 URL 생성

### 사용자 관리 도구 (7개)
- `minio_list_users` - 사용자 목록
- `minio_create_user` - 사용자 생성
- `minio_get_user` - 사용자 정보
- `minio_update_user` - 사용자 수정
- `minio_delete_user` - 사용자 삭제
- `minio_get_user_policies` - 사용자 정책
- `minio_assign_user_policy` - 정책 할당

### 정책 관리 도구 (6개)
- `minio_list_policies` - 정책 목록
- `minio_create_policy` - 정책 생성
- `minio_get_policy` - 정책 조회
- `minio_update_policy` - 정책 수정
- `minio_delete_policy` - 정책 삭제
- `minio_validate_policy` - 정책 검증

## 🔧 문제 해결

### 연결 실패
1. 방화벽 설정 확인
2. 포트 사용 여부 확인: `lsof -i :8765`
3. 서버 로그 확인

### 인증 실패
1. Keycloak 서버 접근 가능 여부 확인
2. `.env` 파일의 인증 정보 확인
3. `minio_login` 도구로 먼저 인증

### 도구 호출 실패
1. MinIO API 서버 접근 가능 여부 확인
2. 사용자 권한 확인
3. `minio_health_check`로 연결 상태 확인

## 📊 서버 상태 모니터링

### 로그 확인
서버 실행 시 콘솔에 실시간 로그가 표시됩니다.

### 프로세스 확인
```bash
# 실행 중인 프로세스 확인
ps aux | grep minio_mcp_sse_server

# 포트 사용 확인
netstat -tlnp | grep 8765
```

## ⚡ 성능 최적화

### 동시 연결 수
- 기본적으로 여러 클라이언트 동시 연결 지원
- 필요시 FastMCP 설정으로 조정 가능

### 메모리 사용량
- 평균 50-100MB 사용
- 대용량 파일 작업 시 증가 가능

## 🔒 보안 고려사항

### 네트워크 보안
- 필요한 포트만 열기
- 가능하면 VPN이나 프라이빗 네트워크 사용

### 인증 보안
- 강력한 Keycloak 비밀번호 사용
- 정기적인 토큰 갱신

### 데이터 보안
- HTTPS 사용 권장 (프록시 설정)
- 민감한 데이터 접근 권한 제한

이 가이드를 통해 MinIO MCP SSE Server를 안전하고 효율적으로 운영할 수 있습니다.
