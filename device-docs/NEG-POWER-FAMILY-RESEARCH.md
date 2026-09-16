# SAES NEG POWER 제품군: 통신 호환성과 프로젝트 범위 조사

조사일: 2026-09-15. 범위: 제품·프로토콜 조사와 설계 판단. 장비 통신이나 제어 코드는 실행하지 않았다.

후속 구현: 이 조사 이후 SIP 구조를 따른 MINI용 읽기 전용 TCP relay를 구현했다.
아래의 “구현 전” 상태는 조사 당시의 기록이며, 최신 상태는
[구현 검증 기록](../.agents/VALIDATION.md)을 따른다. 실기 검증은 아직 수행하지 않았다.

## 결론

**프로젝트 범위는 NEG POWER 제품군으로 정했다.** 조사 후 사용자의 결정에 따라 이름은 기존 `seas` 철자를 유지한 `seas-neg-power-to-influxdb`로 확정했고, 로컬 폴더에도 적용했다. 제조사 철자는 SAES다. 이름 변경 시점에는 로컬 Git 저장소와 GitHub 원격 저장소가 아직 없었다.

MINI와 다채널 NEG POWER는 Ethernet Modbus TCP를 공유한다. 그러나 확인된 레지스터 배치는 다르다. 따라서 하나의 저장소·라이브러리 안에서 MINI와 다채널의 레지스터 정의와 해석을 분리하는 것이 적절하다. 주소가 다르다는 사실만으로 저장소를 MINI 전용으로 제한할 필요는 없다.

아래 세 가지는 서로 다른 주장이다.

1. **프로젝트 대상 제품군:** NEG POWER MINI, NEG POWER standard/LP/hybrid/SMALL.
2. **현재 확보한 구현 근거:** MINI의 주요 조회 맵은 동봉 Manager에서 복원했고, 다채널은 문서 일부와 외부 연동 사례만 확보했다.
3. **현재 구현·검증 상태:** 이 폴더에는 동작하는 NEG 클라이언트가 아직 없고, 어떤 모델도 이 프로젝트에서 실기 검증하지 않았다.

## 1. MINI 외에 확인한 제품

제조사 공통 사용자 매뉴얼 `M.HIST.0101.23 R2`, 2021-01-26, 36쪽의 4–5쪽과 26쪽에 다음 모델이 나온다. [공통 매뉴얼](https://www.manualslib.com/manual/2427840/Saes-Neg-Power.html), [출력 모듈 설명](https://www.manualslib.com/manual/2427840/Saes-Neg-Power.html?page=5), [구성표](https://www.manualslib.com/manual/2427840/Saes-Neg-Power.html?page=26).

| 제품 | 구성 | 제품 코드 |
| --- | --- | --- |
| NEG POWER C1–C4 | standard 출력 1–4개 | 3B0501–3B0504 |
| NEG POWER LP C1–C4 | low-power 출력 1–4개 | 3B0521–3B0524 |
| NEG POWER hybrid | standard와 LP 출력 혼합, 총 2–4개 | 3B0525–3B0530 |
| NEG POWER SMALL | 반폭 랙, standard/LP/혼합 출력 1–2개 | 3B0531–3B0535 |
| NEG POWER MINI | 별도 단일 출력 제품 | 3B0110, 동봉 MINI 매뉴얼 |

**SMALL과 MINI는 다른 제품이다.** SMALL은 다채널 계열의 작은 섀시이고, MINI는 별도 사용자 매뉴얼과 Manager를 사용하는 단일 출력 제품이다.

공통 매뉴얼은 standard 700 W와 LP 150 W 모듈을 같은 장비 안에서 혼합할 수 있다고 설명한다. 여기서 hybrid는 standard/LP 혼합을 뜻하며, 이온 펌프 전원과 NEG 전원을 통합한 NIOPS를 뜻하지 않는다.

제조사 Multicontroller 데이터시트도 standard/LP, 최대 4채널, Ethernet·RS232·RS485 Modbus, Windows/Linux 원격 소프트웨어를 함께 설명한다. LP의 대상 펌프 목록에 NEXTorr Z200도 포함된다. 따라서 Z200이라는 펌프 모델만으로 컨트롤러를 MINI로 확정할 수는 없다. [제조사 데이터시트, 외부 미러](https://saes.spegroup.ru/upload/iblock/a9f/6slhuff4lk21hphe33nuc2o3gf8vge5h.pdf).

## 2. 어느 수준에서 통신이 같은가?

| 항목 | MINI | NEG POWER 다채널 계열 | 판단 |
| --- | --- | --- | --- |
| Ethernet | Modbus TCP | Modbus TCP | 공통 통신 기반 가능 |
| 직렬 연결 | RS232, Modbus RTU | RS232 또는 RS485, Modbus RTU | RTU 프레임은 공유 가능, 포트 설정은 별도 |
| 출력 수 | 1 | standard/LP/hybrid 최대 4, SMALL 최대 2 | 데이터 모델에 채널 개념 필요 |
| 읽기 | 동봉 Manager에서 FC03 확인 | software manual을 인용한 연동자가 FC03 명시 | holding-register 읽기 공통 |
| 레지스터 배치 | 상태가 0x2000부터 | 출력별 0x1000 + 0x100 × 채널번호 구조가 인용됨 | 같은 맵 사용 불가 |
| 값 해석 | Manager에서 주요 값·워드 순서 복원 | 전체 형식·단위·경보 정의 미확보 | decoder는 분리 |

통신 인터페이스의 제조사 근거: [NEG POWER 매뉴얼 23쪽](https://www.manualslib.com/manual/2427840/Saes-Neg-Power.html?page=23), 동봉 `saes-neg_power_mini-user_manual-rev_4.pdf` 5·20쪽. 다채널의 Modbus 설정은 [13쪽](https://www.manualslib.com/manual/2427840/Saes-Neg-Power.html?page=13)에 있으며 직렬과 TCP/IP 모드를 설정한다. 장비가 포트를 가지고 있다는 사실과 해당 통신 모드가 활성화되어 있다는 사실은 구분해야 한다.

**standard/LP/hybrid/SMALL을 하나의 다채널 드라이버로 처리할 수 있을 가능성은 높다.** 공통 매뉴얼, 혼합 가능한 출력 모듈, 출력별 주소 구조가 그 근거다. 다만 이 자료만으로 모든 모델·펌웨어의 레지스터가 동일하다고 확정할 수는 없다. 이는 구현 방향에 대한 추론이며 호환성 보증이 아니다.

## 3. 다채널 레지스터 맵: 실제로 찾은 것

2021-04-24 EPICS Tech-talk에서 Scott A. Baily가 NEG POWER의 **software user manual**을 인용했다. 이는 제품 브로슈어보다 구체적인 프로토콜 자료가 존재한다는 근거다. 단, 인용된 원문 전체와 문서 버전, 장비의 정확한 제품 코드는 확보하지 못했다. [최초 연동 보고](https://epics.anl.gov/tech-talk/2021/msg00866.php).

인용 내용으로 확인되는 주소 구조:

```text
출력별 주소 = 0x1000 + 0x100 × 0부터 시작하는 출력번호 + 항목 offset

VOUT offset = 0x49
첫 번째 출력 VOUT = 0x1049
두 번째 출력 VOUT = 0x1149
```

같은 보고에서 FC03/FC10, 상태 영역 offset 0x40–0x80, 전류를 읽으려는 offset 0x4A가 등장한다. 전류 이름은 예제 record `TESTnegI`에서도 드러나지만, 전체 데이터 타입·스케일 명세를 대신하지는 못한다.

**이 주소들은 실기 검증된 완성 맵으로 취급하지 않는다.** 게시자의 0x1140부터 64-register 읽기는 `83 02`, 즉 illegal-data-address 예외를 받았다. 후속 답변은 unit ID와 읽기 길이 변경을 제안하며, 확인한 스레드에는 성공 결과가 없다. 특정 주소가 틀린 것인지, 범위 안의 미정의 레지스터 때문인지, 다른 원인인지는 결론낼 수 없다. [예외 해석](https://epics.anl.gov/tech-talk/2021/msg00867.php), [후속 제안](https://epics.anl.gov/tech-talk/2021/msg00868.php).

MINI에서 복원한 출력 전압 주소는 `0x2006`, 전류는 `0x2007`이다. 따라서 다채널의 위 구조를 MINI에 적용하거나 그 반대로 적용하면 안 된다. MINI 근거와 검증 범위는 [별도 조사 기록](NEG-POWER-MINI-MODBUS.md)에 보존했다.

## 4. 외부 연동 사례와 공개 코드 조사

### 연구시설의 Modbus TCP 사용

Saraf 외, *LCLS-II Accelerator Vacuum Control System Design, Installation and Checkout*, ICALEPCS 2023, Table 2는 SAES NEG Controller에 **Modbus TCP/IP + EPICS asyn/Modbus**를 명시한다. 그림의 일반적인 직렬 연결선만 보고 RS232 제품이라고 판단하면 안 된다. 다만 논문은 정확한 NEG POWER 모델이나 레지스터 맵을 공개하지 않으므로 MINI/SMALL 등의 호환성을 검증하는 자료는 아니다. [논문, PDF 3쪽 Table 2](https://proceedings.jacow.org/icalepcs2023/papers/thpdp090.pdf).

### 재사용 가능한 공개 NEG POWER 드라이버

GitHub 저장소/코드 검색과 EPICS 자료에서 실제 NEG POWER용으로 확인할 수 있는 완성 드라이버는 이번 조사로 확보하지 못했다. 이는 존재하지 않는다는 뜻은 아니다. 확인한 검색어는 `NEG POWER`, `NEG_POWER`, `negpower`, `negmini`, `saes modbus`, `saes neg`, `NEGmb`, `nextorr`, 그리고 `dls-controls`, `DiamondLightSource`, `slac-epics`, `epics-modules` 관련 검색이다. 수학의 negative power, sparse autoencoder, Windows `WSAESHUTDOWN` 등 동명이 검색 결과를 다수 차지했다.

2024년 EPICS의 “SAES NEG POWER support” 스레드도 내용을 구분해야 한다. Mark Rivers의 답변은 일반적인 EPICS Modbus 모듈 활용을 설명한다. Simon Friederich의 답변에 들어 있는 코드는 **NIOPS와 SIP**용이며, SIP는 UDP라고 직접 명시한다. 이 코드를 NEG POWER용 맵으로 재사용할 근거는 없다. [일반 Modbus 답변](https://epics.anl.gov/epics/tech-talk/2024/msg01334.php), [실제 첨부 코드의 대상](https://epics.anl.gov/tech-talk/2024/msg01336.php).

### 추가 자료를 해석할 때의 한계

- 2022년 pyModbusTCP 사용자는 제조사에게 받은 register map이 있다고 보고했고, 직접 같은 서브넷으로 연결했을 때 응답을 얻었다. 그러나 링크가 MINI와 Multicontroller를 함께 소개하는 브로슈어여서 정확한 모델을 구분할 수 없다. 이를 특정 모델의 맵 검증이나 프로토콜 결함의 근거로 삼지 않았다. [원 사용자 스레드](https://control.com/forums/threads/help-with-pymodbustcp.50645/).
- Wang 외 2024년 *Design and implementation of intelligent control system for non-evaporable getter pumps*는 Modbus RTU 기반 NEG 제어 논문이지만, 확인한 본문에 SAES NEG POWER 제품명이 없고 400 W/8 A 전원을 설명한다. SAES 드라이버 자료에서 제외했다. [논문](https://www.researchgate.net/publication/383073441_Design_and_implementation_of_intelligent_control_system_for_non-evaporable_getter_pumps).
- Agilent는 SAES NEG POWER MINI와 larger NEG POWER를 별도로 판매·설명한다. OEM 유통 경로를 교차 확인할 수 있지만 레지스터 호환성 명세는 아니다. [Agilent 제품 설명](https://www.agilent.com/en/product/vacuum-technologies/ion-pumps-controllers/ion-pump-controllers/controllers-for-neg-cartridges).

## 5. 어디까지를 NEG POWER 범위에 넣을 것인가?

| 대상 | 권고 | 이유 |
| --- | --- | --- |
| NEG POWER MINI | 포함, 최초 구현 대상 | 보유 장비 후보, 동봉 소프트웨어 분석 근거 |
| NEG POWER C1–C4 / LP / hybrid / SMALL | 포함, 향후 다채널 지원 대상 | 제조사가 묶은 제품군과 공통 Modbus 기반 |
| NIOPS | 초기 범위에서 제외 | 이온/NEG 통합 전원이라는 별도 제품 계열 |
| NEG Pump Controller V1.1 | 초기 범위에서 제외 | 구형 전원·온도조절기 구조, NEG POWER 맵 호환성 근거 없음 |
| 다른 회사의 NEG용 전원 | 제외 | 같은 펌프를 가열할 수 있다는 것으로 통신 호환성을 뜻하지 않음 |

구형 **NEG Pump Controller V1.1**도 실제 SAES 제품이다. 제조사 자료는 1100 W 전원과 선택 사양 thermoregulator를 통한 RS485 원격 제어를 설명한다. RS485라는 물리 인터페이스만으로 현행 NEG POWER의 Modbus 맵을 가정할 수 없다. [SAES SORB-AC 제조사 자료, 대학 미러](https://www.npl.washington.edu/TRIMS/sites/sand.npl.washington.edu.TRIMS/files/manuals-documentation/SAES-SORB%20AC%20Cartridge%20Pumps%20MK5%20Series_1880.pdf).

NIOPS-03은 별도의 RS232 ASCII 및 RS485 Modbus 통신 장을 갖는 제품이다. NEG 기능이 있다는 이유로 NEG POWER와 같은 드라이버라고 분류하지 않는다. [제조사 NIOPS-03 매뉴얼, Caltech 미러](https://mmrc.caltech.edu/Sample%20Suitcase/UHV%20suitcase/NexTorr%20Power%20Supply%20NIOPS-03%20Manual.pdf).

## 6. 라이브러리·relay 설계에 대한 권고

이 절은 위 프로토콜 근거에서 도출한 제안이다. Sinclair relay 공통 규약이나 이미 구현된 구조라는 뜻은 아니다.

- **저장소:** NEG POWER 제품군 전체를 대상으로 이름을 잡는다.
- **처음 구현:** MINI 조회를 먼저 구현하되, 지원 목록에는 실제 검증한 모델·펌웨어·연결 방식만 기재한다.
- **공통으로 재사용할 부분:** Modbus 연결, holding-register 요청, 응답 오류 처리, 수집 시각과 업로드 흐름.
- **모델별로 둘 부분:** 주소, 읽기 묶음, 값 타입·스케일·워드 순서, 상태·경보 비트, firmware별 기능.
- **MINI도 출력 하나를 가진 장치로 표현:** 향후 다채널 추가 때 단일 출력 가정을 여러 곳에서 고치지 않게 한다. 실제 InfluxDB 필드/tag 결정은 구현 단계에서 기존 relay들과 맞춘다.
- **다채널은 모듈 구성을 별도 정보로 표현:** LP와 standard가 같은 장비에 섞일 수 있으므로 한 장비 전체를 단일 power class로 단정하지 않는다.
- **자동 감지는 보류:** 제품/firmware 식별 레지스터가 충분히 확인되기 전에는 사용자가 지정한 모델을 기준으로 선택한다. 현재 버전 레지스터 일부를 알아냈다는 것으로 universal auto-detection이 가능한 것은 아니다.

예상되는 드라이버 구분은 `mini`와 `multicontroller` 두 가지다. LP·hybrid·SMALL마다 별도 드라이버를 미리 만들 필요는 없다. 동일 맵이 확인되면 채널 수·모듈 정보로 처리하고, 실제 차이가 확인되면 필요한 부분만 나눈다.

공통 API를 미리 크게 만들거나 현재 없는 다채널 지원을 빈 구현으로 추가할 필요도 없다. 당장은 `saes_neg_power_mini_client.py`로 시작해도 제품군 범위의 저장소 이름과 모순되지 않는다. 독립 라이브러리로 성장하면 `saes_neg_power` 아래에 모델별 구현을 둘 수 있다.

## 7. 아직 필요한 문서와 검증

**전체 다채널 Modbus map 원문은 확보하지 못했다.** 공개 사용자 매뉴얼은 통신 종류와 설정을 알려주지만, 필요한 레지스터 표 전체를 제공하지 않는다. 제조사 [Manuals / Documents](https://www.saesgetters.com/highvacuum/solutions/manuals-documents/)는 이번 접속에서 로그인 페이지로 이동했다. Edinburgh CARME의 검색에 노출된 PDF는 직접 다운로드할 때 401 응답을 받아, 접근 가능한 ManualsLib의 제조사 문서를 사용했다.

다음 확보 대상은 단순한 hardware user manual보다 구체적이다.

1. **NEG POWER Multicontroller software user manual / Modbus communication specification** 전체와 문서 revision.
2. C1–C4, LP, hybrid, SMALL에 대한 공통 적용 범위와 firmware별 차이.
3. 컨트롤러/모듈 식별, 채널 수, 설치 모듈 종류, firmware 읽기.
4. 전압·전류·온도·시간·경보의 주소, 타입, 스케일, 워드 순서, 미지원 값 표현.
5. 허용되는 연속 읽기 범위, unit ID, TCP 연결 제한과 직렬 통신 설정.
6. 쓰기 기능을 실제로 추가할 때는 명령 주소, 상태 전이와 local/remote 동작 규칙.

문서가 없는 경우 다채널용 제조사 Manager 배포본도 다음 분석 자료가 될 수 있다. MINI Manager의 DLL 분석 결과를 다채널 맵으로 확장해서는 안 된다. 이번 조사에서는 다채널 Manager 배포본 자체를 확보하지 못했다.

제조사 요청이나 연구시설 담당자에게 보내는 연락은 하지 않았다. 다음 요청은 “NEG POWER 일반 매뉴얼”보다 위 software/Modbus 문서와 모델 호환표를 정확히 지정하는 것이 효율적이다.

## 8. 조사 산출물과 재현 범위

- 이 문서: 제품군 범위 판단, 확인 근거와 미확인 사항.
- `NEG-POWER-MINI-MODBUS.md`: 동봉 MINI Manager의 복원 맵, 파일 해시, 오프라인 검증. 이 문서의 기존 MINI 전용 저장소 이름 권고는 현재 제품군 조사 결론으로 대체했다.
- `NEG-POWER-Multicontroller-datasheet.pdf`: 제조사 데이터시트의 공개 미러 사본. SHA-256 `1de60b423e17bdf100c67ff707da61097a42deaa0ca11e665bd20e3a6be051dd`.
- 공개 검색과 문서 대조의 결과이지 SAES의 제품 지원 확인서가 아니다. 판매·펌웨어의 최신 전체 목록을 보증하지 않으며, 확인한 모델은 명시한 문서 revision을 기준으로 한다.
