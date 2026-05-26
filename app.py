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
STATUS_OPTS = {"진행중": "0004601", "전체": "", "매각": "0004603", "취하/취소": "0004604", "기각/각하": "0004605"}
BID_DVS = {"전체": "", "기일입찰": "1", "기간입찰": "2"}
SPECIAL_CONDS = [("법정지상권", "A"), ("별도등기", "B"), ("유치권", "C"), ("분묘기지권", "D"), ("재매각", "E"),
                 ("특별매각조건", "F"), ("농지취득", "G"), ("예고등기", "H"), ("선순위", "I"), ("우선매수신고", "J")]
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



# ══════════════════════════════════════════════════════════════════════════════
#  Vercel API 연동 (토지특성/건축물)
# ══════════════════════════════════════════════════════════════════════════════
VERCEL_BASE = "https://realty-board.vercel.app/api"

def vercel_geocode(address):
    try:
        r = requests.get(f"{VERCEL_BASE}/geocode?address={requests.utils.quote(address)}", timeout=10)
        return r.json()
    except:
        return {}

def vercel_land(pnu):
    try:
        r = requests.get(f"{VERCEL_BASE}/land?pnu={pnu}", timeout=10)
        data = r.json()
        parsed = data.get("parsed") or data
        fields = parsed.get("landCharacteristicss", {}).get("field") or parsed.get("landCharacteristics", {}).get("field") or []
        if isinstance(fields, list) and fields:
            return max(fields, key=lambda x: int(x.get("stdrYear", "0")))
        elif isinstance(fields, dict):
            return fields
        return {}
    except:
        return {}

def vercel_building(pnu):
    try:
        r = requests.get(f"{VERCEL_BASE}/building?pnu={pnu}", timeout=10)
        data = r.json()
        parsed = data.get("parsed") or data
        items = parsed.get("response", {}).get("body", {}).get("items", {}).get("item")
        if isinstance(items, list): return items
        elif items: return [items]
        return []
    except:
        return []

def vercel_realtrade(lawd_cd, months=6):
    """Vercel 실거래 API로 최근 N개월 토지 거래 조회"""
    from datetime import date as _date
    all_trades = []
    now = _date.today()
    for m in range(months):
        y = now.year
        mo = now.month - m
        while mo <= 0:
            mo += 12; y -= 1
        ym = f"{y}{mo:02d}"
        try:
            r = requests.get(f"{VERCEL_BASE}/realtrade?lawdCd={lawd_cd}&dealYmd={ym}", timeout=15)
            data = r.json()
            items = data.get("items") or []
            all_trades.extend(items)
        except:
            pass
    return all_trades

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
AEE_ITM = {
    "00083001": "위치 및 주위환경", "00083002": "위치 및 주위환경",
    "00083003": "교통상황", "00083005": "인접 도로상태 등",
    "00083006": "이용상태", "00083009": "토지의 형상 및 이용상태",
    "00083011": "공법상의 제한 및 토지이용계획", "00083014": "제시외 건물",
    "00083015": "건물의 구조", "00083017": "설비내역", "00083026": "임대관계 및 기타",
}


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


# ── 네이버 부동산 연동 ──
NV_TRADE = {"매매": "A1", "전세": "B1", "월세": "B2"}
NV_RETYPE = {"아파트": "APT", "오피스텔": "OPST", "빌라/연립": "VL",
             "단독/다가구": "DDDGG", "토지": "TJ", "상가": "SG",
             "사무실": "SMS", "공장/창고": "GJCG"}


def naver_cortar(db, da=None):
    """경매 소재지 코드 → 네이버 법정동코드(10자리 cortarNo). db/da 전체를 재귀 탐색."""
    srcs = [db] + ([da] if da else [])

    def all_dicts(x):
        out = []

        def w(o):
            if isinstance(o, dict):
                out.append(o)
                for v in o.values():
                    w(v)
            elif isinstance(o, list):
                for e in o:
                    w(e)
        w(x)
        return out

    rows = [r for s in srcs for r in all_dicts(s)]
    # 1) 시도+시군구+읍면동(+리) 코드 조합
    for r in rows:
        sd = str(r.get("adongSdCd") or r.get("sidoCd") or "").strip()
        sgg = str(r.get("adongSggCd") or r.get("sggCd") or "").strip()
        emd = str(r.get("adongEmdCd") or r.get("emdCd") or "").strip()
        if sd and sgg and emd and sd not in ("0", "00"):
            ri = str(r.get("adongRiCd") or "0").strip()
            code = sd.zfill(2) + sgg.zfill(3) + emd.zfill(3) + ri.zfill(2)
            if code[:2] != "00":
                return code[:10]
    # 2) 단일 법정동코드(10자리) 필드 탐색
    for r in rows:
        for k, v in r.items():
            kl = k.lower()
            if "ldong" in kl or "bjd" in kl or "hjd" in kl or kl.endswith("dongcd") \
               or "lawd" in kl or "cortar" in kl:
                s = str(v or "")
                if re.fullmatch(r"\d{10}", s):
                    return s
    return ""


def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _naver_headers(token, cookie):
    token = (token or "").strip()
    if token and not token.lower().startswith("bearer"):
        token = "Bearer " + token
    hdr = {
        "Authorization": token,
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        "Referer": "https://new.land.naver.com/",
        "Accept": "*/*", "Accept-Language": "ko-KR,ko;q=0.9",
    }
    if cookie:
        hdr["Cookie"] = cookie
    return hdr


def naver_cortar_by_coord(lat, lng, token, cookie, zoom=16, timeout=10):
    """좌표(WGS84) → 네이버 법정동코드(cortarNo). (code, error) 반환."""
    if not (token or "").strip():
        return "", "토큰이 필요합니다."
    hdr = _naver_headers(token, cookie)
    try:
        r = requests.get("https://new.land.naver.com/api/cortars", headers=hdr,
                         params={"zoom": zoom, "centerLat": lat, "centerLon": lng},
                         timeout=timeout)
    except Exception as e:
        return "", f"요청 실패: {e}"
    if r.status_code == 401:
        return "", "401 인증 실패 — 토큰이 만료되었습니다."
    if r.status_code == 429:
        return "", "429 차단 — 잠시 후 다시 시도하세요."
    if r.status_code != 200:
        return "", f"HTTP {r.status_code}"
    try:
        d = r.json()
    except Exception:
        return "", "응답 파싱 실패"
    code = d.get("cortarNo")
    if not code and isinstance(d.get("cortar"), dict):
        code = d["cortar"].get("cortarNo")
    code = str(code or "")
    return (code, "") if re.fullmatch(r"\d{10}", code) else ("", "좌표→법정동 변환 실패")


def naver_fetch_articles(cortar, token, cookie, trade="A1", retype="APT",
                         max_pages=5, timeout=10):
    """네이버 부동산 매물 목록 조회. (articleList, error_msg) 반환."""
    if not (token or "").strip():
        return [], "네이버 Authorization 토큰이 필요합니다."
    hdr = _naver_headers(token, cookie)
    out, page = [], 1
    while page <= max_pages:
        params = {
            "cortarNo": cortar, "order": "rank",
            "realEstateType": retype, "tradeType": trade,
            "tag": "::::::::", "rentPriceMin": 0, "rentPriceMax": 900000000,
            "priceMin": 0, "priceMax": 900000000, "areaMin": 0, "areaMax": 900000000,
            "showArticle": "false", "sameAddressGroup": "false",
            "priceType": "RETAIL", "page": page,
        }
        try:
            r = requests.get("https://new.land.naver.com/api/articles",
                             headers=hdr, params=params, timeout=timeout)
        except Exception as e:
            return out, f"요청 실패: {e}"
        if r.status_code == 401:
            return out, "401 인증 실패 — 토큰이 만료되었습니다. 새로 복사해 주세요."
        if r.status_code == 429:
            return out, "429 차단 — 잠시 후 다시 시도하거나 Cookie를 갱신하세요."
        if r.status_code != 200:
            return out, f"HTTP {r.status_code}"
        data = r.json()
        out.extend(data.get("articleList") or [])
        if not data.get("isMoreData"):
            break
        page += 1
    return out, ""


# ── 국토부 실거래가(매매) 연동 + 원/평 단가 분석 ──
PYEONG = 3.305785  # 1평 = 3.305785㎡

MOLIT_SVC = {
    "토지": ("RTMSDataSvcLandTrade", "getRTMSDataSvcLandTrade"),
    "공장 및 창고": ("RTMSDataSvcInduTrade", "getRTMSDataSvcInduTrade"),
    "단독/다가구": ("RTMSDataSvcSHTrade", "getRTMSDataSvcSHTrade"),
    "아파트": ("RTMSDataSvcAptTrade", "getRTMSDataSvcAptTrade"),
    "연립/다세대": ("RTMSDataSvcRHTrade", "getRTMSDataSvcRHTrade"),
    "오피스텔": ("RTMSDataSvcOffiTrade", "getRTMSDataSvcOffiTrade"),
    "상업업무용": ("RTMSDataSvcNrgTrade", "getRTMSDataSvcNrgTrade"),
}


def _area_m2(s):
    m = re.search(r"([\d,]+\.?\d*)\s*㎡", str(s or ""))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except Exception:
            return None
    return None


def auction_area_m2(db):
    """경매 물건 전용면적(㎡) 추출."""
    for o in (db.get("gdsDspslObjctLst") or []):
        if isinstance(o, dict):
            a = _area_m2(o.get("pjbBuldList") or o.get("objctArDts"))
            if a:
                return a
    for r in _dicts_deep(db.get("bldSdtrDtlLstAll") or []):
        if str(r.get("rletDvsDts")) == "전유":
            a = _area_m2(r.get("bldSdtrDtlDts"))
            if a:
                return a
    return None


def auction_bldnm(db):
    for o in (db.get("gdsDspslObjctLst") or []):
        if isinstance(o, dict) and o.get("bldNm"):
            return str(o["bldNm"]).strip()
    return ""


def danga_pyeong(won, area_m2):
    """원/평 단가."""
    try:
        won, area_m2 = float(won), float(area_m2)
        if won > 0 and area_m2 > 0:
            return won / (area_m2 / PYEONG)
    except Exception:
        pass
    return None


def parse_naver_price(s):
    """'3억 5,000' / '8,500' / '12억' → 원 (네이버 만원 단위)."""
    s = str(s or "").replace(" ", "")
    if not s:
        return None
    eok = 0
    m = re.search(r"(\d+)억", s)
    if m:
        eok = int(m.group(1))
        s = s[m.end():]
    s = s.replace(",", "")
    m2 = re.search(r"(\d+)", s)
    man = int(m2.group(1)) if m2 else 0
    won = eok * 100000000 + man * 10000
    return won or None


def molit_lawd(cortar):
    c = re.sub(r"\D", "", str(cortar or ""))
    return c[:5] if len(c) >= 5 else ""


def auction_lawd(db, da=None):
    """경매 데이터 → 시군구코드(LAWD_CD 5자리). 토큰 불필요, db/da 재귀 탐색."""
    srcs = [db] + ([da] if da else [])

    def all_dicts(x):
        out = []

        def w(o):
            if isinstance(o, dict):
                out.append(o)
                for v in o.values():
                    w(v)
            elif isinstance(o, list):
                for e in o:
                    w(e)
        w(x)
        return out

    rows = [r for s in srcs for r in all_dicts(s)]
    for r in rows:
        sd = re.sub(r"\D", "", str(r.get("adongSdCd") or r.get("sidoCd") or ""))
        sgg = re.sub(r"\D", "", str(r.get("adongSggCd") or r.get("sggCd")
                                     or r.get("gugunCd") or ""))
        if sd and sgg and sd not in ("0", "00"):
            code = sd.zfill(2) + sgg.zfill(3)
            if code[:2] != "00":
                return code[:5]
    for r in rows:
        for k, v in r.items():
            kl = k.lower()
            if any(t in kl for t in ("ldong", "bjd", "hjd", "lawd", "adongcd",
                                     "cortar", "dongcd", "legalcd")):
                s = re.sub(r"\D", "", str(v or ""))
                if len(s) == 10:
                    return s[:5]
                if len(s) == 5:
                    return s
    return ""


def lawd_by_name(service_key, name, timeout=12):
    """행안부 법정동코드 API(StanReginCd)로 지역명 → 시군구코드(5자리). (code, error)."""
    if not (service_key or "").strip():
        return "", "서비스키가 필요합니다."
    if not name:
        return "", "지역명이 없습니다."
    url = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
    params = {"serviceKey": service_key, "type": "json", "pageNo": 1,
              "numOfRows": 50, "locatadd_nm": name}
    try:
        r = requests.get(url, params=params, timeout=timeout)
    except Exception as e:
        return "", f"요청 실패: {e}"
    if r.status_code != 200:
        return "", f"HTTP {r.status_code}"
    try:
        d = r.json()
    except Exception:
        return "", "응답 파싱 실패 — 서비스키(Decoding)·승인 여부 확인"
    rows = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("row"), list):
                rows.extend([x for x in o["row"] if isinstance(x, dict)])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for e in o:
                walk(e)
    walk(d)
    if not rows:
        return "", "코드 조회 결과 없음 (지역명/승인 확인)"
    # 시도+시군구 코드 우선
    for x in rows:
        sd = re.sub(r"\D", "", str(x.get("sido_cd") or ""))
        sgg = re.sub(r"\D", "", str(x.get("sgg_cd") or ""))
        if sd and sgg and sgg != "000" and sd not in ("", "00"):
            return (sd.zfill(2) + sgg.zfill(3))[:5], ""
    for x in rows:
        rc = re.sub(r"\D", "", str(x.get("region_cd") or ""))
        if len(rc) >= 5 and rc[2:5] != "000":
            return rc[:5], ""
    return "", "시군구코드를 찾지 못했습니다."


def molit_fetch_trades(service_key, lawd_cd, svc_key="아파트", months=6, timeout=12):
    """국토부 실거래가(매매) 최근 N개월 조회. (records, error)."""
    if not (service_key or "").strip():
        return [], "공공데이터포털 서비스키가 필요합니다."
    if not lawd_cd:
        return [], "시군구코드(LAWD_CD)를 만들 수 없습니다."
    svc, op = MOLIT_SVC.get(svc_key, MOLIT_SVC["아파트"])
    base = f"https://apis.data.go.kr/1613000/{svc}/{op}"
    today = date.today()
    recs = []
    for i in range(int(months)):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        params = {"serviceKey": service_key, "LAWD_CD": lawd_cd,
                  "DEAL_YMD": f"{y}{m:02d}", "numOfRows": 1000, "pageNo": 1}
        try:
            r = requests.get(base, params=params, timeout=timeout)
        except Exception as e:
            return recs, f"요청 실패: {e}"
        if r.status_code != 200:
            return recs, f"HTTP {r.status_code} (서비스키/엔드포인트 확인)"
        try:
            root = ET.fromstring(r.content)
        except Exception:
            return recs, "응답 파싱 실패 — 서비스키(Decoding)·승인 여부를 확인하세요."
        rc = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode")
        if rc and rc not in ("00", "000", "0"):
            msg = (root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg")
                   or root.findtext(".//errMsg") or rc)
            return recs, f"API 오류: {msg}"
        for it in root.iter("item"):
            def g(*ks):
                for k in ks:
                    t = it.findtext(k)
                    if t and t.strip():
                        return t.strip()
                return ""
            amt = g("dealAmount", "거래금액").replace(",", "")
            try:
                won = int(amt) * 10000
            except Exception:
                won = None
            try:
                a = float(g("excluUseAr", "전용면적", "dealArea", "거래면적",
                            "plottageAr", "totalFloorAr", "bldgAr", "buildingAr",
                            "archArea", "건물면적"))
            except Exception:
                a = None
            recs.append({
                "거래일": f"{g('dealYear', '년')}-{(g('dealMonth', '월') or '0').zfill(2)}-"
                          f"{(g('dealDay', '일') or '0').zfill(2)}",
                "단지": g("aptNm", "아파트", "offiNm", "mhouseNm", "연립다세대",
                          "단지명", "bldgNm", "buildingName"),
                "전용㎡": a, "금액원": won, "층": g("floor", "층"),
                "건축년도": g("buildYear", "건축년도"), "법정동": g("umdNm", "법정동"),
            })
    return recs, ""


def analyze_trades(recs, bld_nm, area_m2):
    """실거래 레코드 → 원/평 단가 요약(단지 우선, 없으면 평형±10%, 없으면 동 전체)."""
    rows = []
    for r in recs:
        dp = danga_pyeong(r.get("금액원"), r.get("전용㎡"))
        if dp:
            rows.append((r, dp))
    bn = (bld_nm or "").replace(" ", "")
    matched = [(r, dp) for (r, dp) in rows
               if bn and len(bn) >= 2 and bn[:6] in (r["단지"] or "").replace(" ", "")]
    area_rows = []
    if area_m2:
        area_rows = [(r, dp) for (r, dp) in rows
                     if r["전용㎡"] and abs(r["전용㎡"] - area_m2) / area_m2 <= 0.1]
    pick = matched or area_rows or rows
    dps = [dp for (_, dp) in pick]
    return {
        "건수": len(pick),
        "중앙단가": statistics.median(dps) if dps else None,
        "기준": "단지일치" if matched else ("평형±10%" if area_rows else "동일동 전체"),
        "표본": [r for (r, _) in sorted(pick, key=lambda x: x[0]["거래일"], reverse=True)][:12],
    }


def _fv(k, v):
    if v in (None, ""):
        return "-"
    s = str(v)
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
    """감정평가요항(aeeWevlMnpntLst)을 항목명+내용으로 렌더."""
    lst = (db.get("aeeWevlMnpntLst") or da.get("aeeWevlMnpntLst")
           or find_list_by(db, "aeeWevlMnpnt") or find_list_by(da, "aeeWevlMnpnt") or [])
    rows = []
    for it in lst:
        if not isinstance(it, dict):
            continue
        ctt = str(it.get("aeeWevlMnpntCtt") or "").strip()
        if not ctt:
            continue
        itm = str(it.get("aeeWevlMnpntItmCd") or "")
        lab = (AEE_ITM.get(itm) or it.get("aeeWevlMnpntDvsNm")
               or it.get("aeeWevlMnpntNm") or "기타")
        ctt = ctt.replace('""', '"').replace("\r\n", "\n").replace("\r", "\n")
        rows.append((lab, ctt))
    return _desc_html(rows)


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


RGLT_KND = {"12401": "소유권", "12402": "지상권", "12403": "전세권", "12404": "임차권",
            "12405": "지역권"}


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
    # 검색 모드 분기 (첨부된 작동 코드 로직)
    #  - 법원 선택 시: cortStDvs="1", pgmId="PGJ151M01"
    #  - 지역(주소) 검색 시: cortStDvs="2", pgmId="PGJ151F01", statNum=1
    if p["court_cd"]:
        cort_st, pgm, statnum = "1", "PGJ151M01", ""
    else:
        cort_st, pgm, statnum = "2", "PGJ151F01", 1
    payload = {
        "dma_pageInfo": {"pageNo": page, "pageSize": 10, "bfPageNo": "", "startRowNo": "",
                         "totalCnt": "", "totalYn": "Y", "groupTotalCount": ""},
        "dma_srchGdsDtlSrchInfo": {
            "rletDspslSpcCondCd": p["spc_cond"], "bidDvsCd": p["bid_dvs"],
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
            "lclDspslGdsLstUsgCd": "", "mclDspslGdsLstUsgCd": "", "sclDspslGdsLstUsgCd": "",
            **{k: "" for k in ["mvprpDspslPlcAdongSdCd", "mvprpDspslPlcAdongSggCd",
                               "mvprpDspslPlcAdongEmdCd", "mvprpArtclKndCd", "mvprpArtclNm",
                               "mvprpAtchmPlcTypCd", "dspslDxdyYmd", "dspslPlcNm", "execrOfcDvsCd",
                               "fstDspslHm", "scndDspslHm", "thrdDspslHm", "fothDspslHm",
                               "gdsVendNm", "jdbnCd", "lafjOrderBy", "notifyLoc", "rdnmSdCd",
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

    # 용도 (핵심 필터) + 진행상태
    l, c = st.columns([1.3, 8])
    label(l, "용도")
    with c:
        c1, c2 = st.columns([3, 5])
        rlet_nm = c1.selectbox("rlet", list(RLET_KIND.keys()), label_visibility="collapsed", key="rlet_nm")
        with c2:
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
        for cols_, conds_ in [(st.columns(5), SPECIAL_CONDS[:5]), (st.columns(5), SPECIAL_CONDS[5:])]:
            for i, (nm, cd) in enumerate(conds_):
                if cols_[i].checkbox(nm, key=f"spc_{cd}"):
                    checked.append(cd)
    md("<div class='sep'></div>")

    # 버튼
    _, b1, b2 = st.columns([6.2, 1.2, 1])
    search_btn = b1.button("🔍  검색", use_container_width=True, type="primary")
    reset_btn = b2.button("↺  초기화", use_container_width=True)
    md('</div>')

    if reset_btn:
        for k in [k for k in st.session_state if k not in {"detail", "last_p", "page_no"}]:
            del st.session_state[k]
        st.rerun()

    params = {
        "court_cd": court_cd, "sd_cd": sd_cd, "sgg_cd": sgg_cd, "emd_cd": emd_cd,
        "cs_no": cs_no, "rlet_dvs": RLET_KIND[rlet_nm], "status": STATUS_OPTS[status_nm],
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
def render_card(row, idx, page):
    cs_no = _p(row, "userCsNo", "srnSaNo", "csNo", "saNo")
    court = _p(row, "jiwonNm", "boNm", "cortNm", "cortOfcNm", default="")
    dept = _p(row, "jpDeptNm", default="")
    kind = _p(row, "dspslUsgNm", "kindNm", "mvprpRletDvsNm", default="") \
        or RLET_CD2NM.get(_p(row, "mvprpRletDvsCd", default=""), "")
    # 소재지: 전체주소(printSt) 우선, 없으면 기존 키
    addr = _p(row, "printSt", "daepyoSt", "rprsAdongNm", "userSt", default="")
    # 목물(목록)별 구분 정보 — 동/호수·구조·면적·지목
    seg = " ".join(s for s in [
        _p(row, "buldList", default=""),
        _p(row, "areaList", default=""),
        (f"({_p(row, 'jimokList', default='')})" if _p(row, "jimokList", default="") not in ("", "-") else ""),
    ] if s and s != "-").strip()
    mok = _p(row, "mokmulSer", default="")
    aee = row.get("gamevalAmt") or row.get("gamsungGa") or row.get("aeeEvlAmt") or ""
    lws = row.get("minmaePrice") or row.get("choejeoChalga") or row.get("lwsDspslPrc") or ""
    rate = (row.get("notifyMinmaePriceRate1") or row.get("lwsDspslPrcRate")
            or row.get("lwsPrcRate") or "")
    bid_dt = _p(row, "maeGiil", "maegakDate", "dxdyYmd", "bidBgngYmd", default="")
    bid_hh = _p(row, "maeHh1", default="")
    flbd = _p(row, "yuchalCnt", "yuchulCnt", "flbdNcnt", default="0")
    stat = _p(row, "statNm", "procStatNm", "cortAuctnSrchCondNm", default="") \
        or ("진행중" if _p(row, "mulJinYn", default="") == "Y" else "진행중")

    stat_cls = ("bdg-ok" if "진행" in stat else "bdg-sold" if "매각" in stat
                else "bdg-no" if any(x in stat for x in ("취하", "기각", "각하")) else "bdg-etc")
    kind_h = f'<span class="bdg bdg-type">{kind}</span>' if kind else ""
    flbd_h = f'<span class="bdg bdg-flbd">유찰 {flbd}회</span>' if flbd and str(flbd) not in ("0", "") else ""
    rate_h = f'<span class="cprate">({rate}%)</span>' if rate and rate != "-" else ""
    court_txt = " ".join(t for t in [court, dept] if t and t != "-")
    court_h = f'<span class="ccourt">🏛 {court_txt}</span>' if court_txt else '<span class="ccourt"></span>'
    mok_h = f'<span class="bdg bdg-etc">목록 {mok}</span>' if mok and mok != "-" else ""
    seg_parts = [t for t in seg.split() if t and t not in addr]
    addr_full = " ".join([addr] + seg_parts).strip() or "소재지 정보 없음"
    bid_h = _d(bid_dt) + (f" {bid_hh[:2]}:{bid_hh[2:]}" if bid_hh.isdigit() and len(bid_hh) == 4 else "")

    md(f"""
    <div class="card">
      <div class="chead">
        <span class="cno">{cs_no}</span>{mok_h}{kind_h}{flbd_h}{court_h}
        <span class="bdg {stat_cls}">{stat}</span>
      </div>
      <div class="cbody">
        <div class="caddr">📍 {addr_full}</div>
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
        st.session_state["detail"] = row
        st.session_state["detail_row_idx"] = (page - 1) * 10 + idx
        st.rerun()
    md("<div style='height:8px'></div>")


# ══════════════════════════════════════════════════════════════════════════════
#  상세 페이지
# ══════════════════════════════════════════════════════════════════════════════
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
    obj_kind = RLET_CD2NM.get(rlet_cd) or gds0.get("mvprpRletDvsNm") or rlet_cd or "-"

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
                    "👥 임차인·이해관계인", "📁 문건/송달", "📊 시세분석"])

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
            data_bytes = _img_bytes(p)
            if data_bytes:
                imgs.append((data_bytes, p.get("picTitlNm") or ""))
            else:
                # 폴백: 디렉터리 경로 + 파일명으로 URL 구성
                u = (p.get("picFileUrl") or "")
                fn = p.get("picTitlNm") or ""
                if u:
                    url = (u if u.startswith("http") else BASE + u) + fn
                    try:
                        r = requests.get(url, headers=H_BASE, timeout=5)
                        if r.status_code == 200:
                            imgs.append((r.content, fn))
                    except Exception:
                        pass

        if imgs:
            md("<div class='sec'>물건 사진</div>")
            per_row = 4
            for s in range(0, len(imgs), per_row):
                chunk = imgs[s:s + per_row]
                cols = st.columns(len(chunk))
                for c, (content, _cap) in zip(cols, chunk):
                    with c:
                        try:
                            st.image(content, use_container_width=True)
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

    # ── 탭4: 임차인 + 이해관계인 + 현황조사 정보 ──
    with tabs[3]:
        lessees = find_list_by(dcurst, "LserLtn", "rntr", "tenant", "Lessr")
        md("<div class='sec'>임차인 현황</div>")
        md(_tbl(lessees) or "<div class='nodata'>임차인 정보 없음</div>")

        intrps = _find_list(da, "dlt_rletCsIntrpsLst")
        md("<div class='sec'>이해관계인</div>")
        md(_tbl(intrps) or "<div class='nodata'>이해관계인 정보 없음</div>")

        # 부동산의 현황 및 점유관계 조사서 - 기타 내용(gdsPossCtt) / 점유관계
        poss = collect_desc([dcurst, db], ["gdsPossCtt", "lstPossRltnDts"], "현황/점유")
        if poss:
            md("<div class='sec'>현황 및 점유관계 (기타)</div>")
            md(_desc_html(poss))

        # 현황조사 일자 등 (리스트/정크 제외한 잔여 정보)
        info = ""
        for k, v in (dcurst or {}).items():
            if k in DROP_TABLES or isinstance(v, list):
                continue
            if isinstance(v, dict) and v:
                info += _kv(v)
            elif isinstance(v, str) and v.strip() and k not in LONG_TEXT_COLS and k not in DROP_COLS:
                info += (f'<tr><th>{KOR.get(k, k)}</th><td>{_fv(k, v)}</td></tr>')
        # 문자열 모음을 표로
        if "<tr>" in info and "<table" not in info:
            info = f"<table class='kv'>{info}</table>"
        if info:
            md("<div class='sec'>현황조사 정보</div>")
            md(info)

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

    # ── 탭6: 시세분석 (국토부 실거래가 + 원/평 단가 비교, 누적·엑셀) ──
    with tabs[5]:
        # ── 토지정보 (Vercel API) ──
        addr_for_geo = addrs[0] if addrs else ""
        v_land = {}
        v_bldg = []
        v_jiga = 0
        v_area = 0.0
        if addr_for_geo:
            with st.spinner("토지특성 조회 중 (VWorld)..."):
                geo = vercel_geocode(addr_for_geo)
                v_pnu = geo.get("pnu")
                if v_pnu:
                    v_land = vercel_land(v_pnu)
                    v_bldg = vercel_building(v_pnu)

            if v_land:
                md("<div class='sec'>📐 토지 기본정보</div>")
                v_area = float(v_land.get("lndpclAr", 0) or 0)
                v_jiga = int(float(v_land.get("pblntfPclnd", 0) or 0))
                v_pyeong = round(v_area / 3.3058, 2) if v_area else 0
                jiga_total = int(v_jiga * v_area) if v_jiga and v_area else 0
                jiga_py = round(v_jiga * 3.3058) if v_jiga else 0

                t = "<table class='kv'>"
                t += f"<tr><th>소재지</th><td>{addr_for_geo}</td></tr>"
                t += f"<tr><th>지목</th><td>{v_land.get('lndcgrCodeNm', '-')}</td></tr>"
                t += f"<tr><th>면적</th><td>{v_area:,.1f}㎡ ({v_pyeong:,.2f}평)</td></tr>"
                t += f"<tr><th>용도지역</th><td><b>{v_land.get('prposArea1Nm', '-')}</b></td></tr>"
                t += f"<tr><th>이용상황</th><td>{v_land.get('ladUseSittnNm', '-')}</td></tr>"
                t += f"<tr><th>도로접면</th><td>{v_land.get('roadSideCodeNm', '-')}</td></tr>"
                t += f"<tr><th>지형높이</th><td>{v_land.get('tpgrphHgCodeNm', '-')}</td></tr>"
                t += f"<tr><th>지형형상</th><td>{v_land.get('tpgrphFrmCodeNm', '-')}</td></tr>"
                t += f"<tr><th>공시지가(㎡)</th><td><b>{v_jiga:,}원/㎡</b> ({v_land.get('stdrYear', '')}년)</td></tr>"
                t += f"<tr><th>공시지가(평)</th><td>{jiga_py:,}원/평</td></tr>"
                t += f"<tr><th>공시지가 총액</th><td><b>{jiga_total:,}원</b> ({fmt_krw(jiga_total)})</td></tr>"
                t += "</table>"
                md(t)

                # 감정가 대비
                try:
                    aee_w = int(str(aee_evl).replace(",", "")) if aee_evl else 0
                except:
                    aee_w = 0
                if aee_w and jiga_total:
                    ratio = aee_w / jiga_total * 100
                    if ratio > 100:
                        st.success(f"📌 감정가가 공시지가 총액의 **{ratio:.1f}%** (공시지가 대비 높게 평가)")
                    else:
                        st.info(f"📌 감정가가 공시지가 총액의 **{ratio:.1f}%**")

                # 규제 체크리스트
                md("<div class='sec'>⚠️ 규제 체크리스트</div>")
                yongdo = v_land.get("prposArea1Nm", "")
                jimok = v_land.get("lndcgrCodeNm", "")
                road = v_land.get("roadSideCodeNm", "")
                usage = v_land.get("ladUseSittnNm", "")
                checks = []
                if "농림" in yongdo: checks.append(("⚠️", "농림지역 — 농지전용허가 필요, 농업진흥구역 확인"))
                if "보전관리" in yongdo: checks.append(("⚠️", "보전관리지역 — 개발행위 제한 강함"))
                if "보전녹지" in yongdo or "자연환경보전" in yongdo: checks.append(("⚠️", "보전계열 — 개발 극히 제한"))
                if "계획관리" in yongdo: checks.append(("✅", "계획관리지역 — 개발 가능성 상대적으로 양호"))
                if "생산관리" in yongdo: checks.append(("ℹ️", "생산관리지역 — 행위제한 중간"))
                if jimok in ("전", "답", "과수원"): checks.append(("⚠️", f"지목 {jimok} — 농지취득자격증명(농취증) 필요"))
                if jimok == "임야": checks.append(("⚠️", "지목 임야 — 산지관리법 적용, 보전산지/준보전산지 확인"))
                if "맹지" in road: checks.append(("🔴", "맹지 — 진입로 확보·사도 개설 검토 필수"))
                if road and "맹지" not in road and "없" not in road: checks.append(("✅", f"도로접면: {road}"))
                if not checks: checks.append(("ℹ️", "특이 규제 징후 없음 — 토지이음·현장 확인 별도 권장"))
                for icon, txt in checks:
                    st.markdown(f"- {icon} {txt}")

            # 건축물대장
            if v_bldg:
                md("<div class='sec'>🏢 건축물대장</div>")
                for b in v_bldg[:5]:
                    t = "<table class='kv'>"
                    t += f"<tr><th>건물명</th><td>{b.get('bldNm', '-') or '-'}</td></tr>"
                    t += f"<tr><th>주용도</th><td>{b.get('mainPurpsCdNm', '-')}</td></tr>"
                    t += f"<tr><th>구조</th><td>{b.get('strctCdNm', '-')}</td></tr>"
                    t += f"<tr><th>연면적</th><td>{float(b.get('totArea', 0)):,.1f}㎡</td></tr>"
                    t += f"<tr><th>층수</th><td>지상 {b.get('grndFlrCnt', 0)}층 / 지하 {b.get('ugrndFlrCnt', 0)}층</td></tr>"
                    t += f"<tr><th>사용승인</th><td>{_d(b.get('useAprDay', ''))}</td></tr>"
                    t += "</table>"
                    md(t)
            elif v_land:
                st.info("🏗️ 건축물대장에 등록된 건물 없음 — 나지(裸地)로 판단")

            st.divider()

        # ── 인근 유사 토지 실거래 (Vercel API, 자동 필터링) ──
        if addr_for_geo and v_land:
            md("<div class='sec'>📈 인근 유사 토지 실거래</div>")
            v_yongdo = v_land.get("prposArea1Nm", "")
            v_jimok = v_land.get("lndcgrCodeNm", "")
            lawd5 = v_pnu[:5] if v_pnu else ""

            if lawd5:
                with st.spinner("인근 실거래 조회 중 (최근 24개월)..."):
                    raw_trades = vercel_realtrade(lawd5, months=24)

                if raw_trades:
                    # 필터: 같은 읍면동 + 토지 거래만
                    addr_parts = addr_for_geo.split()
                    umd = ""
                    for ap in addr_parts:
                        if ap.endswith(("읍", "면", "동", "리")):
                            umd = ap; break

                    filtered = []
                    for t in raw_trades:
                        t_umd = t.get("umdNm", "")
                        t_area = float(t.get("dealArea", 0) or 0)
                        t_amt_raw = str(t.get("dealAmount", "0")).replace(",", "").strip()
                        try:
                            t_amt = int(t_amt_raw) * 10000
                        except:
                            continue
                        if t_area <= 0 or t_amt <= 0:
                            continue
                        pp = int(t_amt / t_area * 3.3058)
                        pp_m2 = int(t_amt / t_area)
                        filtered.append({
                            "거래일": f"{t.get('dealYear','')}.{str(t.get('dealMonth','')).zfill(2)}",
                            "읍면동": t_umd,
                            "지목": t.get("jimok", ""),
                            "면적(㎡)": f"{t_area:,.1f}",
                            "면적(평)": f"{t_area/3.3058:,.1f}",
                            "거래가": fmt_krw(t_amt),
                            "단가(원/㎡)": f"{pp_m2:,}",
                            "단가(원/평)": f"{pp:,}",
                            "_umd": t_umd,
                            "_pp": pp,
                        })

                    # 같은 읍면동 우선, 없으면 전체
                    same_umd = [t for t in filtered if umd and umd in t["_umd"]]
                    display_list = same_umd if same_umd else filtered

                    if display_list:
                        # 통계
                        pps = [t["_pp"] for t in display_list if t["_pp"] > 0]
                        if pps:
                            avg_pp = sum(pps) // len(pps)
                            min_pp = min(pps)
                            max_pp = max(pps)
                            scope = f"같은 읍면동({umd})" if same_umd else "같은 시군구"

                            tc1, tc2, tc3, tc4 = st.columns(4)
                            tc1.metric(f"{scope} 거래", f"{len(display_list)}건")
                            tc2.metric("평균 단가", f"{avg_pp:,}원/평")
                            tc3.metric("최저", f"{min_pp:,}원/평")
                            tc4.metric("최고", f"{max_pp:,}원/평")

                            # 감정가/최저가 대비
                            try:
                                aee_w2 = int(str(aee_evl).replace(",", "")) if aee_evl else 0
                            except:
                                aee_w2 = 0
                            try:
                                lws_w2 = int(str(lws_prc).replace(",", "")) if lws_prc else 0
                            except:
                                lws_w2 = 0

                            if v_area > 0 and avg_pp > 0:
                                if lws_w2:
                                    lws_pp = int(lws_w2 / (v_area / 3.3058))
                                    diff = ((lws_pp - avg_pp) / avg_pp * 100)
                                    if diff < 0:
                                        st.success(f"📌 최저가 평단가 **{lws_pp:,}원/평** → 실거래 평균 대비 **{diff:+.1f}%** (저렴)")
                                    else:
                                        st.warning(f"📌 최저가 평단가 **{lws_pp:,}원/평** → 실거래 평균 대비 **{diff:+.1f}%** (비쌈)")

                        # 테이블
                        df_rt = pd.DataFrame(display_list)
                        df_rt = df_rt.drop(columns=["_umd", "_pp"])
                        st.dataframe(df_rt, use_container_width=True, hide_index=True)
                    else:
                        st.info("필터 조건에 맞는 실거래 내역 없음")
                else:
                    st.info("최근 6개월 실거래 내역 없음")

            st.divider()

        md("<div class='sec'>시세분석 — 원/평 단가 비교</div>")
        area = auction_area_m2(db)
        bld_nm = auction_bldnm(db)
        data_lawd = auction_lawd(db, da)
        sgg_nm = ""
        for r in _dicts_deep(db.get("gdsRletStLtnoLstAll") or []):
            sgg_nm = " ".join(x for x in [r.get("adongSdNm"), r.get("adongSggNm")] if x)
            if sgg_nm:
                break
        if not sgg_nm and addrs:
            sgg_nm = " ".join(addrs[0].split()[:2])
        try:
            aee_won = int(str(aee_evl).replace(",", "")) if aee_evl else None
        except Exception:
            aee_won = None
        try:
            lws_won = int(str(lws_prc).replace(",", "")) if lws_prc else None
        except Exception:
            lws_won = None
        pyeong = round(area / PYEONG, 2) if area else None
        st.caption(f"전용면적: {area or '-'}㎡ ({pyeong or '-'}평)  ·  단지: {bld_nm or '-'}  ·  "
                   f"{sgg_nm or ''}  ·  시군구코드: "
                   f"{data_lawd or '조회 시 지역명으로 자동 결정'}")

        if not area:
            st.warning("전용면적을 추출하지 못해 단가 계산을 할 수 없습니다.")
        c1, c2 = st.columns([2, 1])
        svc_key = c1.selectbox("실거래 유형", list(MOLIT_SVC.keys()), key="mo_type")
        months = c2.number_input("조회 개월", min_value=1, max_value=24, value=6, key="mo_months")
        skey = st.text_input("국토부(공공데이터포털) 서비스키 (Decoding)",
                             type="password", key="mo_key",
                             help="data.go.kr 마이페이지 → '일반 인증키(Decoding)'. "
                                  "실거래가 + 법정동코드(StanReginCd) API 모두 활용신청 필요")

        if st.button("실거래 조회·분석", key="mo_go"):
            use_lawd = data_lawd
            if not use_lawd and skey and sgg_nm:
                with st.spinner("지역명으로 시군구코드 자동 조회 중..."):
                    use_lawd, lerr = lawd_by_name(skey, sgg_nm)
                if use_lawd:
                    st.caption(f"자동 결정된 시군구코드: {use_lawd} ({sgg_nm})")
                elif lerr:
                    st.error(f"시군구코드 자동조회 실패: {lerr}")
            if not area:
                st.error("전용면적이 없어 분석할 수 없습니다.")
            elif not use_lawd:
                st.error("시군구코드를 자동으로 찾지 못했습니다. 서비스키 승인 상태와 "
                         "법정동코드 API 활용신청 여부를 확인하세요.")
            else:
                with st.spinner("국토부 실거래가 조회 중..."):
                    recs, merr = molit_fetch_trades(skey, use_lawd, svc_key, int(months))
                if merr:
                    st.error(merr)
                summ = analyze_trades(recs, bld_nm, area) if recs else {
                    "건수": 0, "중앙단가": None, "기준": "-", "표본": []}

                aee_dp = danga_pyeong(aee_won, area)
                lws_dp = danga_pyeong(lws_won, area)
                rt_med = summ["중앙단가"]

                def pct_below(price_dp, ref_dp):
                    if price_dp and ref_dp:
                        return round((1 - price_dp / ref_dp) * 100, 1)
                    return None

                def won_p(v):
                    return f"{round(v):,}원/평" if v else "-"

                st.markdown("##### 단가 비교 (원/평)")
                comp = pd.DataFrame([
                    {"구분": "감정평가액", "총액": fmt_krw(aee_won), "원/평": won_p(aee_dp)},
                    {"구분": "최저매각가", "총액": fmt_krw(lws_won), "원/평": won_p(lws_dp)},
                    {"구분": f"실거래 중앙({summ['기준']}·{summ['건수']}건)",
                     "총액": "-", "원/평": won_p(rt_med)},
                ])
                st.dataframe(comp, use_container_width=True, hide_index=True)

                d_rt = pct_below(lws_dp, rt_med)
                d_aee = pct_below(lws_dp, aee_dp)
                msgs = []
                if d_rt is not None:
                    msgs.append(f"최저가가 실거래 중앙 대비 **{d_rt:+.1f}%** "
                                + ("(쌈)" if d_rt > 0 else "(비쌈)"))
                if d_aee is not None:
                    msgs.append(f"감정가 대비 **{d_aee:+.1f}%**")
                if msgs:
                    st.info("  ·  ".join(msgs))

                if summ["표본"]:
                    st.markdown("##### 최근 실거래 (단가순 표본)")
                    sdf = pd.DataFrame([{
                        "거래일": r["거래일"], "단지": r["단지"],
                        "전용㎡": r["전용㎡"],
                        "금액": fmt_krw(r["금액원"]),
                        "원/평": won_p(danga_pyeong(r["금액원"], r["전용㎡"])),
                        "층": r["층"], "건축": r["건축년도"],
                    } for r in summ["표본"]])
                    st.dataframe(sdf, use_container_width=True, hide_index=True)

                # 누적용 현재 행 저장
                st.session_state["analysis_row"] = {
                    "사건번호": base.get("userCsNo", ""),
                    "소재지": (addrs[0] if addrs else ""),
                    "단지": bld_nm, "전용㎡": area, "전용평": pyeong,
                    "감정가": aee_won, "최저가": lws_won,
                    "감정단가(원/평)": round(aee_dp) if aee_dp else None,
                    "최저단가(원/평)": round(lws_dp) if lws_dp else None,
                    "실거래중앙단가(원/평)": round(rt_med) if rt_med else None,
                    "실거래건수": summ["건수"], "실거래기준": summ["기준"],
                    "최저가_실거래대비(%)": d_rt, "최저가_감정대비(%)": d_aee,
                }

        # 누적 / 내보내기
        st.divider()
        cc1, cc2, cc3 = st.columns(3)
        if cc1.button("➕ 이 물건 분석에 추가", key="pf_add"):
            row = st.session_state.get("analysis_row")
            if row:
                pf = st.session_state.setdefault("portfolio", [])
                pf = [r for r in pf if r.get("사건번호") != row.get("사건번호")]
                pf.append(row)
                st.session_state["portfolio"] = pf
                st.success(f"추가됨 (누적 {len(pf)}건). 먼저 '실거래 조회·분석'을 실행해야 값이 채워집니다.")
            else:
                st.warning("먼저 '실거래 조회·분석'을 실행하세요.")
        if cc3.button("🗑 누적 초기화", key="pf_clear"):
            st.session_state["portfolio"] = []
            st.info("누적 데이터를 초기화했습니다.")

        pf = st.session_state.get("portfolio", [])
        if pf:
            st.markdown(f"##### 누적 분석 ({len(pf)}건)")
            pdf = pd.DataFrame(pf)
            st.dataframe(pdf, use_container_width=True, hide_index=True)
            cc2.download_button("⬇ CSV 다운로드", pdf.to_csv(index=False).encode("utf-8-sig"),
                                file_name="경매_시세분석.csv", mime="text/csv", key="pf_csv")
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    pdf.to_excel(w, index=False, sheet_name="시세분석")
                st.download_button("⬇ 엑셀(xlsx) 다운로드", buf.getvalue(),
                                   file_name="경매_시세분석.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="pf_xlsx")
            except Exception:
                st.caption("xlsx 출력에는 openpyxl 패키지가 필요합니다 (pip install openpyxl). CSV로 받으세요.")


    # ── 서류 자동화 링크 ──
    st.divider()
    md("<div class='sec'>📄 서류 자동화</div>")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        st.link_button("📝 입찰 신청서 보내기", "https://realty-board.vercel.app/bid-form.html", use_container_width=True)
    with dc2:
        st.link_button("📄 기일입찰표 작성", "https://realty-board.vercel.app/bid-sheet.html", use_container_width=True)
    with dc3:
        st.link_button("📋 확인설명서", "https://realty-board.vercel.app/auction-form.html", use_container_width=True)

    with st.expander("🔧 원본 JSON (구축용 — 배포 전 제거)"):
        st.json({"pgj15B": db, "pgj15A": da, "기일상세": ddxdy, "문건송달": ddlvr, "현황조사": dcurst})


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  관심물건 / 의뢰인 / 일정
# ══════════════════════════════════════════════════════════════════════════════
def render_watchlist():
    st.subheader("⭐ 관심물건 관리")
    wl = st.session_state.get("watchlist", [])
    if not wl:
        st.info("검색 결과에서 물건을 관심등록하면 여기에 표시됩니다.")
        return
    for i, item in enumerate(wl):
        sale = item.get("saleDate", "")
        d_str, urg = "-", "⚪"
        if sale and len(str(sale)) == 8:
            try:
                sd = date(int(str(sale)[:4]), int(str(sale)[4:6]), int(str(sale)[6:]))
                d = (sd - date.today()).days
                d_str = f"D-{d}" if d > 0 else ("D-Day" if d == 0 else f"D+{abs(d)}")
                urg = "🔴" if d <= 3 else ("🟡" if d <= 7 else "🟢")
            except: pass
        with st.expander(f"{urg} {item.get('caseNo','-')} — {item.get('address','-')} | {fmt_krw(item.get('minPrice',0))} | {d_str}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("감정가", fmt_krw(item.get("appraisal", 0)))
            c2.metric("최저가", fmt_krw(item.get("minPrice", 0)))
            c3.metric("매각기일", _d(item.get("saleDate", "")))
            new_st = st.selectbox("상태", ["입찰예정","입찰완료","낙찰","패찰","포기"],
                index=["입찰예정","입찰완료","낙찰","패찰","포기"].index(item.get("status","입찰예정")), key=f"ws_{i}")
            item["status"] = new_st
            item["memo"] = st.text_area("메모", value=item.get("memo",""), key=f"wm_{i}")
            if st.button("🗑️ 삭제", key=f"wd_{i}"):
                st.session_state["watchlist"].pop(i); st.rerun()


def render_clients():
    st.subheader("👥 의뢰인 접수 현황")
    try:
        res = requests.get(f"{VERCEL_BASE}/notion-bid-list", timeout=10)
        items = res.json().get("items") or []
        if not items:
            st.info("접수된 의뢰인이 없습니다."); return
        for ni, item in enumerate(items):
            icon = "🏢" if item.get("bidType") == "법인" else "👤"
            sale = item.get("saleDate", "")
            d_str = "-"
            if sale:
                try:
                    sd = date.fromisoformat(sale); d = (sd - date.today()).days
                    d_str = f"D-{d}" if d > 0 else ("D-Day" if d == 0 else f"D+{abs(d)}")
                except: pass
            with st.expander(f"{icon} {item.get('caseNo','-')} | {item.get('name','-')} | {item.get('court','-')} | {d_str}"):
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("사건번호", item.get("caseNo","-"))
                c2.metric("입찰가", fmt_krw(item.get("bidPrice",0)))
                c3.metric("매각기일", sale or "-")
                c4.metric("연락처", item.get("phone","-"))
                st.text(f"주소: {item.get('address','-')}")
                if item.get("bidType") == "법인":
                    st.text(f"회사: {item.get('company','-')} | 사업자: {item.get('bizNo','-')}")
                dc1, dc2 = st.columns(2)
                with dc1: st.link_button("📄 입찰표", "https://realty-board.vercel.app/bid-sheet.html")
                with dc2: st.link_button("📋 확인설명서", "https://realty-board.vercel.app/auction-form.html")
    except Exception as e:
        st.error(f"노션 연동 실패: {e}")


def render_schedule():
    st.subheader("📅 입찰 일정 대시보드")
    schedule = []
    for item in st.session_state.get("watchlist", []):
        schedule.append({"유형":"⭐관심","사건번호":item.get("caseNo","-"),
            "소재지":item.get("address","-"),"금액":fmt_krw(item.get("minPrice",0)),
            "매각기일":_d(item.get("saleDate","")),"상태":item.get("status","-"),
            "_s":str(item.get("saleDate","99999999"))})
    try:
        res = requests.get(f"{VERCEL_BASE}/notion-bid-list", timeout=10)
        for item in (res.json().get("items") or []):
            sale = item.get("saleDate","")
            schedule.append({"유형":"👥의뢰","사건번호":item.get("caseNo","-"),
                "소재지":f"{item.get('name','')} ({item.get('court','')})",
                "금액":fmt_krw(item.get("bidPrice",0)),
                "매각기일":sale or "-","상태":"접수",
                "_s":sale.replace("-","") if sale else "99999999"})
    except: pass
    if schedule:
        schedule.sort(key=lambda x: x.get("_s","99999999"))
        df = pd.DataFrame(schedule).drop(columns=["_s"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("관심물건 등록 또는 의뢰인 접수가 없습니다.")


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

    # 최상위 네비게이션
    nav = st.radio("", ["🔍 검색", "⭐ 관심물건", "👥 의뢰인", "📅 일정"],
                   horizontal=True, label_visibility="collapsed")
    if nav == "⭐ 관심물건":
        render_watchlist(); return
    if nav == "👥 의뢰인":
        render_clients(); return
    if nav == "📅 일정":
        render_schedule(); return

    # 상세
    if "detail" in st.session_state:
        bk, _ = st.columns([1, 7])
        if bk.button("← 목록으로", use_container_width=True):
            del st.session_state["detail"]
            st.rerun()
        md("<div style='height:8px'></div>")

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
          st.session_state["_search_row"] = row
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

    for i, row in enumerate(rows):
        render_card(row, i, page)

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
