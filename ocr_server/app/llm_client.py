import torch
import os
import gc
import json
import uuid
import asyncio  # 비동기 처리를 위해 추가
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

# 프롬프트 임포트
try:
    from .prompts import OCR_SYSTEM_PROMPT
except ImportError:
    # 비상용 기본 프롬프트
    OCR_SYSTEM_PROMPT = "Extract data in JSON format."

# ==========================================
# 1. 모델 초기화 (전역 로드)
# ==========================================
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
os.environ["HF_HOME"] = "/workspace/hf_cache"
# 메모리 단편화 방지 설정
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

print(f"⏳ [System] 모델 로딩 시작: {MODEL_ID} (4-bit Fixed Mode)")

try:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",  # 자동 할당 권장
        low_cpu_mem_usage=True,
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    print("✅ [System] 모델 로딩 완료!")

except Exception as e:
    print(f"❌ [Error] 모델 로딩 실패: {e}")
    os._exit(1)

# ==========================================
# 2. 내부 동기 함수 (스레드에서 실행될 실제 작업)
# ==========================================
def _run_inference_sync(image_paths, prompt_text):
    """
    이 함수는 CPU/GPU를 점유하므로 반드시 별도 스레드에서 실행해야 함
    """
    temp_files = []
    
    try:
        if not isinstance(image_paths, list):
            image_paths = [image_paths]

        content_list = []
        
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    img = img.convert("RGB")
                    
                    # 🚨 [수정] 해상도 상향: 800px -> 1280px
                    # 등기부등본의 작은 글씨(날짜, 금액)를 위해 최소 1024~1280px 필요
                    # Qwen2.5-VL은 해상도 처리가 뛰어나므로 약간 커져도 속도 저하 적음
                    img.thumbnail((1280, 1280))
                    
                    temp_filename = f"/tmp/resized_{uuid.uuid4()}.jpg"
                    img.save(temp_filename, quality=90) # 품질 약간 상향
                    temp_files.append(temp_filename)
                    
                    content_list.append({"type": "image", "image": temp_filename})
            except Exception as e:
                print(f"⚠️ 이미지 전처리 실패 (Skip): {path} - {e}")

        # 프롬프트 적용
        final_prompt = prompt_text if prompt_text else OCR_SYSTEM_PROMPT
        content_list.append({"type": "text", "text": final_prompt})
        
        messages = [{"role": "user", "content": content_list}]

        # 전처리
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        # 생성
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs, 
                max_new_tokens=2048,
                do_sample=False,        # OCR은 랜덤성 제거 (Greedy Search)
                temperature=0.0,        # 환각 최소화
                repetition_penalty=1.05 # 반복 방지 (너무 높으면 성능 저하)
            )

        # 디코딩
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        
        return output_text, temp_files

    except Exception as e:
        raise e
    finally:
        # GPU 메모리 정리는 여기서 하지 않고 주기적으로 하거나, 
        # 필요 시 명시적으로 호출 (잦은 호출은 오히려 성능 저하)
        pass

# ==========================================
# 3. 메인 분석 함수 (Async Wrapper)
# ==========================================
async def analyze_images_with_llm(image_paths: list, prompt_text: str = None) -> dict:
    """
    FastAPI 라우터에서 호출되는 비동기 함수
    """
    temp_files_to_delete = []
    
    try:
        print("⚡ [Inference] 별도 스레드에서 모델 추론 시작...")
        
        # 🚨 [핵심 수정] Blocking 구간을 별도 스레드로 위임하여 서버 멈춤 방지
        output_text, temp_files = await asyncio.to_thread(
            _run_inference_sync, image_paths, prompt_text
        )
        temp_files_to_delete = temp_files

        # --- 후처리 (JSON 파싱) ---
        clean_text = output_text.strip()
        
        # 마크다운 제거 로직 강화
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            # 가끔 ``` 만 쓰는 경우 대응
            clean_text = clean_text.split("```")[1].strip()
            
        # 가끔 끝에 이상한 문자가 붙는 경우 대비 (JSON 닫는 괄호 뒤 제거)
        if "}" in clean_text:
            last_brace_index = clean_text.rfind("}")
            clean_text = clean_text[:last_brace_index+1]

        # JSON 변환
        try:
            parsed_json = json.loads(clean_text)
            
            # data 래핑 확인
            if "data" not in parsed_json:
                parsed_json = {"data": parsed_json}
                
            return {"status": "success", "text": parsed_json}
            
        except json.JSONDecodeError:
            print(f"⚠️ JSON 파싱 실패. 원본: {clean_text[:100]}...")
            # 비상용 구조체 반환
            fallback_json = {
                "data": {
                    "title": {}, 
                    "gaggu": [], 
                    "eulgu": [], 
                    "rawText": clean_text
                }
            }
            return {"status": "partial_success", "text": fallback_json}

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        emergency_json = {
            "data": {
                "title": {}, "gaggu": [], "eulgu": [], 
                "rawText": f"System Error: {str(e)}"
            }
        }
        return {"status": "error", "error": str(e), "text": emergency_json}

    finally:
        # 임시 파일 삭제
        for t_file in temp_files_to_delete:
            if os.path.exists(t_file):
                try: os.remove(t_file)
                except: pass
        
        # 메모리 정리는 요청 끝날 때 한번씩
        torch.cuda.empty_cache()
        gc.collect()