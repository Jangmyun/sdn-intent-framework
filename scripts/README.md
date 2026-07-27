# Pipeline Scripts

파이프라인 앱([Pipeline Guide](../docs/PIPELINE_GUIDE.md)) 전용 보조 스크립트입니다.
`requirements.txt`(pip) 환경이 필요하며, 모든 명령은 레포 루트에서 실행합니다.

| Script | Role |
| --- | --- |
| `generate_dataset.py` | 파이프라인용 인텐트 데이터셋 생성 |
| `validate_dataset.py` | 데이터셋 구조 검증 |
| `manual_traffic_check.py` | 트래픽 생성기 + 모니터링 수동 검증 (root + Mininet + ONOS 필요) |
| `make_exp1_pptx.py` | GOLD-350 Exp-1 결과 발표자료(pptx) 재생성 |

논문 재현 트랙의 운영 스크립트(ONOS 기동, Mininet 스모크, 설치)는
`research/scripts/`에 있습니다.
