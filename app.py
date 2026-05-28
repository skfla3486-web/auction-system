# -*- coding: utf-8 -*-
"""
법원경매 물건 검색 시스템 (전면 재작성판)
주요 수정
  1) 용도 필터를 mvprpRletDvsCd(부동산 종류 코드)로 정상 연결 → 검색 필터 정상 작동
  2) 라디오/체크박스 대비 문제 해결(선택 시 흰 글씨, 기본 점 제거)
  3) 카드/헤더 HTML 들여쓰기로 인한 태그 노출(Markdown 코드블록 오인) → 평탄화 처리
  4) 상세 페이지를 탭으로 분리
"""
import re
import io
import math
import base64
import statistics
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import streamlit as st
from datetime import date, timedelta

# ══════════════════════════════════════════════════════════════════════════════
#  상수 / 설정
# ══════════════════════════════════════════════════════════════════════════════
BASE = "https://www.courtauction.go.kr"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")
H_BASE = {"Accept": "application/json", "Content-Type": "application/json;charset=UTF-8",
          "Origin": BASE, "Referer": f"{BASE}/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml",
          "User-Agent": UA}
H_SEARCH = {**H_BASE, "Submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch"}
H_DETAIL = {**H_BASE, "Submissionid": "mf_wfm_mainFrame_sbm_selectAuctnCsSrchRslt"}

# 부동산 종류(용도) → mvprpRletDvsCd  ※ 검색 핵심 필터
RLET_KIND = {"전체": "", "아파트": "00031R", "다세대/빌라": "00032R", "단독/다가구": "00030R",
             "오피스텔": "00033R", "근린상가": "00034R", "근린시설": "00035R", "사무실": "00036R",
             "숙박시설": "00037R", "공장/창고": "000Y0R", "토지": "000Z0R", "임야": "000X0R",
             "기타건물": "000W0R"}
RLET_CD2NM = {v: k for k, v in RLET_KIND.items() if v}


def dspsl_dae():
    return [(c, n) for c, n in DSPSL_USG.items() if c.endswith("0000")]


def dspsl_jung(dae):
    return [(c, n) for c, n in DSPSL_USG.items()
            if c.endswith("00") and not c.endswith("0000") and dae and c[0] == dae[0]]


def dspsl_so(jung):
    return [(c, n) for c, n in DSPSL_USG.items()
            if not c.endswith("00") and jung and c[:3] == jung[:3]]

COURTS_FB = [("서울중앙지방법원", "B000210"), ("서울동부지방법원", "B000220"), ("서울남부지방법원", "B000230"),
             ("서울북부지방법원", "B000240"), ("서울서부지방법원", "B000250"), ("의정부지방법원", "B000310"),
             ("인천지방법원", "B000320"), ("수원지방법원", "B000330"), ("춘천지방법원", "B000410"),
             ("대전지방법원", "B000510"), ("청주지방법원", "B000520"), ("대구지방법원", "B000610"),
             ("부산지방법원", "B000710"), ("울산지방법원", "B000720"), ("창원지방법원", "B000730"),
             ("광주지방법원", "B000810"), ("전주지방법원", "B000820"), ("제주지방법원", "B000910")]

KOR = {
    # 목록/물건
    "dspslObjctSeq": "목록번호", "bldSdtrSeq": "목록번호", "rletDvsDts": "구분", "auctnLstNm": "구분",
    "rprsLtnoAddr": "지번", "rletStLtnoAddr": "지번",
    "userPrintSt": "소재지", "userSt": "소재지", "printSt": "소재지", "storgPlcRdnmAddr": "소재지(도로명)",
    "adongSdNm": "시도", "adongSggNm": "시군구", "adongEmdNm": "읍면동", "adongRiNm": "리",
    "objctArDts": "면적(㎡)", "ldcgDts": "지목", "ldcgNm": "지목", "bldDtlDts": "건물상세",
    "pjbBuldList": "건물현황", "dspslStkCtt": "비고", "ultmtNm": "종국결과", "lesCnt": "임차인수",
    "gdsPossCtt": "물건현황/점유",
    # 기일
    "dxdyYmd": "기일", "dspslDxdyYmd": "기일", "dxdyHm": "시각", "dxdyTime": "기일(시각)",
    "dxdyPlcNm": "장소", "dspslPlcNm": "장소", "auctnDxdyKndNm": "기일종류", "dxdyKndNm": "기일종류",
    "auctnDxdyRsltNm": "결과", "dxdyRsltNm": "결과", "dxdyRslt": "결과",
    "lwsDspslPrc": "최저매각가", "tsLwsDspslPrc": "최저매각가", "fstPbancLwsDspslPrc": "최저매각가",
    "aeeEvlAmt": "감정평가액", "bidderNcnt": "입찰자수",
    # 이해관계인
    "auctnIntrpsDvsNm": "구분", "intrpsDvsNm": "구분", "intrpsNm": "성명/명칭", "rprsvNm": "성명/명칭",
    # 문건/송달
    "dlvrYmd": "접수일", "rcptYmd": "접수일", "dlvrbkRegYmd": "접수일", "lastDlvrblRchYmd": "도달/송달",
    "ofdocRcptYmd": "접수일", "rcptDts": "접수내역",
    "dlvrDts": "내용", "dlvrOfdocDvsNm": "구분", "dlvrOfdocNm": "문건명",
    "ofdocNm": "문건명", "dlvrCtt": "내용", "dlvrRsltNm": "결과", "sndngDvsNm": "송달구분",
    "sndngRsltNm": "송달결과", "rcptrNm": "수령인", "rcptrTypNm": "수령인구분", "sbmtrNm": "제출인",
    "ofdocSbmtrNm": "제출인", "dlvrDvsNm": "구분", "dlvrNm": "문건명",
    # 현황조사
    "exmndcSndngYmd": "현황조사명령 송달일", "exmndcRcptnYmd": "현황조사서 접수일", "exmnDtDts": "조사일시",
    "lstPossRltnDts": "점유관계", "curstExmnYmd": "조사일", "curstExmnrNm": "조사자", "curstExmnCtt": "조사내용",
    # 임차인
    "basAddr": "기본주소", "objctDtlAddr": "상세주소", "mvinDtlCtt": "전입일",
    "ocpnNm": "점유자", "ocpnRelNm": "점유관계", "lsYn": "임대차여부", "lsDpstAmt": "보증금",
    "mRntAmt": "월세", "lsBgngYmd": "임대시작", "lsEndYmd": "임대종료",
    "rntrNm": "임차인", "rntrTypNm": "구분", "rntrAmt": "보증금", "rntrMnthlyAmt": "월세",
    "rntrMvInYmd": "전입일", "rntrLeaseEndYmd": "계약만료", "rntrRgstYn": "확정일자", "rntrOccpnYn": "점유",
    # 감정평가요항
    "aeeWevlMnpntDvsNm": "항목", "aeeWevlMnpntCtt": "내용", "aeeWevlMnpntNm": "항목",
    # 도로명 주소 구성요소
    "rdnmSdNm": "도로명시도", "rdnmSggNm": "도로명시군구", "rdnm": "도로명",
    "rdnmBldNo": "건물번호", "rdnmRefcAddr": "참조주소", "bldNm": "건물명",
}
SKIP = {"cortOfcCd", "dspslGdsSeq", "pgmId", "csNo", "srnSaNo", "srchRowIndex", "boCd",
        "cortCd", "saNo", "saCd", "userCsNo", "mvprpRletDvsCd", "rletStLtnoSeq",
        "aeeWevlMnpntSeq", "dspslGdsLstSeq", "ordTsCnt", "auctnInfOriginDvsCd"}

# 항상 숨길 컬럼(내부값/노이즈)
DROP_COLS = {"objctRletCarUnqNo", "gdsDtlSrchYn", "cortAuctnDvsPicCnt", "zpcd", "selectedYn",
             "value", "reltCsNo", "auctnCurstExmnTrsmStatCnt", "userReltCsNo", "rgstRcrdYn",
             "fstmLstPossRltnDts", "scntmLstPossRltnDts", "printRltnDts"}
# 통째로 숨길 리스트/테이블 키(내부 상태값)
DROP_TABLES = {"dlt_mrgDpcnSbxLst", "dlt_ordTsPicDvs", "dlt_curstExmnDpcnMrg"}
# 표에서 빼는 긴 서술 컬럼(별도 블록으로 표시)
LONG_TEXT_COLS = {"gdsPossCtt", "aeeWevlMnpntCtt", "lstPossRltnDts", "printRltnDts",
                  "fstmLstPossRltnDts", "scntmLstPossRltnDts"}
# 주소 구성요소 / 전체주소
ADDR_PARTS = {"adongSdNm", "adongSggNm", "adongEmdNm", "adongRiNm",
              "rdnmSdNm", "rdnmSggNm", "rdnm", "rdnmBldNo", "rdnmRefcAddr", "bldNm"}
FULL_ADDR = {"printSt", "userPrintSt", "userSt", "storgPlcRdnmAddr", "basAddr"}

PRICE_OPTS = {"전체": "", "1천만": "10000000", "3천만": "30000000", "5천만": "50000000",
              "1억": "100000000", "2억": "200000000", "3억": "300000000", "5억": "500000000",
              "10억": "1000000000", "20억": "2000000000", "50억": "5000000000", "100억": "10000000000"}
FLBD_OPTS = {"전체": "", "0회": "0", "1회": "1", "2회": "2", "3회": "3", "4회": "4", "5회이상": "5"}
RATE_OPTS = {"전체": "", "20%": "20", "30%": "30", "40%": "40", "50%": "50",
             "60%": "60", "70%": "70", "80%": "80", "90%": "90"}
STATUS_OPTS = {"진행중": "0004601", "전체": "0004601", "매각": "0004603", "취하/취소": "0004604", "기각/각하": "0004605"}
BID_DVS = {"전체": "", "기일입찰": "000331", "기간입찰": "000332"}
SPECIAL_CONDS = [("법정지상권", "0004301"), ("별도등기", "0004302"), ("유치권", "0004303"),
                 ("분묘기지권", "0004304"), ("재매각", "0004305"), ("특별매각조건", "0004306"),
                 ("농지취득", "0004307"), ("예고등기", "0004308"), ("선순위", "0004309"),
                 ("우선매수신고", "0004310"), ("맹지", "0004311")]
SPC_CD2NM = {cd: nm for nm, cd in SPECIAL_CONDS}
SPC_CD2NM["0004399"] = "특수조건모두제외"
YEARS = [str(y) for y in range(2026, 2009, -1)]

# ══════════════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
*{box-sizing:border-box}
html,body,[class*="css"]{font-family:'Noto Sans KR',-apple-system,sans-serif!important}
#MainMenu,footer,header{visibility:hidden}
.block-container{padding:0 0 40px!important;max-width:1160px!important;margin:0 auto!important}
[data-testid="stAppViewContainer"]{background:#eceff4}

/* 헤더 */
.top-bar{background:linear-gradient(135deg,#11254a 0%,#1d3a72 100%);padding:16px 30px;
  display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 10px rgba(0,0,0,.18);
  border-radius:0 0 10px 10px;margin-bottom:16px}
.top-bar .logo{color:#fff;font-size:21px;font-weight:800;letter-spacing:-.5px;display:flex;align-items:center;gap:9px}
.top-bar .logo span{font-weight:400;font-size:12.5px;opacity:.6;margin-left:6px}
.top-bar .tagline{color:rgba(255,255,255,.5);font-size:12px}

/* 검색 패널 */
.panel{background:#fff;border-radius:10px;box-shadow:0 1px 10px rgba(0,0,0,.05);
  padding:8px 24px 16px;border:1px solid #e3e8ef;margin-bottom:16px}
.flabel{font-size:12.5px;font-weight:700;color:#3b4a5e;padding-top:9px}
.sep{border:none;border-top:1px solid #eef2f7;margin:10px 0}

/* 버튼 */
div[data-testid="stButton"]>button{border-radius:7px!important;font-weight:600!important;
  font-size:13.5px!important;transition:all .15s!important;padding:8px 16px!important}
div[data-testid="stButton"]>button[kind="primary"]{
  background:linear-gradient(135deg,#1d3a72,#2563eb)!important;border:none!important;color:#fff!important}
div[data-testid="stButton"]>button[kind="primary"]:hover{
  box-shadow:0 4px 13px rgba(37,99,235,.32)!important;transform:translateY(-1px)!important}
div[data-testid="stButton"]>button:not([kind="primary"]){
  border:1px solid #cdd6e0!important;color:#475569!important;background:#fff!important}
div[data-testid="stButton"]>button:not([kind="primary"]):hover{background:#f5f8fc!important;border-color:#93c5fd!important}

/* ── 라디오: 알약형, 대비 확실 (선택=남색바탕 흰글씨, 기본 점 숨김) ── */
div[role="radiogroup"]{gap:7px!important;flex-wrap:wrap!important}
div[role="radiogroup"]>label{background:#eef2f7!important;border:1px solid #dde4ec!important;
  border-radius:18px!important;padding:5px 16px!important;margin:0!important;cursor:pointer;transition:all .14s}
div[role="radiogroup"]>label>div:first-child{display:none!important}
div[role="radiogroup"]>label p,div[role="radiogroup"]>label div{color:#475569!important;font-size:13px!important}
div[role="radiogroup"]>label:hover{border-color:#93c5fd!important}
div[role="radiogroup"]>label:has(input:checked){background:#1d3a72!important;border-color:#1d3a72!important}
div[role="radiogroup"]>label:has(input:checked) p,
div[role="radiogroup"]>label:has(input:checked) div{color:#ffffff!important;font-weight:600!important}

/* 체크박스 텍스트 대비 */
div[data-testid="stCheckbox"] label p,div[data-testid="stCheckbox"] label div{color:#3b4a5e!important;font-size:13px!important}

/* 셀렉트/인풋 */
div[data-testid="stSelectbox"]>div>div,div[data-testid="stTextInput"]>div>div>input{
  border-radius:6px!important;font-size:13px!important;border-color:#dde4ec!important}

/* 통계바 */
.r-stat{font-size:13px;color:#64748b;margin:2px 0 12px;padding:0 2px}
.r-stat b{color:#11254a;font-size:15.5px}

/* ── 결과 카드 ── */
.card{background:#fff;border:1px solid #e2e8f0;border-radius:9px;overflow:hidden;
  transition:box-shadow .15s,border-color .15s;margin-bottom:2px}
.card:hover{border-color:#93c5fd;box-shadow:0 3px 16px rgba(37,99,235,.1)}
.chead{display:flex;align-items:center;gap:9px;padding:11px 18px;background:#f7f9fc;border-bottom:1px solid #eef2f7}
.cno{font-size:15px;font-weight:700;color:#11254a}
.ccourt{font-size:12px;color:#64748b;margin-left:auto}
.bdg{display:inline-block;padding:3px 9px;border-radius:5px;font-size:11px;font-weight:700;white-space:nowrap}
.bdg-type{background:#eaf1ff;color:#2563eb}
.bdg-ok{background:#dcfce7;color:#15803d}
.bdg-sold{background:#dbeafe;color:#1d4ed8}
.bdg-no{background:#fee2e2;color:#b91c1c}
.bdg-etc{background:#f1f5f9;color:#475569}
.bdg-flbd{background:#fff3e6;color:#c2410c}
.cbody{padding:14px 18px 6px}
.caddr{font-size:13.5px;color:#1e293b;font-weight:600;margin-bottom:12px}
.cprices{display:flex;border:1px solid #eef2f7;border-radius:7px;overflow:hidden;margin-bottom:6px}
.cp{flex:1;padding:9px 12px;text-align:center}
.cp+.cp{border-left:1px solid #eef2f7}
.cplabel{font-size:11px;color:#9aa7b8;margin-bottom:3px}
.cpval{font-size:15px;font-weight:700;color:#1e293b}
.cpval.red{color:#dc2626}
.cprate{font-size:11px;color:#9aa7b8;font-weight:500;margin-left:2px}

/* ── 상세 ── */
.dhead{background:linear-gradient(135deg,#11254a,#1d3a72);border-radius:11px;padding:22px 26px;
  color:#fff;margin-bottom:14px}
.dcs{font-size:23px;font-weight:800;letter-spacing:-.5px}
.dsub{font-size:13px;opacity:.85;margin:6px 0 13px}
.dsub .tag{background:rgba(255,255,255,.16);padding:3px 11px;border-radius:6px;font-size:12px;font-weight:700;margin-right:6px}
.daddr{background:rgba(255,255,255,.12);border-radius:8px;padding:11px 16px;font-size:13px;line-height:1.7}
.dgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
.dbox{background:rgba(255,255,255,.1);border-radius:8px;padding:12px 15px}
.dboxl{font-size:11px;opacity:.7;margin-bottom:4px}
.dboxv{font-size:16px;font-weight:700}
.dboxv.red{color:#fca5a5;font-size:18px}
.drmk{background:#fffbeb;color:#92400e;border-radius:8px;padding:10px 15px;font-size:13px;line-height:1.6;margin-top:12px}

.sec{font-size:14px;font-weight:700;color:#11254a;border-left:4px solid #2563eb;padding:3px 0 3px 11px;margin:6px 0 10px}
.dt-table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0}
.dt-table th{background:#f1f5f9;color:#475569;padding:9px 11px;font-weight:600;text-align:center;border-bottom:1px solid #e2e8f0;border-right:1px solid #e8edf3;white-space:nowrap;font-size:12.5px}
.dt-table td{background:#fff;padding:9px 11px;border-bottom:1px solid #f4f7fa;border-right:1px solid #f4f7fa;color:#334155;vertical-align:top;text-align:center}
.dt-table tr:last-child td{border-bottom:none}
.dt-table tr:hover td{background:#fafcff}
.kv{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}
.kv th{width:130px;background:#f1f5f9;color:#475569;text-align:right;padding:9px 14px;font-weight:600;border-bottom:1px solid #eef2f7;border-right:1px solid #e2e8f0;font-size:12.5px}
.kv td{padding:9px 14px;color:#334155;border-bottom:1px solid #eef2f7}
.erow{display:flex;border:1px solid #e2e8f0;border-bottom:none;font-size:13px}
.erow:last-child{border-bottom:1px solid #e2e8f0}
.ek{width:160px;flex-shrink:0;background:#f7f9fc;color:#3b4a5e;font-weight:700;padding:12px 16px;border-right:1px solid #e2e8f0}
.ev{padding:12px 16px;color:#374151;line-height:1.75;white-space:pre-wrap}
.nodata{text-align:center;padding:30px;color:#9aa7b8;font-size:13px;background:#f7f9fc;border-radius:8px;border:1px dashed #cdd6e0;margin-bottom:12px}

/* 탭 */
button[data-baseweb="tab"]{font-size:13.5px!important;font-weight:600!important}
button[data-baseweb="tab"][aria-selected="true"]{color:#1d3a72!important}
div[data-baseweb="tab-highlight"]{background:#2563eb!important}

/* 빈 화면 */
.empty{text-align:center;padding:60px 20px;color:#9aa7b8}
.empty .ico{font-size:46px;margin-bottom:10px}
.empty .t1{font-size:16px;font-weight:700;color:#64748b;margin-bottom:5px}
.empty .t2{font-size:13px}
</style>
"""

# ══════════════════════════════════════════════════════════════════════════════
#  헬퍼
# ══════════════════════════════════════════════════════════════════════════════
def H(s):
    """HTML 평탄화: 줄별 좌우 공백 제거 후 결합 → Markdown 코드블록 오인/태그 노출 방지"""
    return "".join(line.strip() for line in str(s).splitlines())


def md(html):
    st.markdown(H(html), unsafe_allow_html=True)


def _post(url, payload, hdr=None, timeout=12):
    try:
        r = requests.post(url, headers=hdr or H_BASE, json=payload, timeout=timeout)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def _unwrap(raw):
    """응답 본문 평탄화. 실제 데이터는 data.dma_result 아래에 있는 경우가 많아
    dma_result 하위 키를 data 레벨로 끌어올린다(기존 dlt_* 형제 키도 보존)."""
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return {}
    inner = data.get("dma_result")
    if isinstance(inner, dict):
        merged = dict(data)
        merged.update(inner)
        return merged
    return data


# 감정평가요항 항목코드 → 항목명
AEE_ITM = {"00083001": "위치 및 주위환경", "00083002": "위치 및 부근의 상황",
           "00083003": "교통상황", "00083004": "인접 도로상태", "00083005": "인접 도로상태등",
           "00083006": "이용상태", "00083007": "이용상태 및 장래성", "00083008": "형태 및 이용상태",
           "00083009": "토지의 형상 및 이용상태", "00083010": "토지의 상황",
           "00083011": "토지이용계획 및 제한상태", "00083012": "도시계획 및 기타공법상의 제한사항",
           "00083013": "제시목록 외의 물건", "00083014": "공부와의 차이", "00083015": "건물의 구조",
           "00083016": "건물의 구조 및 현상", "00083017": "설비내역", "00083018": "부합물 및 종물",
           "00083019": "기계/기구의 현상", "00083020": "공작물의 현상", "00083021": "년식 및 주행거리",
           "00083022": "색상", "00083023": "관리상태", "00083024": "사용연료", "00083025": "유효검사기간",
           "00083026": "기타참고사항(임대관례 및 기타)", "00083027": "기타참고사항",
           "00083028": "기타(옵션등)", "00083029": "입지조건", "00083030": "임지사항",
           "00083031": "임목상황", "00083032": "사업체의 개요", "00083033": "어종 및 어기",
           "00083034": "어장의 시설현황", "00083035": "어획고 및 동변천상황과 판로", "00083036": "경영상황"}
# 감정평가요항표 종류(AEE_WEVL_MNPNT_TBLT_DVS_CD)
AEE_TBLT = {"00082001": "토지 감정평가요항표", "00082002": "건물 감정평가요항표",
            "00082003": "구분건물 감정평가요항표", "00082004": "공장 감정평가요항표",
            "00082005": "자동차 감정평가요항표", "00082006": "임야 감정평가요항표",
            "00082007": "어업권 감정평가요항표"}
# 종국구분(ULTMT_DVS_CD)
ULTMT_DVS = {"044": "이송", "107": "기각", "108": "각하", "201": "배당종결", "204": "취하",
             "205": "취소", "099": "기타", "000": "미종국", "501": "<(재)항고>인용",
             "502": "<(재)항고>기각", "991": "사건부 참조", "992": "정보화 2413-30호에 의하여 종결처리함"}
# 기일종류(AUCTN_DXDY_KND_CD)
DXDY_KND = {"01": "매각기일", "02": "매각결정기일", "03": "대금지급기한", "04": "대금지급및 배당기일",
            "05": "배당기일", "06": "일부배당", "07": "일부배당 및 상계", "08": "심문기일",
            "09": "추가배당기일", "11": "개찰기일"}


def _items(raw, *keys):
    data = raw.get("data") if isinstance(raw, dict) else raw
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
    return []


def _nm_cd(items):
    r = {}
    for i in items:
        if not isinstance(i, dict):
            continue
        if "name" in i and "code" in i:
            if i["name"]:
                r[i["name"]] = i["code"]
        else:
            nm = next((i[k] for k in i if k.endswith(("Nm", "nm"))), None)
            cd = next((i[k] for k in i if k.endswith(("Cd", "cd"))), None)
            if nm and cd:
                r[nm] = cd
    return r


def _p(row, *keys, default="-"):
    for k in keys:
        if not isinstance(k, str):
            continue
        v = row.get(k) if isinstance(row, dict) else None
        if v not in (None, ""):
            return str(v)
    return default


def _d(v):
    s = str(v).strip() if v else ""
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}.{s[4:6]}.{s[6:]}"
    return s or "-"


def fmt_krw(v):
    try:
        n = int(str(v).replace(",", "").split(".")[0])
    except Exception:
        return "-"
    if n <= 0:
        return "-"
    return f"{n:,}원"


def katec_to_wgs84(x, y):
    """경매 좌표(stXcrd/stYcrd, KATEC/TM128, GRS80) → WGS84(위도, 경도)."""
    a = 6378137.0
    f = 1.0 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9999
    lat0 = math.radians(38.0)
    lon0 = math.radians(128.0)
    x0, y0 = 400000.0, 600000.0
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    def M(lat):
        return a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat
                    - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat)
                    + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat)
                    - (35 * e2**3 / 3072) * math.sin(6 * lat))

    Mv = M(lat0) + (y - y0) / k0
    mu = Mv / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
            + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
            + (151 * e1**3 / 96) * math.sin(6 * mu)
            + (1097 * e1**4 / 512) * math.sin(8 * mu))
    C1 = ep2 * math.cos(phi1)**2
    T1 = math.tan(phi1)**2
    N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
    D = (x - x0) / (N1 * k0)
    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * ep2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 252 * ep2 - 3 * C1**2) * D**6 / 720)
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D**3 / 6
                  + (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * ep2 + 24 * T1**2) * D**5 / 120) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


def obj_latlng(db):
    """gdsDspslObjctLst의 stXcrd/stYcrd → (lat, lng). 없거나 범위 밖이면 None."""
    for o in (db.get("gdsDspslObjctLst") or []):
        if not isinstance(o, dict):
            continue
        try:
            x, y = float(o.get("stXcrd")), float(o.get("stYcrd"))
        except Exception:
            continue
        if not (x and y):
            continue
        lat, lng = katec_to_wgs84(x, y)
        if 33.0 < lat < 39.5 and 124.0 < lng < 132.0:
            return lat, lng
    return None



def _fv(k, v):
    if v in (None, ""):
        return "-"
    s = str(v)
    if k in ("ultmtDvsCd", "ultmtCd") or k.endswith("UltmtDvsCd"):
        return ULTMT_DVS.get(s, s)
    if "DxdyKndCd" in k or k == "dxdyKndCd" or k == "auctnDxdyKndCd":
        return DXDY_KND.get(s, s)
    if k.endswith("Ymd") and s.isdigit() and len(s) == 8:
        return _d(s)
    if k.endswith("Hm") and s.isdigit() and len(s) >= 3:
        s = s.zfill(4)
        return f"{s[:2]}:{s[2:]}"
    if (k.endswith("Amt") or k.endswith("Prc")) and s.replace(",", "").isdigit():
        return fmt_krw(s.replace(",", ""))
    if k.endswith("Yn"):
        return {"Y": "유", "N": "무"}.get(s, s)
    return s


def to_long_csno(cs_a):
    """'2023타경3842' -> '20230130003842'"""
    m = re.match(r"\s*(\d{4})\s*타경\s*(\d+)", str(cs_a))
    if m:
        return m.group(1) + "0130" + m.group(2).zfill(6)
    digits = re.sub(r"\D", "", str(cs_a))
    return digits if len(digits) >= 12 else ""


def _tbl(items, skip=None, keep_long=False):
    items = [i for i in (items or []) if isinstance(i, dict)]
    if not items:
        return ""
    sk = (skip or set()) | SKIP | DROP_COLS
    if not keep_long:
        sk = sk | LONG_TEXT_COLS
    cols, seen = [], set()
    for item in items:
        for k in item:
            if k in seen or k in sk:
                continue
            if k.endswith(("Cd", "Seq", "Id")) and k not in KOR:
                continue
            if any(i.get(k) not in (None, "") for i in items):
                cols.append(k)
                seen.add(k)
    # 전체주소가 있으면 시도/시군구/읍면동 구성요소 컬럼 제거
    if any(c in FULL_ADDR for c in cols):
        cols = [c for c in cols if c not in ADDR_PARTS]
    if not cols:
        return ""
    hdrs = "".join(f"<th>{KOR.get(c, c)}</th>" for c in cols)
    rows = ""
    for item in items:
        cells = ""
        for c in cols:
            rv = item.get(c, "")
            val = _fv(c, rv)
            if isinstance(rv, str) and "\n" in rv:
                val = rv.replace("\n", "<br>")
            cells += f"<td>{val}</td>"
        rows += f"<tr>{cells}</tr>"
    return f"<table class='dt-table'><thead><tr>{hdrs}</tr></thead><tbody>{rows}</tbody></table>"


def _kv(d, skip=None):
    sk = (skip or set()) | SKIP | DROP_COLS | LONG_TEXT_COLS
    rows = ""
    for k, v in d.items():
        if k in sk or v in (None, "", [], {}):
            continue
        if k.endswith(("Cd", "Seq", "Id")) and k not in KOR:
            continue
        rows += f"<tr><th>{KOR.get(k, k)}</th><td>{_fv(k, v)}</td></tr>"
    return f"<table class='kv'>{rows}</table>" if rows else ""


def _find_list(d, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    for v in d.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def find_list_by(src, *substrs):
    """src(dict)에서 키에 substr이 포함된 첫 list[dict] 반환."""
    if not isinstance(src, dict):
        return []
    for k, v in src.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            if any(s.lower() in k.lower() for s in substrs):
                return v
    return []


def collect_desc(sources, content_keys, default_label, min_len=8):
    """지정한 content_keys 값만 모아 [(라벨, 내용)] 반환. 내용 중복 제거.
    감정평가(aeeWevlMnpntCtt)와 현황·점유(gdsPossCtt)를 분리 수집하기 위함."""
    out, seen = [], set()
    label_keys = ["aeeWevlMnpntDvsNm", "aeeWevlMnpntNm", "dspslObjctSeq", "rprsLtnoAddr",
                  "rletStLtnoAddr", "ldcgNm"]
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key, val in src.items():
            if not (isinstance(val, list) and val and isinstance(val[0], dict)):
                continue
            for item in val:
                if not isinstance(item, dict):
                    continue
                ctt = ""
                for ck in content_keys:
                    v = item.get(ck)
                    if v and len(str(v).strip()) > min_len:
                        ctt = str(v).strip()
                        break
                if not ctt:
                    continue
                norm = re.sub(r"\s+", "", ctt)
                if norm in seen:
                    continue
                seen.add(norm)
                lab = ""
                for lk in label_keys:
                    v = item.get(lk)
                    if v:
                        sv = str(v)
                        lab = f"목록 {sv}" if lk == "dspslObjctSeq" else (
                            f"지번 {sv}" if lk in ("rprsLtnoAddr", "rletStLtnoAddr") else sv)
                        break
                out.append((lab or default_label, ctt))
    return out


def _desc_html(items):
    return "".join(
        f'<div class="erow"><div class="ek">{lab}</div>'
        f'<div class="ev">{ctt.replace(chr(10), "<br>")}</div></div>'
        for lab, ctt in items)


def render_aee(db, da):
    """감정평가요항(aeeWevlMnpntLst)을 요항표 종류(토지/건물 등)별로 구분해 렌더."""
    lst = (db.get("aeeWevlMnpntLst") or da.get("aeeWevlMnpntLst")
           or find_list_by(db, "aeeWevlMnpnt") or find_list_by(da, "aeeWevlMnpnt") or [])
    groups, order = {}, []
    for it in lst:
        if not isinstance(it, dict):
            continue
        ctt = str(it.get("aeeWevlMnpntCtt") or "").strip()
        if not ctt:
            continue
        tblt = str(it.get("aeeWevlMnpntTbltDvsCd") or "")
        itm = str(it.get("aeeWevlMnpntItmCd") or "")
        lab = (AEE_ITM.get(itm) or it.get("aeeWevlMnpntDvsNm")
               or it.get("aeeWevlMnpntNm") or "기타")
        ctt = ctt.replace('""', '"').replace("\r\n", "\n").replace("\r", "\n")
        try:
            seq = int(it.get("aeeWevlMnpntDtlSeq") or 0)
        except Exception:
            seq = 0
        if tblt not in groups:
            groups[tblt] = []
            order.append(tblt)
        groups[tblt].append((seq, lab, ctt))
    if not groups:
        return ""
    html = []
    show_hdr = len(groups) > 1 or any(t in AEE_TBLT for t in groups)
    for tblt in order:
        rows = sorted(groups[tblt], key=lambda x: x[0])
        if show_hdr:
            html.append("<div style='font-weight:700;margin:12px 0 4px;color:#1d3a72'>"
                        f"{AEE_TBLT.get(tblt, '감정평가요항')}</div>")
        html.append(_desc_html([(lab, ctt) for _, lab, ctt in rows]))
    return "".join(html)


# ── 목록내역(부동산의 표시) 전용 ──────────────────────────────────────────────
LST_SEQ_KEYS = ("dspslObjctSeq", "bldSdtrSeq", "objctSeq", "dspslGdsLstSeq", "mokmulSer")
LST_GBN_KEYS = ("rletDvsDts", "auctnLstNm", "objctDvsNm", "lstDvsNm", "gdsKndNm",
                "rletKndNm", "objctKndNm", "auctnObjctTypNm")
LST_GBN_VALUES = ("집합건물", "구분건물", "토지및건물", "토지·건물", "토지와 건물", "토지와건물",
                  "제시외건물", "미등기건물", "건물", "토지", "차량", "선박", "기타")
# 부동산 표시 본문 식별용 섹션 키워드
SECTION_MARKERS = ("동의 건물의 표시", "전유부분", "대지권", "토지의 표시", "건물의 표시", "매각지분")


def _pre(s):
    """줄바꿈/들여쓰기 보존(HTML 단일 라인화) — md() 평탄화에도 형식 유지."""
    out = []
    for ln in str(s).split("\n"):
        stripped = ln.lstrip(" ")
        lead = "&nbsp;" * (len(ln) - len(stripped))
        stripped = re.sub(r" {2,}", lambda m: "&nbsp;" * len(m.group()), stripped)
        out.append(lead + stripped)
    return "<br>".join(out)


def _looks_encoded(s):
    """한글·공백·줄바꿈이 없고 base64/토큰 문자만으로 된 긴 문자열 → 인코딩값으로 간주."""
    s = s.strip()
    if len(s) < 16:
        return False
    if re.search(r"[가-힣\s]", s):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=._\-]+", s))


def _obj_detail_text(item):
    """부동산 표시 본문 추출. 한글이 포함된 텍스트만 본문으로 인정(토큰/코드 제외).
    섹션 키워드 포함 본문 우선, 없으면 최장 한글 텍스트, 그것도 없으면 라벨:값 폴백."""
    HANGUL = re.compile(r"[가-힣]")
    texts = []
    for k, v in item.items():
        if not isinstance(v, str) or k in SKIP or k in DROP_COLS:
            continue
        s = v.strip()
        if len(s) >= 10 and HANGUL.search(s) and not _looks_encoded(s):
            texts.append(s)
    best = ""
    for s in texts:
        if any(m in s for m in SECTION_MARKERS) and len(s) > len(best):
            best = s
    if not best:
        for s in texts:
            if len(s) > len(best):
                best = s
    mj = str(item.get("maejibun") or item.get("mmaeJibun") or "").strip()
    # 본문이 전혀 없으면 구조화 필드를 라벨:값으로 폴백
    if not best:
        lines = []
        for k, v in item.items():
            if not isinstance(v, str) or k in (SKIP | DROP_COLS | set(LST_GBN_KEYS) | set(LST_SEQ_KEYS)):
                continue
            s = v.strip()
            if not s or _looks_encoded(s):
                continue
            if not HANGUL.search(s) and not re.search(r"\d", s):
                continue
            if k in KOR:
                lines.append(f"{KOR[k]} : {s}")
        best = "\n".join(lines)
    if mj and re.sub(r"\s+", "", mj) not in re.sub(r"\s+", "", best):
        best = (best + "\n\n매각지분 : " + mj) if best else ("매각지분 : " + mj)
    return best


# 용도 분류(DSPSL_GDS_LST_USG_CD) — 대(끝0000)/중(끝00)/소
DSPSL_USG = {"10101": "전", "10102": "답", "10103": "과수원", "10104": "목장용지", "10105": "임야", "10106": "광천지", "10107": "염전", "10108": "대지", "10109": "공장용지", "10110": "학교용지", "10111": "주차장", "10112": "주유소용지", "10113": "창고용지", "10114": "도로", "10115": "철도용지", "10116": "제방", "10117": "하천", "10118": "구거", "10119": "유지", "10120": "양어장", "10121": "수도용지", "10122": "공원", "10123": "체육용지", "10124": "유원지", "10125": "종교용지", "10126": "사적지", "10127": "묘지", "10128": "잡종지", "10199": "대지,임야,전답", "20101": "단독주택", "20102": "다가구주택", "20103": "다중주택", "20104": "아파트", "20105": "연립주택", "20106": "다세대주택", "20107": "기숙사", "20108": "빌라", "20109": "상가주택", "20110": "오피스텔", "20111": "주상복합", "20198": "단독주택,다가구주택", "20199": "연립주택,다세대,빌라", "21101": "근린생활시설", "21102": "문화및집회시설", "21103": "종교시설", "21104": "판매시설", "21105": "운수시설", "21106": "의료시설", "21107": "교육연구시설", "21108": "노유자시설", "21109": "수련시설", "21110": "운동시설", "21111": "업무시설", "21112": "숙박시설", "21113": "위락시설", "21114": "교정및군사시설", "21115": "방송통신시설", "21116": "발전시설", "21117": "묘지관련시설", "21118": "관광휴게시설", "21199": "상가,오피스텔,근린시설", "22101": "공장", "22102": "창고시설", "22103": "위험물저장및처리시설", "22104": "자동차관련시설", "22105": "동물및식물관련시설", "22106": "분뇨및쓰레기처리시설", "23101": "주/상용건물", "23102": "주/산용건물", "23103": "기타복합용건물", "30101": "승용차", "30102": "승합차", "30103": "버스", "30104": "화물차", "30105": "기타차량", "30199": "자동차,중기_차량", "31101": "덤프트럭", "31102": "굴삭기", "31103": "지게차", "31104": "기타중기", "32101": "선박", "33101": "항공기", "34101": "이륜차", "40101": "어업권", "40102": "광업권", "40103": "농업권", "40201": "기타", "10000": "토지", "10100": "지목", "20000": "건물", "20100": "주거용건물", "21100": "상업용및업무용", "22100": "산업용및기타특수용", "23100": "용도복합용", "30000": "차량및운송장비", "30100": "차량", "31100": "중기", "31199": "자동차,중기_중기", "32100": "선박_중분류", "33100": "항공기_중분류", "34100": "이륜차_중분류", "40000": "기타_대분류", "40100": "권리", "40200": "기타_중분류"}
# 등기권리(AUCTN_RGLT_KND_CD)
RGLT_KND = {"12400": "1동건물", "12401": "소유권", "12402": "전세권", "12403": "임차권", "12404": "지상권"}
# 사진유형(CORT_AUCTN_PIC_DVS_CD)
PIC_DVS = {"000241": "전경도", "000242": "지번약도", "000243": "내부구조도", "000244": "위치도", "000245": "관련사진", "000246": "지적도", "000247": "개황도", "000249": "동산물품사진"}
# 관계인 구분(AUCTN_INTRPS_DVS_CD)
INTRPS_DVS = {"0001505": "신청인", "0001507": "감정인", "0001515": "승계인", "000151E": "이해관계인", "0001527": "채권자", "0001528": "채무자", "0001535": "제3취득자", "0001536": "상대방", "0001550": "근저당권부질권자", "0001551": "수계인", "0001556": "지역권자", "0001557": "소유자", "0001558": "채무자겸소유자", "000155A": "저당권부질권자", "000155D": "상대방겸소유자", "000155E": "신청인겸소유자", "000155F": "상대방겸소유자대리인", "000155G": "신청인겸소유자대리인", "0001560": "최고가매수신고인", "0001561": "차순위매수신고인", "0001562": "임차인", "0001563": "근저당권자", "0001564": "가압류권자", "0001565": "저당권자", "0001566": "전세권자", "0001567": "압류권자", "0001568": "공유자", "0001569": "가등기권자", "0001570": "임금채권자", "0001571": "교부권자", "0001572": "지상권자", "0001573": "가처분권자", "0001574": "배당요구권자", "0001575": "점유자", "000157A": "유치권자", "0001580": "주택임차권자", "0001581": "임차권자", "0001589": "집행관", "0001590": "최고가매수인", "0001591": "차순위매수인", "0001592": "소유자대리인", "0001593": "채무자겸소유자대리인", "0001594": "임차인대리인", "0001595": "임금채권자대리인", "0001596": "배당요구권자대리인", "0001599": "기타", "00015C10": "채권자_집행관", "00015C11": "채권자_내국인", "00015C12": "채권자_외국인", "00015C13": "채권자_법인", "00015C14": "채권자_검사", "00015C20": "대리인", "00015C21": "대리인_내국인", "00015C22": "대리인_외국인", "00015C23": "대리인_법인", "00015D10": "채무자_집행관", "00015D11": "채무자_내국인", "00015D12": "채무자_외국인", "00015D13": "채무자_법인", "00015D20": "제3채무자", "00015D21": "제3채무자_내국인", "00015D22": "제3채무자_외국인", "00015D23": "제3채무자_법인", "00015P10": "채무자의 배우자", "00015P11": "채무자의 배우자_내국인", "00015P12": "채무자의 배우자_외국인", "00015P13": "채무자의 배우자_법인", "00015P20": "배당요구자(교부청구등)", "00015P21": "배당요구자(교부청구등)_내국인", "00015P22": "배당요구자(교부청구등)_외국인", "00015P23": "배당요구자(교부청구등)_법인", "00015P30": "집행의 제3자", "00015P31": "집행의 제3자_내국인", "00015P32": "집행의 제3자_외국인", "00015P33": "집행의 제3자_법인", "00015P40": "매수신고인(경락인)", "00015P41": "매수신고인(경락인)_내국인", "00015P42": "매수신고인(경락인)_외국인", "00015P43": "매수신고인(경락인)_법인", "00015P50": "가압류채권자", "00015P51": "가압류채권자_내국인", "00015P52": "가압류채권자_외국인", "00015P53": "가압류채권자_법인", "00015P60": "가처분채권자", "00015P61": "가처분채권자_내국인", "00015P62": "가처분채권자_외국인", "00015P63": "가처분채권자_법인", "00015P70": "감정촉탁인", "00015P71": "감정촉탁인_내국인", "00015P72": "감정촉탁인_외국인", "00015P73": "감정촉탁인_법인", "00015P80": "기타접수자", "00015P81": "기타접수자_내국인", "00015P82": "기타접수자_외국인", "00015P83": "기타접수자_법인"}


def _dicts_deep(x):
    """list/중첩list 안의 dict만 평탄하게 수집."""
    out = []

    def w(o):
        if isinstance(o, list):
            for e in o:
                w(e)
        elif isinstance(o, dict):
            out.append(o)
    w(x)
    return out


def _bld_disp(db, da):
    """법원 사이트의 '부동산의 표시'를 구조화 필드로 재구성.
    반환: [(목록번호, 목록구분, 상세내역텍스트), ...]"""
    objs = _dicts_deep(db.get("gdsDspslObjctLst") or da.get("dlt_dspslGdsDspslObjctLst")
                       or da.get("dlt_rletCsDspslObjctLst") or [])
    blds = _dicts_deep(db.get("bldSdtrDtlLstAll") or [])
    lands = _dicts_deep(db.get("rgltLandLstAll") or [])
    ltnos = _dicts_deep(db.get("gdsRletStLtnoLstAll") or [])
    if not (objs or blds or lands):
        return []

    def seq_of(r):
        try:
            return int(r.get("dspslObjctSeq") or 1)
        except Exception:
            return 1
    seqs = sorted({seq_of(r) for r in (objs + blds + lands + ltnos)}) or [1]

    result = []
    for sq in seqs:
        o0 = next((o for o in objs if seq_of(o) == sq), {})
        bld_lst = [b for b in blds if seq_of(b) == sq]
        land_lst = [L for L in lands if seq_of(L) == sq]
        ltno_lst = [t for t in ltnos if seq_of(t) == sq]
        whole = [b for b in bld_lst if str(b.get("rletDvsDts") or "") != "전유"]
        jeonyu = [b for b in bld_lst if str(b.get("rletDvsDts") or "") == "전유"]

        lines = []
        # 1동의 건물의 표시
        if whole:
            lines.append("1동의 건물의 표시")
            la = ltno_lst[0] if ltno_lst else o0
            adr = " ".join(str(x) for x in [
                la.get("adongSdNm"), la.get("adongSggNm"), la.get("adongEmdNm"),
                la.get("adongRiNm"), la.get("rletStLtnoAddr") or o0.get("rprsLtnoAddr")] if x)
            if adr:
                lines.append("   " + adr)
            if o0.get("bldNm"):
                lines.append("   " + str(o0["bldNm"]))
            for b in whole:
                for ln in str(b.get("bldSdtrDtlDts") or "").split("\n"):
                    if ln.strip():
                        lines.append("   " + ln.strip())
        # 전유부분의 건물의 표시
        bno = str(o0.get("bldDtlDts") or "").strip()
        jstruct = str((jeonyu[0].get("bldSdtrDtlDts") if jeonyu else "")
                      or o0.get("pjbBuldList") or "").strip()
        if bno or jstruct:
            if lines:
                lines.append("")
            lines.append("전유부분의 건물의 표시")
            if bno:
                lines.append(f"   건물의 번호 : {bno}")
            if jstruct:
                lines.append(f"   구        조 : {jstruct}")
        # 대지권의 목적인 토지의 표시
        if land_lst:
            if lines:
                lines.append("")
            lines.append("대지권의 목적인 토지의 표시")
            for L in land_lst:
                no = L.get("rgltLandNo") or 1
                ind = str(L.get("rletIndctDts") or "").strip()
                lines.append(f"   토 지 의  표시 : {no}. {ind}".rstrip())
                ldcg = str(L.get("landLdcgDts") or "").strip()
                ar = str(L.get("landArDts") or "").strip()
                if ldcg or ar:
                    lines.append(f"                       {ldcg} {ar}".rstrip())
            knds, rates = [], []
            for L in land_lst:
                no = L.get("rgltLandNo") or 1
                knds.append(f"{no}. {RGLT_KND.get(str(L.get('auctnRgltKndCd') or ''), '소유권')}")
                dn, nm = L.get("rgltRateDnmnVal"), L.get("rgltRateNmrtVal")
                if dn and nm:
                    rates.append(f"{no}. {dn} 분의 {nm}")
            if knds:
                lines.append("   대지권의 종류 : " + ", ".join(knds))
            if rates:
                lines.append("   대지권의 비율 : " + ", ".join(rates))
        # 토지/단일물건 표시 (1동건물·전유·대지권 어느 것도 없을 때)
        if not (whole or bno or jstruct or land_lst):
            la = ltno_lst[0] if ltno_lst else o0
            adr = " ".join(str(x) for x in [
                la.get("adongSdNm"), la.get("adongSggNm"), la.get("adongEmdNm"),
                la.get("adongRiNm"),
                la.get("rletStLtnoAddr") or o0.get("rprsLtnoAddr")] if x) \
                or str(o0.get("userPrintSt") or o0.get("printSt") or "").strip()
            ldcg = str(o0.get("ldcgDts") or o0.get("ldcgNm") or "").strip()
            ar = str(o0.get("objctArDts") or o0.get("arDts")
                     or o0.get("objctAr") or "").strip()
            struct2 = str(o0.get("pjbBuldList") or o0.get("bldDtlDts") or "").strip()
            if ldcg or ar:
                lines.append("토지의 표시")
                if adr:
                    lines.append("   " + adr)
                body = " ".join(x for x in [ldcg, ar] if x)
                if body:
                    lines.append("   " + body)
            elif struct2:
                lines.append("건물의 표시")
                if adr:
                    lines.append("   " + adr)
                lines.append("   " + struct2)
            elif adr:
                lines.append(adr)
        # 매각지분
        stk = str(o0.get("dspslStkCtt") or "").strip()
        if stk:
            if lines:
                lines.append("")
            lines.append("매각지분 : " + stk)

        if jeonyu or land_lst:
            gbn = "집합건물"
        elif whole:
            gbn = "건물"
        elif o0.get("ldcgDts") or o0.get("ldcgNm") or o0.get("objctArDts"):
            gbn = "토지"
        else:
            gbn = str(o0.get("rletDvsDts") or "")
        detail = "\n".join(lines).strip()
        if detail:
            result.append((sq, gbn, detail))
    return result


def render_object_list(db, da, dcurst):
    """목록번호 / 목록구분 / 상세내역(부동산 표시 본문) 3컬럼 표."""
    disp = _bld_disp(db, da)
    if disp:
        rows = ""
        for seq, gbn, detail in disp:
            rows += (f"<tr>"
                     f"<td style='text-align:center;white-space:nowrap;vertical-align:top'>{seq}</td>"
                     f"<td style='text-align:center;white-space:nowrap;vertical-align:top'>{gbn or '-'}</td>"
                     f"<td style='text-align:left;vertical-align:top'>{_pre(detail)}</td>"
                     f"</tr>")
        return ("<table class='dt-table'><thead><tr>"
                "<th>목록번호</th><th>목록구분</th><th>상세내역</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>")
    return _render_object_list_fallback(db, da, dcurst)


def _render_object_list_fallback(db, da, dcurst):
    """구조화 필드가 없을 때 기존 방식으로 폴백."""
    lst = (da.get("dlt_dspslGdsDspslObjctLst")
           or da.get("dlt_rletCsDspslObjctLst")
           or db.get("gdsDspslObjctLst")
           or db.get("bldSdtrDtlLstAll")
           or find_list_by(dcurst, "DspslObjct", "ordTsRlet")
           or [])
    lst = [i for i in lst if isinstance(i, dict)]
    if not lst:
        return "<div class='nodata'>데이터 없음</div>"
    rows = ""
    for idx, item in enumerate(lst, 1):
        seq = next((str(item[k]) for k in LST_SEQ_KEYS if item.get(k) not in (None, "")), str(idx))
        gbn = next((str(item[k]) for k in LST_GBN_KEYS if item.get(k) not in (None, "")), "")
        if not gbn:
            for v in item.values():
                if isinstance(v, str) and v.strip() in LST_GBN_VALUES:
                    gbn = v.strip()
                    break
        # 상세내역: 소재지 + 구조/면적 + 건물상세 + 매각지분 조합(있는 필드만)
        parts = []
        addr = str(item.get("userPrintSt") or item.get("printSt")
                   or item.get("userSt") or "").strip()
        if addr:
            parts.append(addr)
        struct = str(item.get("pjbBuldList") or item.get("objctArDts") or "").strip()
        bdtl = str(item.get("bldDtlDts") or "").strip()
        if struct:
            parts.append(struct + (f"  {bdtl}" if bdtl and bdtl not in struct else ""))
        elif bdtl:
            parts.append(bdtl)
        ldcg = str(item.get("ldcgDts") or item.get("ldcgNm") or "").strip()
        if ldcg:
            parts.append(f"지목: {ldcg}")
        stk = str(item.get("dspslStkCtt") or "").strip()
        if stk:
            parts.append("[매각지분]\n" + stk)
        detail = "\n".join(parts).strip() or _obj_detail_text(item)
        if not gbn:  # 본문 첫머리로 구분 추정
            head = detail[:60]
            if "동의 건물의 표시" in head or "전유부분" in head:
                gbn = "집합건물"
            elif "토지의 표시" in head and "건물" not in head:
                gbn = "토지"
            else:
                gbn = next((g for g in LST_GBN_VALUES if g in head), "")
        rows += (f"<tr>"
                 f"<td style='text-align:center;white-space:nowrap;vertical-align:top'>{seq}</td>"
                 f"<td style='text-align:center;white-space:nowrap;vertical-align:top'>{gbn or '-'}</td>"
                 f"<td style='text-align:left;vertical-align:top'>{_pre(detail) or '-'}</td>"
                 f"</tr>")
    return ("<table class='dt-table'><thead><tr>"
            "<th>목록번호</th><th>목록구분</th><th>상세내역</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def list_keys_dump(*sources):
    """디버그용: 각 응답의 list/str 키 목록."""
    lines = []
    names = ["pgj15B", "pgj15A", "기일상세", "문건송달", "현황조사"]
    for nm, src in zip(names, sources):
        if not isinstance(src, dict) or not src:
            continue
        ks = []
        for k, v in src.items():
            if isinstance(v, list) and v:
                ks.append(f"{k}[{len(v)}]")
            elif isinstance(v, dict) and v:
                ks.append(f"{k}{{}}")
            elif isinstance(v, str) and v.strip():
                ks.append(k)
        if ks:
            lines.append(f"• {nm}: " + ", ".join(ks))
    return "<br>".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  참조 데이터 API
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def get_court_list():
    raw = _post(f"{BASE}/pgj/pgj002/selectCortOfcLst.on", {"cortExecrOfcDvsCd": "00079B"})
    d = _nm_cd(_items(raw, "cortOfcLst", "dlt_cortOfcLst", "list"))
    return {"전체": ""} | d if d else {"전체": ""} | {nm: cd for nm, cd in COURTS_FB}


@st.cache_data(ttl=3600)
def get_sd():
    raw = _post(f"{BASE}/pgj/pgj002/selectAdongSdLst.on",
                {"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "A"})
    return {"전체": ""} | _nm_cd(_items(raw, "adongSdLst", "dlt_adongSdLst", "list"))


@st.cache_data(ttl=3600)
def get_sgg(sd_cd):
    if not sd_cd:
        return {"전체": ""}
    raw = _post(f"{BASE}/pgj/pgj002/selectAdongSggLst.on",
                {"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "A", "adongSdCd": sd_cd})
    return {"전체": ""} | _nm_cd(_items(raw, "adongSggLst", "dlt_adongSggLst", "list"))


@st.cache_data(ttl=3600)
def get_emd(sd_cd, sgg_cd):
    if not sd_cd or not sgg_cd:
        return {"전체": ""}
    raw = _post(f"{BASE}/pgj/pgj002/selectAdongEmdLst.on",
                {"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "B",
                 "adongSdCd": sd_cd, "adongSggCd": sgg_cd})
    return {"전체": ""} | _nm_cd(_items(raw, "adongEmdLst", "dlt_adongEmdLst", "list"))


# ══════════════════════════════════════════════════════════════════════════════
#  검색 / 상세 조회
# ══════════════════════════════════════════════════════════════════════════════
def search_page(page, p):
    # 작동 확인된 실제 요청과 동일: cortStDvs="2", pgmId="PGJ151F01", statNum=1
    cort_st, pgm, statnum = "2", "PGJ151F01", 1
    payload = {
        "dma_pageInfo": {"pageNo": page, "pageSize": 10, "bfPageNo": "", "startRowNo": "",
                         "totalCnt": "", "totalYn": "Y", "groupTotalCount": ""},
        "dma_srchGdsDtlSrchInfo": {
            "rletDspslSpcCondCd": p["spc_cond"], "bidDvsCd": p.get("bid_dvs") or "000331",
            "mvprpRletDvsCd": p["rlet_dvs"],                      # ★ 용도 필터
            "cortAuctnSrchCondCd": p["status"],
            "cortOfcCd": p["court_cd"], "cortStDvs": cort_st, "csNo": p["cs_no"], "pgmId": pgm,
            "statNum": statnum,                                  # ★ 지역검색 시 1
            "aeeEvlAmtMin": p["aee_min"], "aeeEvlAmtMax": p["aee_max"],
            "lwsDspslPrcMin": p["lws_min"], "lwsDspslPrcMax": p["lws_max"],
            "lwsDspslPrcRateMin": p["rate_min"], "lwsDspslPrcRateMax": p["rate_max"],
            "flbdNcntMin": p["flbd_min"], "flbdNcntMax": p["flbd_max"],
            "bidBgngYmd": p["bid_from"], "bidEndYmd": p["bid_to"],
            "objctArDtsMin": p["area_min"], "objctArDtsMax": p["area_max"],
            "rprsAdongSdCd": p["sd_cd"], "rprsAdongSggCd": p["sgg_cd"], "rprsAdongEmdCd": p["emd_cd"],
            "lclDspslGdsLstUsgCd": p.get("usg_lcl", ""),
            "mclDspslGdsLstUsgCd": p.get("usg_mcl", ""),
            "sclDspslGdsLstUsgCd": p.get("usg_scl", ""),
            "notifyLoc": "on",
            **{k: "" for k in ["mvprpDspslPlcAdongSdCd", "mvprpDspslPlcAdongSggCd",
                               "mvprpDspslPlcAdongEmdCd", "mvprpArtclKndCd", "mvprpArtclNm",
                               "mvprpAtchmPlcTypCd", "dspslDxdyYmd", "dspslPlcNm", "execrOfcDvsCd",
                               "fstDspslHm", "scndDspslHm", "thrdDspslHm", "fothDspslHm",
                               "gdsVendNm", "jdbnCd", "lafjOrderBy", "rdnmSdCd",
                               "rdnmSggCd", "rdnmNo", "sideDvsCd", "grbxTypCd",
                               "fuelKndCd", "carMdyrMax", "carMdyrMin", "carMdlNm", "cortAuctnMbrsId",
                               "rdDspslPlcAdongSdCd", "rdDspslPlcAdongSggCd", "rdDspslPlcAdongEmdCd"]}
        }
    }
    raw = _post(f"{BASE}/pgj/pgjsearch/searchControllerMain.on", payload, hdr=H_SEARCH)
    inner = raw.get("data") or {}
    return (inner.get("dlt_srchResult") or [],
            int((inner.get("dma_pageInfo") or {}).get("totalCnt") or 0))


@st.cache_data(ttl=600)
def fetch_db(cs_a, cort, seq, sd="", sgg="", emd="", ridx=0):
    si = {"cortOfcCd": cort, "cortStDvs": "1", "cortAuctnSrchCondCd": "0004601", "csNo": "",
          "pgmId": "PGJ151M01", "menuNm": "물건상세검색", "sideDvsCd": "2", "srchRowIndex": ridx,
          "rprsAdongSdCd": sd, "rprsAdongSggCd": sgg, "rprsAdongEmdCd": emd,
          "bidBgngYmd": "", "bidEndYmd": "",
          **{k: "" for k in ["rletDspslSpcCondCd", "bidDvsCd", "mvprpRletDvsCd", "dspslDxdyYmd",
                             "dspslPlcNm", "execrOfcDvsCd", "flbdNcntMax", "flbdNcntMin",
                             "fothDspslHm", "fstDspslHm", "scndDspslHm", "thrdDspslHm", "gdsVendNm",
                             "jdbnCd", "lafjOrderBy", "lwsDspslPrcMax", "lwsDspslPrcMin",
                             "lwsDspslPrcRateMax", "lwsDspslPrcRateMin", "mvprpArtclKndCd",
                             "mvprpArtclNm", "mvprpAtchmPlcTypCd", "mvprpDspslPlcAdongSdCd",
                             "mvprpDspslPlcAdongSggCd", "mvprpDspslPlcAdongEmdCd",
                             "rdDspslPlcAdongSdCd", "rdDspslPlcAdongSggCd", "rdDspslPlcAdongEmdCd",
                             "rdnmSdCd", "rdnmSggCd", "rdnmNo", "lclDspslGdsLstUsgCd",
                             "mclDspslGdsLstUsgCd", "sclDspslGdsLstUsgCd", "notifyLoc",
                             "objctArDtsMax", "objctArDtsMin", "statNum", "grbxTypCd", "fuelKndCd",
                             "carMdyrMax", "carMdyrMin", "carMdlNm", "cortAuctnMbrsId"]}}
    raw = _post(f"{BASE}/pgj/pgj15B/selectAuctnCsSrchRslt.on",
                {"dma_srchGdsDtlSrch": {"cortOfcCd": cort, "csNo": cs_a,
                                        "dspslGdsSeq": str(seq or 1), "pgmId": "PGJ151M01",
                                        "srchInfo": si}}, hdr=H_DETAIL)
    return _unwrap(raw)


@st.cache_data(ttl=600)
def fetch_da(cs_b, cort):
    raw = _post(f"{BASE}/pgj/pgj15A/selectAuctnCsSrchRslt.on",
                {"dma_srchCsDtlInf": {"cortOfcCd": cort, "csNo": cs_b}}, hdr=H_DETAIL)
    return _unwrap(raw)


@st.cache_data(ttl=600)
def fetch_dxdy(cs_b, cort):
    raw = _post(f"{BASE}/pgj/pgj15A/selectCsDtlDxdyDts.on",
                {"dma_srchDxdyDtsLst": {"cortOfcCd": cort, "csNo": cs_b}}, hdr=H_DETAIL)
    return _unwrap(raw)


@st.cache_data(ttl=600)
def fetch_dlvr(cs_b, cort):
    raw = _post(f"{BASE}/pgj/pgj15A/selectDlvrOfdocDtsDtl.on",
                {"dma_srchDlvrOfdocDts": {"cortOfcCd": cort, "csNo": cs_b, "srchFlag": "F"}},
                hdr=H_DETAIL)
    return _unwrap(raw)


@st.cache_data(ttl=600)
def fetch_curst(cs_b, cort):
    raw = _post(f"{BASE}/pgj/pgj15B/selectCurstExmndc.on",
                {"dma_srchCurstExmn": {"cortOfcCd": cort, "csNo": cs_b,
                                       "auctnInfOriginDvsCd": "2", "ordTsCnt": ""}}, hdr=H_DETAIL)
    return _unwrap(raw)


# ══════════════════════════════════════════════════════════════════════════════
#  검색 폼
# ══════════════════════════════════════════════════════════════════════════════
def label(col, text):
    col.markdown(f"<p class='flabel'>{text}</p>", unsafe_allow_html=True)


def render_form():
    md('<div class="panel">')

    # 지역 검색 방식
    l, c = st.columns([1.3, 8])
    label(l, "지역 검색")
    with c:
        mode = st.radio("region_mode", ["전국(법원 선택)", "주소(시도→시군구→읍면동)"],
                        horizontal=True, label_visibility="collapsed", key="mode")
    md("<div class='sep'></div>")

    sd_cd = sgg_cd = emd_cd = court_cd = ""
    if mode == "전국(법원 선택)":
        l, c = st.columns([1.3, 8])
        label(l, "법원")
        with c:
            court_map = get_court_list()
            court_nm = st.selectbox("court", list(court_map.keys()), label_visibility="collapsed", key="court_nm")
            court_cd = court_map.get(court_nm, "")
    else:
        l, c = st.columns([1.3, 8])
        label(l, "소재지")
        with c:
            c1, c2, c3 = st.columns(3)
            sd_map = get_sd()
            sd_nm = c1.selectbox("sd", list(sd_map.keys()), label_visibility="collapsed", key="sd_nm")
            sd_cd = sd_map.get(sd_nm, "")
            sgg_map = get_sgg(sd_cd)
            sgg_nm = c2.selectbox("sgg", list(sgg_map.keys()), label_visibility="collapsed", key="sgg_nm")
            sgg_cd = sgg_map.get(sgg_nm, "")
            emd_map = get_emd(sd_cd, sgg_cd)
            emd_nm = c3.selectbox("emd", list(emd_map.keys()), label_visibility="collapsed", key="emd_nm")
            emd_cd = emd_map.get(emd_nm, "")
    md("<div class='sep'></div>")

    # 용도(대/중/소 분류) + 진행상태
    l, c = st.columns([1.3, 8])
    label(l, "용도")
    with c:
        u1, u2, u3, u4 = st.columns([2, 2, 2, 3])
        dae_opts = {"전체": ""}
        dae_opts.update({n: cd for cd, n in dspsl_dae()})
        dae_nm = u1.selectbox("대분류", list(dae_opts.keys()),
                              label_visibility="collapsed", key="usg_dae")
        dae_cd = dae_opts[dae_nm]

        jung_opts = {"전체": ""}
        jung_opts.update({n: cd for cd, n in dspsl_jung(dae_cd)})
        if "usg_jung" in st.session_state and st.session_state["usg_jung"] not in jung_opts:
            del st.session_state["usg_jung"]
        jung_nm = u2.selectbox("중분류", list(jung_opts.keys()),
                               label_visibility="collapsed", key="usg_jung")
        jung_cd = jung_opts.get(jung_nm, "")

        so_opts = {"전체": ""}
        so_opts.update({n: cd for cd, n in dspsl_so(jung_cd)})
        if "usg_so" in st.session_state and st.session_state["usg_so"] not in so_opts:
            del st.session_state["usg_so"]
        so_nm = u3.selectbox("소분류", list(so_opts.keys()),
                             label_visibility="collapsed", key="usg_so")
        so_cd = so_opts.get(so_nm, "")

        with u4:
            status_nm = st.radio("status", list(STATUS_OPTS.keys()), horizontal=True,
                                 label_visibility="collapsed", key="status")
    md("<div class='sep'></div>")

    # 사건번호
    l, c = st.columns([1.3, 8])
    label(l, "사건번호")
    with c:
        c1, cm, c2 = st.columns([1.4, 0.5, 3])
        cs_yr = c1.selectbox("yr", YEARS, label_visibility="collapsed", key="cs_yr")
        cm.markdown("<p style='padding-top:8px;text-align:center;font-size:13px'>타경</p>", unsafe_allow_html=True)
        cs_num = c2.text_input("num", value="", label_visibility="collapsed",
                               placeholder="번호 입력(선택)", key="cs_num")
    cs_no = f"{cs_yr}타경{cs_num.strip()}" if cs_num.strip() else ""
    md("<div class='sep'></div>")

    # 감정평가액 / 최저매각가
    l, c = st.columns([1.3, 8])
    label(l, "감정평가액")
    with c:
        c1, m1, c2, lb, c3, c4 = st.columns([1.5, 0.25, 1.5, 1.4, 1.5, 1.5])
        aee_min_nm = c1.selectbox("amn", list(PRICE_OPTS.keys()), label_visibility="collapsed", key="aee_min")
        m1.markdown("<p style='padding-top:8px;text-align:center'>~</p>", unsafe_allow_html=True)
        aee_max_nm = c2.selectbox("amx", list(PRICE_OPTS.keys()), label_visibility="collapsed", key="aee_max")
        lb.markdown("<p class='flabel' style='text-align:right'>최저매각가</p>", unsafe_allow_html=True)
        lws_min_nm = c3.selectbox("lmn", list(PRICE_OPTS.keys()), label_visibility="collapsed", key="lws_min")
        lws_max_nm = c4.selectbox("lmx", list(PRICE_OPTS.keys()), label_visibility="collapsed", key="lws_max")
    md("<div class='sep'></div>")

    # 유찰횟수 / 최저매각가율
    l, c = st.columns([1.3, 8])
    label(l, "유찰횟수")
    with c:
        c1, m1, c2, lb, c3, c4 = st.columns([1.5, 0.25, 1.5, 1.4, 1.5, 1.5])
        flbd_min_nm = c1.selectbox("fmn", list(FLBD_OPTS.keys()), label_visibility="collapsed", key="flbd_min")
        m1.markdown("<p style='padding-top:8px;text-align:center'>~</p>", unsafe_allow_html=True)
        flbd_max_nm = c2.selectbox("fmx", list(FLBD_OPTS.keys()), label_visibility="collapsed", key="flbd_max")
        lb.markdown("<p class='flabel' style='text-align:right'>최저가율</p>", unsafe_allow_html=True)
        rate_min_nm = c3.selectbox("rmn", list(RATE_OPTS.keys()), label_visibility="collapsed", key="rate_min")
        rate_max_nm = c4.selectbox("rmx", list(RATE_OPTS.keys()), label_visibility="collapsed", key="rate_max")
    md("<div class='sep'></div>")

    # 면적
    l, c = st.columns([1.3, 8])
    label(l, "면적(㎡)")
    with c:
        c1, m1, c2, _ = st.columns([2, 0.3, 2, 3.7])
        area_min = c1.text_input("armn", value="", placeholder="최소", label_visibility="collapsed", key="area_min")
        m1.markdown("<p style='padding-top:8px;text-align:center'>~</p>", unsafe_allow_html=True)
        area_max = c2.text_input("armx", value="", placeholder="최대", label_visibility="collapsed", key="area_max")
    md("<div class='sep'></div>")

    # 매각기일 기간 (체크 시에만 적용)
    l, c = st.columns([1.3, 8])
    label(l, "매각기일")
    with c:
        c0, c1, m1, c2, _ = st.columns([1.6, 1.8, 0.3, 1.8, 2.5])
        use_date = c0.checkbox("기간지정", key="use_date")
        bid_from = c1.date_input("bf", value=date.today(), label_visibility="collapsed",
                                 key="bid_from", disabled=not use_date)
        m1.markdown("<p style='padding-top:8px;text-align:center'>~</p>", unsafe_allow_html=True)
        bid_to = c2.date_input("bt", value=date.today() + timedelta(weeks=4),
                               label_visibility="collapsed", key="bid_to", disabled=not use_date)
    md("<div class='sep'></div>")

    # 특이사항
    l, c = st.columns([1.3, 8])
    label(l, "특이사항")
    with c:
        checked = []
        for s in range(0, len(SPECIAL_CONDS), 5):
            chunk = SPECIAL_CONDS[s:s + 5]
            cols_ = st.columns(5)
            for i, (nm, cd) in enumerate(chunk):
                if cols_[i].checkbox(nm, key=f"spc_{cd}"):
                    checked.append(cd)
    md("<div class='sep'></div>")

    # 버튼
    _, b1, b2 = st.columns([6.2, 1.2, 1])
    search_btn = b1.button("🔍  검색", use_container_width=True, type="primary")
    reset_btn = b2.button("↺  초기화", use_container_width=True)
    md('</div>')

    if reset_btn:
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    params = {
        "court_cd": court_cd, "sd_cd": sd_cd, "sgg_cd": sgg_cd, "emd_cd": emd_cd,
        "cs_no": cs_no, "rlet_dvs": "", "status": STATUS_OPTS[status_nm],
        "usg_lcl": dae_cd, "usg_mcl": jung_cd, "usg_scl": so_cd,
        "bid_dvs": "", "bid_from": bid_from.strftime("%Y%m%d") if use_date else "",
        "bid_to": bid_to.strftime("%Y%m%d") if use_date else "",
        "aee_min": PRICE_OPTS[aee_min_nm], "aee_max": PRICE_OPTS[aee_max_nm],
        "lws_min": PRICE_OPTS[lws_min_nm], "lws_max": PRICE_OPTS[lws_max_nm],
        "rate_min": RATE_OPTS[rate_min_nm], "rate_max": RATE_OPTS[rate_max_nm],
        "flbd_min": FLBD_OPTS[flbd_min_nm], "flbd_max": FLBD_OPTS[flbd_max_nm],
        "area_min": area_min.strip(), "area_max": area_max.strip(),
        "spc_cond": ",".join(checked),
    }
    return params, search_btn


# ══════════════════════════════════════════════════════════════════════════════
#  결과 카드
# ══════════════════════════════════════════════════════════════════════════════
def _row_kind(row):
    return _p(row, "dspslUsgNm", "kindNm", "mvprpRletDvsNm", default="") \
        or DSPSL_USG.get(str(_p(row, "sclDspslGdsLstUsgCd", "mclDspslGdsLstUsgCd",
                                "lclDspslGdsLstUsgCd", default=""))) \
        or RLET_CD2NM.get(_p(row, "mvprpRletDvsCd", default=""), "")


def _row_addr(row):
    addr = _p(row, "printSt", "daepyoSt", "rprsAdongNm", "userSt", default="")
    seg = " ".join(s for s in [
        _p(row, "buldList", default=""), _p(row, "areaList", default=""),
        (f"({_p(row, 'jimokList', default='')})"
         if _p(row, "jimokList", default="") not in ("", "-") else ""),
    ] if s and s != "-").strip()
    parts = [t for t in seg.split() if t and t not in addr]
    return " ".join([addr] + parts).strip() or "소재지 정보 없음"


def _row_spc_badges(row):
    raw = _p(row, "rletDspslSpcCondCd", "dspslSpcCondCd", "spcCondCd", default="")
    nms = _p(row, "rletDspslSpcCondNm", "dspslSpcCondNm", default="")
    labels = []
    if raw and raw != "-":
        for c in re.split(r"[,\s]+", str(raw)):
            if c in SPC_CD2NM:
                labels.append(SPC_CD2NM[c])
    elif nms and nms != "-":
        labels = [x for x in re.split(r"[,/]+", str(nms)) if x.strip()]
    return "".join(f'<span class="bdg" style="background:#fee2e2;color:#b91c1c">{x}</span>'
                   for x in labels)


def render_card(group, idx, page):
    """한 물건(사건번호+물건번호) = 카드 1개. 목록 여러 개는 묶어서 표시."""
    rep = group[0]
    cs_no = _p(rep, "userCsNo", "srnSaNo", "csNo", "saNo")
    mul = _p(rep, "maemulSer", "dspslGdsSeq", default="")
    court = _p(rep, "jiwonNm", "boNm", "cortNm", "cortOfcNm", default="")
    dept = _p(rep, "jpDeptNm", default="")
    aee = rep.get("gamevalAmt") or rep.get("gamsungGa") or rep.get("aeeEvlAmt") or ""
    lws = rep.get("minmaePrice") or rep.get("choejeoChalga") or rep.get("lwsDspslPrc") or ""
    rate = (rep.get("notifyMinmaePriceRate1") or rep.get("lwsDspslPrcRate")
            or rep.get("lwsPrcRate") or "")
    bid_dt = _p(rep, "maeGiil", "maegakDate", "dxdyYmd", "bidBgngYmd", default="")
    bid_hh = _p(rep, "maeHh1", default="")
    flbd = _p(rep, "yuchalCnt", "yuchulCnt", "flbdNcnt", default="0")
    stat = _p(rep, "statNm", "procStatNm", "cortAuctnSrchCondNm", default="") \
        or ("진행중" if _p(rep, "mulJinYn", default="") == "Y" else "진행중")

    stat_cls = ("bdg-ok" if "진행" in stat else "bdg-sold" if "매각" in stat
                else "bdg-no" if any(x in stat for x in ("취하", "기각", "각하")) else "bdg-etc")
    mul_h = f'<span class="bdg bdg-etc">물건 {mul}</span>' if mul and mul != "-" else ""
    flbd_h = f'<span class="bdg bdg-flbd">유찰 {flbd}회</span>' if flbd and str(flbd) not in ("0", "") else '<span class="bdg" style="background-color: #e6f0fa; color: #0066cc;">신건</span>'
    rate_h = f'<span class="cprate">({rate}%)</span>' if rate and rate != "-" else ""
    court_txt = " ".join(t for t in [court, dept] if t and t != "-")
    court_h = f'<span class="ccourt">🏛 {court_txt}</span>' if court_txt else '<span class="ccourt"></span>'
    spc_h = _row_spc_badges(rep) or "".join(_row_spc_badges(r) for r in group[1:])

    # 목록별 소재지 라인
    addr_lines = ""
    for r in group:
        mok = _p(r, "mokmulSer", "dspslObjctSeq", default="")
        rk = _row_kind(r)
        tag = f'<span class="bdg bdg-type" style="margin-right:4px">{rk}</span>' if rk else ""
        lead = f"목록 {mok} · " if (len(group) > 1 and mok and mok != "-") else ""
        addr_lines += f'<div class="caddr">📍 {lead}{tag}{_row_addr(r)}</div>'
    bid_h = _d(bid_dt) + (f" {bid_hh[:2]}:{bid_hh[2:]}" if bid_hh.isdigit() and len(bid_hh) == 4 else "")

    md(f"""
    <div class="card">
      <div class="chead">
        <span class="cno">{cs_no}</span>{mul_h}{flbd_h}{spc_h}{court_h}
        <span class="bdg {stat_cls}">{stat}</span>
      </div>
      <div class="cbody">
        {addr_lines}
        <div class="cprices">
          <div class="cp"><div class="cplabel">감정평가액</div><div class="cpval">{fmt_krw(aee)}</div></div>
          <div class="cp"><div class="cplabel">최저매각가</div><div class="cpval red">{fmt_krw(lws)} {rate_h}</div></div>
          <div class="cp"><div class="cplabel">매각기일</div><div class="cpval" style="font-size:14px">{bid_h}</div></div>
        </div>
      </div>
    </div>
    """)
    _, bc = st.columns([4, 1])
    if bc.button("상세보기 ›", key=f"btn_{page}_{idx}", use_container_width=True, type="primary"):
        st.session_state["detail"] = rep
        st.session_state["detail_row_idx"] = (page - 1) * 10 + idx
        st.rerun()
    md("<div style='height:8px'></div>")


# ══════════════════════════════════════════════════════════════════════════════
#  상세 페이지
# ══════════════════════════════════════════════════════════════════════════════
POSS_RLTN = {"01": "채무자(소유자)점유", "02": "임차인(별지)점유",
             "03": "미상", "04": "임차인점유", "05": "기타", "09": "미상"}
AUCTN_LES_USG = {"00": "조사된 내용없음", "01": "주거", "02": "점포",
                 "03": "주거및점포", "04": "공장", "09": "기타"}


def _clean_br(s):
    """gdsPossCtt 등에 섞인 <br />·\\r·\\n을 단일 <br>로 정리."""
    s = str(s or "")
    for t in ("<br />", "<br/>", "<br>", "\r\n", "\r", "\n"):
        s = s.replace(t, "\n")
    lines = [ln.strip() for ln in s.split("\n")]
    return "<br>".join(ln for ln in lines if ln)


def _find_lease_rows(dcurst, da):
    """현황조사 임대차 상세 목록만 사용(이해관계인 목록과 혼동 금지)."""
    rows = (dcurst.get("dlt_ordTsLserLtn")
            or dcurst.get("dlt_ordTsCurstExmnLserLtn") or [])
    return [r for r in rows if isinstance(r, dict)]


def _lease_detail_html(rows):
    def g(it, *ks):
        for k in ks:
            if it.get(k) not in (None, ""):
                return str(it.get(k))
        return ""
    out = []
    for it in rows:
        usg = AUCTN_LES_USG.get(str(it.get("auctnLesUsgCd") or ""),
                                g(it, "lesUsgDts", "ocpnPrpsNm", "useDvsNm"))
        out.append(
            "<table class='kv'>"
            f"<tr><th>점유인</th><td>{g(it, 'intrpsNm', 'ocpnNm', 'rntrNm', 'lesPnm')}</td>"
            f"<th>당사자구분</th><td>임차인</td></tr>"
            f"<tr><th>점유부분</th><td>{g(it, 'lesPartCtt', 'ocpnPartCtt', 'rntrOccpnPartCtt')}</td>"
            f"<th>용도</th><td>{usg}</td></tr>"
            f"<tr><th>점유기간</th><td>{g(it, 'lesPdCtt', 'ocpnPdCtt')}</td><th></th><td></td></tr>"
            f"<tr><th>보증(전세)금</th><td>{g(it, 'lesDposDts', 'dpstAmt', 'rntrAmt')}</td>"
            f"<th>차임</th><td>{g(it, 'mmrntAmtDts', 'mrntAmt', 'rntrMnthlyAmt')}</td></tr>"
            f"<tr><th>전입일자</th><td>{g(it, 'mvinDtlCtt', 'mvinYmd', 'rntrMvInYmd')}</td>"
            f"<th>확정일자</th><td>{g(it, 'rgstryCrtcpCfmtnCtt', 'fdtnYmd', 'fxdtYmd')}</td></tr>"
            "</table>")
    return "".join(out)


def render_mnps(gds_dxdy):
    """매각물건명세서 요약 — 값 있는 항목만(토지 등 비면 숨김)."""
    if not gds_dxdy:
        return ""

    def ymd(s):
        s = str(s or "")
        return f"{s[:4]}.{s[4:6]}.{s[6:8]}" if (len(s) == 8 and s.isdigit()) else s
    rows = []
    if ymd(gds_dxdy.get("gdsSpcfcWrtYmd")):
        rows.append(("작성일", ymd(gds_dxdy.get("gdsSpcfcWrtYmd"))))
    fst = str(gds_dxdy.get("tprtyRnkHypthcStngDts") or "").strip()
    if fst:
        rows.append(("최선순위 설정", fst))
    if ymd(gds_dxdy.get("dstrtDemnLstprdYmd")):
        rows.append(("배당요구종기", ymd(gds_dxdy.get("dstrtDemnLstprdYmd"))))
    ndst = str(gds_dxdy.get("ndstrcRghCtt") or "").strip()
    rmk = str(gds_dxdy.get("dspslGdsRmk") or gds_dxdy.get("gdsSpcfcRmk") or "").strip()
    sprfc = str(gds_dxdy.get("sprfcExstcDts") or "").strip()
    if not (rows or ndst or rmk or sprfc):
        return ""
    h = ["<div class='sec'>매각물건명세서</div>"]
    if rows:
        h.append("<table class='kv'>"
                 + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
                 + "</table>")
    if ndst:
        h.append("<div style='font-weight:600;margin:8px 0 2px'>인수되는 권리 (매수인 인수사항)</div>"
                 f"<div class='drmk'>{_clean_br(ndst)}</div>")
    if rmk:
        h.append("<div style='font-weight:600;margin:8px 0 2px'>특별매각조건</div>"
                 f"<div class='drmk'>{_clean_br(rmk)}</div>")
    if sprfc:
        h.append("<div style='font-weight:600;margin:8px 0 2px'>지상권 개요</div>"
                 f"<div class='drmk'>{_clean_br(sprfc)}</div>")
    return "".join(h)


def render_curst(dcurst, da, base):
    """현황조사서 — 기본정보 / 부동산임대차정보 / 점유관계 / 임대차관계 / 기타."""
    if not dcurst:
        return "<div class='nodata'>현황조사 데이터 없음</div>"
    mng = (dcurst.get("dma_curstExmnMngInf")
           or dcurst.get("dma_ordTsCurstExmnMngInf") or {})
    rlet = [r for r in (dcurst.get("dlt_ordTsRlet")
                        or dcurst.get("dlt_ordTsCurstExmnRletLst") or [])
            if isinstance(r, dict)]
    h = []
    case_no = (f"{mng.get('userCsNo') or base.get('userCsNo', '')} "
               f"{base.get('csNm', '')}").strip()
    exmn = " ".join(x for x in re.split(r"[\^]+", str(mng.get("exmnDtDts") or "")) if x.strip())

    h.append("<div class='sec'>현황조사서 · 기본정보</div>")
    h.append("<table class='kv'>"
             f"<tr><th>사건번호</th><td>{case_no or '-'}</td></tr>"
             f"<tr><th>조사일시</th><td>{exmn or '-'}</td></tr></table>")

    if rlet:
        rows = ""
        for r in rlet:
            les = f"{r.get('lesCnt')}명" if r.get("lesCnt") is not None else "-"
            rows += (f"<tr><td style='text-align:center'>{r.get('objctSeq') or ''}</td>"
                     f"<td>{r.get('printSt') or ''}</td>"
                     f"<td style='text-align:center'>{les}</td></tr>")
        h.append("<div class='sec'>부동산임대차정보</div>"
                 "<table class='dt-table'><thead><tr><th>번호</th><th>소재지</th>"
                 "<th>임대차관계</th></tr></thead><tbody>" + rows + "</tbody></table>")

    h.append("<div class='sec'>부동산의 현황 및 점유관계 조사서</div>")
    for i, r in enumerate(rlet, 1):
        poss = POSS_RLTN.get(str(r.get("auctnPossRltnCd") or ""),
                             r.get("auctnPossRltnCd") or "-")
        h.append(f"<div style='font-weight:600;margin:8px 0 4px'>{i}. 부동산의 점유관계</div>"
                 "<table class='kv'>"
                 f"<tr><th>소재지</th><td>{i}. {r.get('printSt') or ''}</td></tr>"
                 f"<tr><th>점유관계</th><td>{poss}</td></tr>"
                 f"<tr><th>기타</th><td>{_clean_br(r.get('gdsPossCtt'))}</td></tr></table>")

    h.append("<div class='sec'>임대차관계 조사서</div>")
    leases = _find_lease_rows(dcurst, da)
    if leases:
        loc = rlet[0].get("printSt") if rlet else (leases[0].get("printSt") or "")
        if loc:
            h.append(f"<div style='margin:6px 0;font-weight:600'>[소재지] {loc}</div>")
        h.append(_lease_detail_html(leases))
    else:
        h.append("<div class='nodata'>조사된 임대차 상세내역이 없습니다.</div>")

    if mng.get("lesDts"):
        h.append("<div class='sec'>기타</div>"
                 f"<div class='drmk'>{_clean_br(mng['lesDts'])}</div>")
    return "".join(h)


def render_detail(db, da, ddxdy, ddlvr, dcurst):
    base = db.get("csBaseInfo") or da.get("dma_csBasInf") or {}
    gds_dxdy = db.get("dspslGdsDxdyInfo") or {}
    gds_lst = (db.get("gdsDspslObjctLst") or da.get("dlt_dspslGdsDspslObjctLst")
               or da.get("dlt_rletCsDspslObjctLst") or [])
    gds0 = gds_lst[0] if gds_lst else {}

    aee_evl = gds_dxdy.get("aeeEvlAmt") or gds0.get("aeeEvlAmt")
    lws_prc = (gds_dxdy.get("fstPbancLwsDspslPrc") or gds0.get("fstPbancLwsDspslPrc")
               or gds0.get("lwsDspslPrc"))
    try:
        prc_rate = int(gds_dxdy.get("prchDposRate") or gds0.get("prchDposRate") or 10)
    except Exception:
        prc_rate = 10
    deposit = int(str(lws_prc).replace(",", "")) * prc_rate // 100 if lws_prc else None
    dxdy_ymd = gds_dxdy.get("dspslDxdyYmd") or gds0.get("dspslDxdyYmd", "")
    dxdy_plc = gds_dxdy.get("dspslPlcNm", "")
    gds_rmk = str(gds_dxdy.get("dspslGdsRmk") or gds0.get("dspslGdsRmk") or "").replace("\n", "<br>")
    rlet_cd = base.get("mvprpRletDvsCd") or gds0.get("mvprpRletDvsCd", "")
    # 물건유형: DSPSL 용도코드(소→중→대) 우선, 없으면 기존 코드/명
    usg_cd = (gds0.get("sclDspslGdsLstUsgCd") or gds0.get("mclDspslGdsLstUsgCd")
              or gds0.get("lclDspslGdsLstUsgCd") or "")
    obj_kind = (DSPSL_USG.get(str(usg_cd))
                or gds0.get("mvprpRletDvsNm")
                or RLET_CD2NM.get(rlet_cd) or rlet_cd or "-")

    addrs, seen_a = [], set()
    for r in (db.get("gdsRletStLtnoLstAll") or []):
        if not isinstance(r, dict):
            continue
        parts = [r.get(k, "") for k in ("adongSdNm", "adongSggNm", "adongEmdNm", "adongRiNm") if r.get(k)]
        ltno = r.get("rletStLtnoAddr") or r.get("jibun", "")
        if ltno:
            parts.append(ltno)
        for k in ("buldNm", "apatNm", "gdsNm"):
            if r.get(k):
                parts.append(r[k])
                break
        a = " ".join(parts).strip()
        if a and a not in seen_a:
            addrs.append(a)
            seen_a.add(a)
    if not addrs:
        for item in gds_lst:
            if not isinstance(item, dict):
                continue
            v = str(item.get("userPrintSt") or item.get("userSt") or "").strip()
            if v and v not in seen_a:
                addrs.append(v)
                seen_a.add(v)
    addr_html = "<br>".join(addrs) or "-"

    dstrct = db.get("dstrtDemnInfo") or da.get("dlt_dstrtDemnLstprdDts") or []
    dstrct_ymd = next((d.get("dstrtDemnLstprdYmd", "") for d in dstrct
                       if isinstance(d, dict) and d.get("orddcsDvsCd") == "021"), "")
    dp_str = f"(보증금 {fmt_krw(deposit)})" if deposit else ""

    # 헤더
    md(f"""
    <div class="dhead">
      <div class="dcs">{base.get("userCsNo", "-")}</div>
      <div class="dsub">
        <span class="tag">{obj_kind}</span>🏛 {base.get("cortOfcNm", "-")} | {base.get("cortAuctnJdbnNm", "-")}
        &nbsp;{base.get("jdbnTelno", "")}
      </div>
      <div class="daddr">📍 {addr_html}</div>
      <div class="dgrid">
        <div class="dbox"><div class="dboxl">감정평가액</div><div class="dboxv">{fmt_krw(aee_evl)}</div></div>
        <div class="dbox"><div class="dboxl">최저매각가격 {dp_str}</div><div class="dboxv red">{fmt_krw(lws_prc)}</div></div>
        <div class="dbox"><div class="dboxl">매각기일</div><div class="dboxv" style="font-size:15px">{_d(dxdy_ymd)} {dxdy_plc}</div></div>
        <div class="dbox"><div class="dboxl">사건접수일</div><div class="dboxv" style="font-size:14px">{_d(base.get("csRcptYmd", ""))}</div></div>
        <div class="dbox"><div class="dboxl">청구금액</div><div class="dboxv" style="font-size:15px">{fmt_krw(base.get("clmAmt"))}</div></div>
        <div class="dbox"><div class="dboxl">배당요구종기</div><div class="dboxv" style="font-size:14px">{_d(dstrct_ymd)}</div></div>
      </div>
      {f'<div class="drmk">📌 {gds_rmk}</div>' if gds_rmk else ''}
    </div>
    """)

    tabs = st.tabs(["📷 물건/목록", "📋 감정평가요항", "📅 기일내역",
                    "👥 임차인·이해관계인", "📁 문건/송달"])

    # ── 탭1: 사진 + 목록내역 ──
    with tabs[0]:
        raw_pics = [p for p in (db.get("csPicLst") or []) if isinstance(p, dict)]

        def _img_bytes(p):
            """picFile(base64) 우선 디코드, 실패 시 URL 폴백용 (None 반환)."""
            b64 = p.get("picFile")
            if b64:
                try:
                    return base64.b64decode(b64)
                except Exception:
                    return None
            return None

        imgs = []
        for p in raw_pics:
            cap = PIC_DVS.get(str(p.get("cortAuctnPicDvsCd") or ""), "")
            data_bytes = _img_bytes(p)
            if data_bytes:
                imgs.append((data_bytes, cap))
            else:
                # 폴백: 디렉터리 경로 + 파일명으로 URL 구성
                u = (p.get("picFileUrl") or "")
                fn = p.get("picTitlNm") or ""
                if u:
                    url = (u if u.startswith("http") else BASE + u) + fn
                    try:
                        r = requests.get(url, headers=H_BASE, timeout=5)
                        if r.status_code == 200:
                            imgs.append((r.content, cap))
                    except Exception:
                        pass

        if imgs:
            md("<div class='sec'>물건 사진</div>")
            per_row = 4
            for s in range(0, len(imgs), per_row):
                chunk = imgs[s:s + per_row]
                cols = st.columns(len(chunk))
                for c, (content, cap) in zip(cols, chunk):
                    with c:
                        try:
                            st.image(content, use_container_width=True)
                            if cap:
                                st.caption(cap)
                        except Exception:
                            st.caption("이미지 표시 실패")
        # 목록내역: 부동산 표시 본문(목록번호·목록구분·상세내역)
        md("<div class='sec'>목록내역</div>")
        md(render_object_list(db, da, dcurst))

        # 위치 (stXcrd/stYcrd → WGS84)
        ll = obj_latlng(db)
        if ll:
            lat, lng = ll
            md("<div class='sec'>위치</div>")
            st.map(pd.DataFrame({"lat": [lat], "lon": [lng]}), zoom=15)
            st.caption(f"좌표(WGS84): {lat:.6f}, {lng:.6f}  ·  "
                       f"[카카오맵](https://map.kakao.com/link/map/{lat},{lng})  ·  "
                       f"[네이버지도](https://map.naver.com/v5/?lat={lat}&lng={lng}&z=16)")

    # ── 탭2: 감정평가요항 (aeeWevlMnpntLst) ──
    with tabs[1]:
        md("<div class='sec'>감정평가요항</div>")
        html = render_aee(db, da)
        if html:
            md(html)
        else:
            md("<div class='nodata'>감정평가요항 데이터 없음</div>")
            dump = list_keys_dump(db, da, ddxdy, ddlvr, dcurst)
            if dump:
                md(f"<div style='font-size:12px;color:#94a3b8;line-height:1.8;"
                   f"background:#f7f9fc;border:1px dashed #cdd6e0;border-radius:8px;padding:12px 16px'>"
                   f"<b style='color:#64748b'>응답 실제 키 (구축용)</b><br>{dump}</div>")

    # ── 탭3: 기일내역 ──
    with tabs[2]:
        detail = _find_list(ddxdy) if ddxdy else []
        if detail:
            md("<div class='sec'>기일내역 상세</div>")
            md(_tbl(detail))
        else:
            md("<div class='nodata'>기일내역 데이터 없음</div>")

    # ── 탭4: 현황조사서 (임대차/점유관계) + 이해관계인(맨 아래) ──
    with tabs[3]:
        mnps = render_mnps(gds_dxdy)
        if mnps:
            md(mnps)
        md(render_curst(dcurst, da, base))

        intrps = _find_list(da, "dlt_rletCsIntrpsLst")
        md("<div class='sec'>이해관계인</div>")
        md(_tbl(intrps) or "<div class='nodata'>이해관계인 정보 없음</div>")

    # ── 탭5: 문건/송달 (정크 테이블 제외) ──
    with tabs[4]:
        shown = False
        if ddlvr:
            for k, v in ddlvr.items():
                if k in DROP_TABLES:
                    continue
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    t = _tbl(v)
                    if t:
                        md(t)
                        shown = True
                elif isinstance(v, dict) and v:
                    kv = _kv(v)
                    if kv:
                        md(kv)
                        shown = True
        if not shown:
            md("<div class='nodata'>문건/송달 데이터 없음</div>")

    with st.expander("🔧 원본 JSON (구축용 — 배포 전 제거)"):
        st.json({"pgj15B": db, "pgj15A": da, "기일상세": ddxdy, "문건송달": ddlvr, "현황조사": dcurst})


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="경매정보 검색 시스템", page_icon="🏛️",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("<style>[data-testid='collapsedControl'],section[data-testid='stSidebar']{display:none}</style>",
                unsafe_allow_html=True)

    md("""
    <div class="top-bar">
      <div class="logo">🏛 경매정보 검색 시스템 <span>새로공인중개사사무소 · 최나림</span></div>
      <div class="tagline">경매 물건 검색 · 분석 · 서류 자동화</div>
    </div>
    """)

    # 상세
    if "detail" in st.session_state:
        bk_col, _ = st.columns([1, 7])
        if bk_col.button("← 목록으로", use_container_width=True):
            del st.session_state["detail"]
            st.rerun()

        row = st.session_state["detail"]
        cs_a = _p(row, "userCsNo", "srnSaNo")
        cort = _p(row, "boCd", "cortOfcCd", "cortCd")
        seq = _p(row, "maemulSer", "dspslGdsSeq", "mokmulSer")
        cs_b = to_long_csno(cs_a)
        if not cs_b:
            for fld in ("saNo", "csNo", "saCd"):
                v = str(row.get(fld, ""))
                if v.isdigit() and len(v) >= 12:
                    cs_b = v
                    break
        d_sd = row.get("daepyoSidoCd") or row.get("srchHjguSidoCd") or ""
        d_sgg = row.get("daepyoSiguCd") or ""
        ridx = st.session_state.get("detail_row_idx", 0)

        with st.spinner("물건 상세 정보를 불러오는 중..."):
            db = fetch_db(cs_a, cort, seq, d_sd, d_sgg, ridx=ridx)
            da = fetch_da(cs_b, cort)
            ddxdy = fetch_dxdy(cs_b, cort)
            ddlvr = fetch_dlvr(cs_b, cort)
            dcurst = fetch_curst(cs_b, cort)

        # 서류 버튼용 데이터 추출
        _cs_no = _p(row, "srnSaNo", "userCsNo", "csNo", default="")
        _court = _p(row, "jiwonNm", "cortOfcNm", default="")
        _mae_giil = _p(row, "maeGiil", "dspslDxdyYmd", default="")
        _min_price = _p(row, "minmaePrice", "lwsDspslPrc", default="")
        _appraisal = _p(row, "gamevalAmt", "aeeEvlAmt", default="")
        _mae_hh = _p(row, "maeHh1", default="")
        _mul_ser = _p(row, "maemulSer", "dspslGdsSeq", default="1")

        # 사진 URL 추출 (전경도 000241 우선, 없으면 첫 사진)
        _photo_url = ""
        _pics = [pp for pp in (db.get("csPicLst") or []) if isinstance(pp, dict)]
        if _pics:
            _pri = [pp for pp in _pics if str(pp.get("cortAuctnPicDvsCd") or "") == "000241"]
            _pp = (_pri or _pics)[0]
            _u = (_pp.get("picFileUrl") or "").strip()
            _fn = (_pp.get("picTitlNm") or "").strip()
            if _u and _fn:
                _photo_url = (_u if _u.startswith("http") else BASE + _u) + _fn

        # 보증금 = 최저가 × 10%
        try:
            _deposit = str(int(int(str(_min_price).replace(",", "")) * 0.1))
        except Exception:
            _deposit = ""

        # 매각기일 → YYYY-MM-DD 변환
        _sale_iso = ""
        if _mae_giil and len(str(_mae_giil)) == 8:
            _sale_iso = f"{str(_mae_giil)[:4]}-{str(_mae_giil)[4:6]}-{str(_mae_giil)[6:]}"

        import urllib.parse
        _bid_params = urllib.parse.urlencode({
            "caseNo": _cs_no, "mulSer": _mul_ser, "court": _court,
            "saleDate": _sale_iso, "time": _mae_hh,
            "appraisal": _appraisal, "minPrice": _min_price, "deposit": _deposit,
            "photoUrl": _photo_url,
        })

        _, b1, b2, b3 = st.columns([5, 1, 1, 1])
        with b1:
            st.link_button("📝 입찰신청서", f"https://realty-board.vercel.app/bid-form.html?{_bid_params}", use_container_width=True)
        with b2:
            st.link_button("📄 입찰표", "https://realty-board.vercel.app/bid-sheet.html", use_container_width=True)
        with b3:
            st.link_button("📋 확인설명서", "https://realty-board.vercel.app/auction-form.html", use_container_width=True)
        md("<div style='height:8px'></div>")

        render_detail(db, da, ddxdy, ddlvr, dcurst)
        return

    # 검색
    params, search_btn = render_form()
    st.session_state.setdefault("page_no", 1)
    st.session_state.setdefault("last_p", None)

    if search_btn:
        st.session_state["last_p"] = params
        st.session_state["page_no"] = 1

    if st.session_state["last_p"] is None:
        md("""
        <div class="empty">
          <div class="ico">🏛</div>
          <div class="t1">검색 조건을 입력하고 검색 버튼을 눌러주세요</div>
          <div class="t2">법원 · 지역 · 용도 · 금액 등 다양한 조건으로 경매 물건을 검색할 수 있습니다</div>
        </div>
        """)
        return

    p = st.session_state["last_p"]
    page = st.session_state["page_no"]
    with st.spinner("검색 중..."):
        rows, total = search_page(page, p)

    if not rows and total == 0:
        md("<div class='nodata'>검색 결과가 없습니다.</div>")
        return

    total_pages = max(1, (total + 9) // 10)
    md(f"<div class='r-stat'>검색 결과 <b>{total:,}건</b> &nbsp;|&nbsp; {page} / {total_pages} 페이지</div>")

    if rows:
        df = pd.DataFrame(rows)
        cdl, _ = st.columns([2, 8])
        with cdl:
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button("📥 엑셀 다운로드", buf, "경매결과.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

    # (사건번호 + 물건번호)로 묶어 카드 1개 — 목록 여러 개는 합쳐 표시
    seen, groups = {}, []
    for i, row in enumerate(rows):
        cs = _p(row, "userCsNo", "srnSaNo", "csNo", "saNo", default="")
        mul = _p(row, "maemulSer", "dspslGdsSeq", default="")
        key = (cs, mul)
        if key in seen:
            seen[key][1].append(row)
        else:
            seen[key] = [i, [row]]
            groups.append(seen[key])
    for first_idx, grp in groups:
        render_card(grp, first_idx, page)

    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("◀  이전", disabled=(page <= 1), use_container_width=True):
        st.session_state["page_no"] -= 1
        st.rerun()
    c2.markdown(f"<div style='text-align:center;padding-top:8px;font-size:13px;color:#64748b'>{page} / {total_pages} 페이지</div>",
                unsafe_allow_html=True)
    if c3.button("다음  ▶", disabled=(page >= total_pages), use_container_width=True):
        st.session_state["page_no"] += 1
        st.rerun()


if __name__ == "__main__":
    main()
