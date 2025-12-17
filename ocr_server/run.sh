echo "🧹 [1/4] 강력 청소 시작... (GPU 점유 프로세스 전체 사살)"

# 1. GPU를 쓰고 있는 모든 녀석 강제 종료 (컨테이너에 fuser가 없으므로 주석 처리 또는 제거)
# fuser -k -9 /dev/nvidia0

# 2. 혹시 모를 파이썬 잔여물 정리
pkill -9 -f uvicorn
pkill -9 -f python

# 3. 죽을 때까지 잠시 대기
echo "   ...3초 대기 (메모리 반환 중)..."
sleep 3

# 4. 임시 파일 삭제
rm -rf /workspace/temp_uploads/*

echo "🧹 [2/4] GPU 상태 확인"
nvidia-smi

# 5. 환경 변수 설정
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HOME="/workspace/hf_cache"

echo "🐍 [3/4] 가상 환경 활성화 및 실행 경로 설정"

# ★ 핵심 수정: 숨겨진 디렉토리 .venv를 명시하고, activate 대신 python 경로 직접 사용
# source .venv/bin/activate # 이 명령어는 nohup과 함께 사용 시 문제가 발생할 수 있습니다.
# 대신, 아래에서 파이이썬 인터프리터 경로를 직접 지정합니다.

echo "🚀 [4/4] 서버 실행 중..."

# ★ 최종 실행 명령어 수정: 
#    1. 가상 환경의 python3.11 인터프리터를 직접 사용합니다. (가장 안정적)
#    2. uvicorn을 python 모듈로 실행합니다.
nohup .venv/bin/python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 3003 > ocr_api.log 2>&1 &

echo "✅ 서버가 시작되었습니다! 로그 확인: tail -f ocr_api.log"