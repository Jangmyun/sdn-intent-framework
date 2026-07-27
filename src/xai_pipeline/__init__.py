"""xai_pipeline — 자연어 인텐트를 ONOS FlowRule로 변환하는 End-to-End 파이프라인.

LLM/RAG 기반 인텐트 해석(stage1) → 결정론적 컴파일(stage2) → 정적 검증(stage3)
→ Digital Twin 검증(stage4) → XAI 설명(stage5) → ONOS 배포(stage6).
"""
