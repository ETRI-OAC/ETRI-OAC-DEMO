""" BACKEND MASTER """

""" 
COMPONENTS
    - User tracking node
    - Patrol node
    - VLM Client node
    - GUI Manager node

CONSIDERATIONS
    - STT, TTS and VLM always running in background & visualize on GUI
"""

from facetracking_client import faceTracking 
from vlm_client import VLLMClient 


class BackendMaster:
    def __init__(self):
        self.face_tracking = faceTracking()
        self.vlm_client = VLLMClient(api_url="http://localhost:8000/v1/chat/completions")
        self.gui_manager = 
    
    def run(self):
        # Start face tracking in a separate thread
        self.face_tracking.start_tracking()
        
        # Main loop for backend operations
        while True:
            # Here you can add logic to handle interactions between components
            pass



def inference_vlm():
    try:
        # Warmup 단계
        print(f"Warming up VLM for {warmup_count} times...")
        warmup_start = time.time()
        for i in range(warmup_count):
            try:
                response, _ = client.query(str(image_path), prompt, measure_time=False)
                print(f"  [{i+1}/{warmup_count}] Warmup complete", end='\r')
            except Exception as e:
                print(f"\nWarmup {i+1} failed: {e}")
                return
        warmup_total_time = time.time() - warmup_start
        print(f"\nWarmup complete! (Total: {warmup_total_time:.2f} seconds)")
        print("-" * 60)
        
        # 실제 측정 단계
        print("Query sent")
        response, elapsed_time = client.query(str(image_path), prompt, measure_time=True)
        
        # 응답 파싱
        if "choices" in response and len(response["choices"]) > 0:
            answer = response["choices"][0]["message"]["content"]
            
            print("VLM response:")
            print("-" * 60)
            print(answer)
            print("-" * 60)
        else:
            print("Unexpected response format: 'choices' key missing or empty")
            print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")

    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: vLLM 서버에 연결할 수 없습니다.")
        print(f"   서버가 {api_url}에서 실행 중인지 확인하세요.")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 오류: {e}")
        if hasattr(e.response, 'text'):
            print(f"   응답 내용: {e.response.text}")
    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()