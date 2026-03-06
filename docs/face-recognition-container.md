# Face Recognition Container

얼굴 인식 서버를 Docker 컨테이너에서 구동합니다.  
컨테이너 이름: `face-recognition`.

---

## 구동 서버

| 항목 | 내용 |
|------|------|
| **실행 스크립트** | `face-recognition/run_face_recognition_server.sh` |
| **진입점** | `face_recognition_server.py` |
| **기본 포트** | **7999** |
| **바인드** | `0.0.0.0` (외부에서 접근 가능) |

**역할:** 등록된 얼굴 DB와 비교해 입력 이미지에서 얼굴을 인식하고, 이름·유사도 등을 JSON으로 반환하는 REST API 서버입니다.

---

## 구조

- **웹 프레임워크:** Flask.
- **인식 엔진:** `face_recognizer` 모듈 — **InsightFace** (`FaceAnalysis`, 기본 모델 `buffalo_l`)로 얼굴 검출·임베딩 추출 후, 등록된 얼굴과 임베딩 유사도 비교.
- **DB:** `database/known_faces.pkl` (기본 경로). 등록 얼굴 임베딩·이름이 저장되며, `register_face.py`로 사전 등록합니다.

**요청 흐름:**

1. 클라이언트가 base64 인코딩된 이미지를 JSON으로 전송.
2. 서버가 디코딩 → InsightFace로 얼굴 검출·임베딩 계산.
3. DB 내 임베딩과 유사도 비교, 임계값(기본 0.5) 이상이면 해당 이름 반환, 아니면 `Unknown`.

---

## 얼굴 등록 (Register)

`register_face.py`를 실행하면 `database` 안에 있는 모든 얼굴 이미지에 대해 embedding을 추출하여 `known_faces.pkl`에 저장합니다.

---

## API 엔드포인트

| Method | 경로 | 설명 |
|--------|------|------|
| `GET`  | `/health` | 서버 상태. `recognizer_loaded`, `known_faces_count` 등 반환 |
| `POST` | `/recognize` | JSON body: `{ "image": "base64_encoded_image_string" }`. 응답: `{ "name", "similarity", "success" }` |

---

## 설정 (명령줄 인자)

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--port` | 7999 | 서버 포트 |
| `--host` | 0.0.0.0 | 바인드 주소 |
| `--database` | database/known_faces.pkl | 등록 얼굴 DB 경로 |
| `--threshold` | 0.5 | 인식 유사도 임계값 |
| `--model` | buffalo_l | InsightFace 모델 이름 |
| `--warmup` | 100 | 기동 시 워밍업 반복 횟수 (첫 추론 지연 완화) |

---

## 클라이언트 연동

데모 스크립트에서는 `FaceRecognitionClient`(예: `zed-ros2-workspace/clients/face_recognition_client.py`)가 이 서버의 `/recognize`를 호출합니다.  
서버가 켜진 상태에서 `face_recognition_client.py`를 실행하면 단위 테스트용 요청을 보낼 수 있습니다.
