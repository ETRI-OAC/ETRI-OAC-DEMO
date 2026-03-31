# VLM Container

Vision-Language Model(VLM) 추론 서버를 Docker 컨테이너에서 구동합니다.
컨테이너 이름: `vlm-server`.

> **현재 비활성 상태** — Ryzen AI SDK 1.7.0이 Krackan NPU를 아직 지원하지 않습니다.

---

## 구동 서버

| 항목 | 내용 |
|------|------|
| **실행** | `vlm/run_vlm_server.sh` |
| **모델** | `amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu` (AWQ UINT4, ONNX) |
| **추론** | Ryzen AI 350 NPU (VitisAI EP) / CPU fallback |
| **포트** | `8000` (OpenAI 호환 API) |

첫 실행 시 HuggingFace에서 모델을 다운로드합니다. 이후에는 `vlm/models/`에 캐시된 모델을 재사용합니다.

---

## 구조

- **역할:** 이미지+텍스트를 입력받아 비전/언어 추론(질의응답, 캡션 등)을 수행하는 HTTP API 서버.
- **프로토콜:** OpenAI 호환 API. 클라이언트는 `http://localhost:8000` (기본 포트)로 요청을 보냅니다.
- **클라이언트:** 데모 스크립트의 `VLLMClient` (`demo-gui/clients/vlm_client.py`)가 이 주소로 이미지와 프롬프트를 전달합니다.

**요청 흐름:**

1. 클라이언트가 이미지를 base64 또는 URL로 인코딩.
2. `POST /v1/chat/completions` (또는 동일 호환 엔드포인트)로 메시지 리스트 전송.
3. 서버가 모델 추론 후 텍스트 응답 반환.

---

## 주의사항

- **기동 시간:** 서버가 켜지기까지 **최대 약 5분** 걸릴 수 있습니다.
- **네트워크:** 첫 기동 및 **첫 번째 쿼리 응답**이 나올 때까지 **네트워크 연결**이 필요합니다(모델/토큰라이저 등).
- `run_all_servers.sh`에서 VLM은 비활성 상태이며 별도 실행이 필요합니다.
