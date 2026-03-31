# Face Recognition Container

얼굴 인식 서버를 Docker 컨테이너에서 구동합니다.
컨테이너 이름: `face-recognition` (hailo-inference 컨테이너 내부에서 실행).

---

## 구동 서버

| 항목 | 내용 |
|------|------|
| **실행 스크립트** | `hailo-inference/run_face_recognition_server.sh` |
| **진입점** | `face_recognition_server.py` |
| **기본 포트** | **7999** |
| **바인드** | `0.0.0.0` |

**역할:** 등록된 얼굴 DB와 비교해 입력 이미지에서 얼굴을 인식하고, 이름/유사도를 JSON으로 반환하는 REST API 서버입니다.

---

## 구조

- **웹 프레임워크:** Flask
- **얼굴 검출:** Hailo-10 SCRFD (`--hailo-hef` 지정 시) 또는 CPU InsightFace SCRFD (기본)
- **얼굴 임베딩:** InsightFace ArcFace (`buffalo_l`) — 항상 CPU에서 실행
- **유사도 비교:** 코사인 유사도 (512차원 벡터)
- **DB:** `database/known_faces.pkl` — `{이름: embedding(np.ndarray)}` 딕셔너리 (pickle)

**요청 흐름:**

1. 클라이언트가 base64 인코딩된 이미지를 JSON으로 전송
2. 서버가 디코딩 → SCRFD로 얼굴 검출 → ArcFace로 임베딩 추출
3. DB 내 임베딩과 코사인 유사도 비교, 임계값(기본 0.5) 이상이면 이름 반환, 아니면 `Unknown`

> **Hailo-10 사용 시:** `--use-hailo-server` 플래그로 중앙 Hailo Inference Server(port 8003)를 통해 SCRFD를 실행합니다. 직접 Hailo 장치를 사용하려면 `--hailo-hef`로 HEF 경로를 지정합니다.

---

## 얼굴 등록 (Register)

`hailo-inference/register_face.py`로 얼굴을 사전 등록합니다.

### 단일 이미지 등록

```bash
cd hailo-inference/docker && ./exec.sh
cd /root/workspace/hailo-inference
python3 register_face.py --image /path/to/photo.jpg --name "홍길동"
```

### 디렉토리 일괄 등록

`database/` 폴더에 이미지를 넣고 실행하면 **파일명을 이름으로** 자동 등록합니다:

```
database/
├── 홍길동.jpg
├── 김철수.png
└── known_faces.pkl  ← 자동 생성/갱신
```

```bash
python3 register_face.py --directory ./database/
```

### register_face.py 인자

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--name` | — | 등록할 이름 (단일 이미지 모드 시) |
| `--image` | — | 단일 이미지 파일 경로 |
| `--directory` | `./database/` | 이미지 디렉토리 (파일명 = 이름) |
| `--database` | `./database/known_faces.pkl` | DB 저장 경로 |
| `--threshold` | 0.5 | 인식 유사도 임계값 |

지원 이미지 형식: `.jpg`, `.jpeg`, `.png`, `.webp`

---

## API 엔드포인트

| Method | 경로 | 설명 |
|--------|------|------|
| `GET`  | `/health` | 서버 상태 (`recognizer_loaded`, `known_faces_count` 등) |
| `POST` | `/recognize` | 얼굴 인식 요청 |

### /recognize 요청 형식

```json
{
  "image": "base64_encoded_image_string"
}
```

> `data:image/jpeg;base64,` 접두사가 붙어 있어도 자동 제거됩니다.

### /recognize 응답 형식

```json
{
  "success": true,
  "name": "홍길동",
  "similarity": 0.85
}
```

---

## 설정 (명령줄 인자)

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--port` | 7999 | 서버 포트 |
| `--host` | 0.0.0.0 | 바인드 주소 |
| `--database` | `database/known_faces.pkl` | 등록 얼굴 DB 경로 |
| `--threshold` | 0.5 | 인식 유사도 임계값 |
| `--model` | `buffalo_l` | InsightFace 모델 이름 |
| `--warmup` | 100 | 기동 시 워밍업 반복 횟수 |
| `--warmup-image` | — | 워밍업용 이미지 경로 |
| `--hailo-hef` | — | SCRFD HEF 경로 (Hailo 직접 사용 시) |
| `--hailo-device` | — | Hailo 장치 ID (예: `0000:02:00.0`) |
| `--hailo-index` | 0 | Hailo 장치 인덱스 |
| `--use-hailo-server` | — | 중앙 Hailo Inference Server 사용 |
| `--hailo-server-host` | `localhost` | Hailo 서버 호스트 |
| `--hailo-server-port` | 8003 | Hailo 서버 포트 |

---

## 클라이언트 연동

데모 스크립트에서는 `FaceRecognitionClient` (`demo-gui/clients/face_recognition_client.py`)가 `/recognize`를 호출합니다.

```bash
# 단위 테스트 (hailo-inference 컨테이너 내부)
cd /root/workspace/hailo-inference
python3 face_recognition_client.py --image test_face.jpg
```
