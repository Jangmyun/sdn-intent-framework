# 0 Project Overview

## 1. Project Information 프로젝트 정보

> Digital Twin 검증과 XAI 설명 계층을 활용한 안전한 LLM/RAG 기반 Intent-Driven SDN 운영 자동화 시스템

핵심은 LLM이 SDN 정책을 생성하는 데에 그치는게 아니라, LLM이 생성한 정책을 인간이 검증 가능하고 설명 가능하게 만들어 안전하게 적용하는 것을 중점으로 한다.

## 2. 연구 배경 및 동기

네트워크 운영은 zero-touch 자동화를 점차 도입하고 있다. 운영을 사람이 직접 수행하지 않고, AI·Agent·Digital Twin 을 결합해 자동화하는 흐름이 보인다.

한편 LLM 기반 네트워크 관리 연구에서는 LLM이 사용자의 intent 해석과 운영 자동화에 유용하다는 점을 보이면서도 hallucination, domain adaptation 부족, 잘못된 설정 생성을 핵심 한계로 지적한다. 본 프로젝트는 이 한계를 RAG(context 주입), Static Validator(정적 검사), Digital Twin(사전 검증), XAI(근거 설명)의 결합으로 완화하는 것을 목표로 한다.

## 3. 문제 정의

기존 SDN 운영에서 관리자는 다음을 직접 수행한다.

1. 네트워크 상태 확인
2. 병목·장애 원인 추론
3. 정책 수립
4. OpenFlow rule 적용
5. 적용 후 문제 여부 확인

본 시스템은 이 과정을 다음 파이프라인으로 대체하고자 한다.

```text
사용자 자연어 Intent
-> LLM/RAG 가 Intent 해석
-> SDN 정책 후보 생성
-> Static Validator가 기존 Rule 충돌 검사
-> Digital Twin에서 사전 검증
-> XAI Layer가 근거 설명
-> 안전한 상황에서만 실제 Controller (Ryu) 에 적용
```

완전 자율 네트워크가 아니라 AI 기반 네트워크 운영 assistant 역할을 수행하는 것으로 한정한다.
