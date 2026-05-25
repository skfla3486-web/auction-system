import requests
import pandas as pd
import time
import streamlit as st
import io
from datetime import date, timedelta

st.set_page_config(page_title="경매 관리 시스템", page_icon="🏛️", layout="wide")

# ===== 상수 =====
VERCEL_BASE = "https://realty-board.vercel.app/api"

URL_SEARCH = "https://www.courtauction.go.kr/pgj/pgjsearch/searchControllerMain.on"
URL_SD     = "https://www.courtauction.go.kr/pgj/pgj002/selectAdongSdLst.on"
URL_SGG    = "https://www.courtauction.go.kr/pgj/pgj002/selectAdongSggLst.on"
URL_EMD    = "https://www.courtauction.go.kr/pgj/pgj002/selectAdongEmdLst.on"
URL_LCL    = "https://www.courtauction.go.kr/pgj/pgj002/selectLclLst.on"
URL_MCL    = "https://www.courtauction.go.kr/pgj/pgj002/selectMclLst.on"
URL_SCL    = "https://www.courtauction.go.kr/pgj/pgj002/selectSclLst.on"
URL_DETAIL = "https://www.courtauction.go.kr/pgj/pgj15B/selectAuctnCsSrchRslt.on"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://www.courtauction.go.kr",
    "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36",
}
HEADERS_SEARCH = {**HEADERS, "Submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch"}
HEADERS_DETAIL = {**HEADERS, "Submissionid": "mf_wfm_mainFrame_sbm_selectAuctnCsSrchRslt"}

OBJ_TYPES = {"전체": "", "아파트": "00031R", "토지": "00030R", "상가": "00033R"}


# ===== 유틸 =====
def fmt_price(v):
    try:
        n = int(float(str(v)))
    except:
        return "-"
    if n <= 0:
        return "-"
    eok = n // 100000000
    man = (n % 100000000) // 10000
    r = ""
    if eok > 0:
        r += f"{eok}억 "
    if man > 0:
        r += f"{man:,}만"
    return (r.strip() + "원") if r else f"{n:,}원"


def fmt_date(s):
    s = str(s).strip()
    if len(s) != 8 or not s.isdigit():
        return s or "-"
    return f"{s[:4]}.{s[4:6]}.{s[6:]}"


def safe_int(v):
    try:
        return int(float(str(v)))
    except:
        return 0


def _pick(row, *keys):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


# ===== 지역 API =====
@st.cache_data
def get_sd_list():
    res = requests.post(URL_SD, headers=HEADERS, json={"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "A"})
    items = res.json().get("data", {}).get("adongSdLst", [])
    return {i["name"]: i["code"] for i in items}


@st.cache_data
def get_sgg_list(sd_cd):
    if not sd_cd:
        return {}
    res = requests.post(URL_SGG, headers=HEADERS, json={"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "A", "adongSdCd": sd_cd})
    items = res.json().get("data", {}).get("adongSggLst", [])
    return {i["name"]: i["code"] for i in items}


@st.cache_data
def get_emd_list(sd_cd, sgg_cd):
    if not sd_cd or not sgg_cd:
        return {}
    res = requests.post(URL_EMD, headers=HEADERS, json={"pbancMidYn": "Y", "srchDvsCd": "B", "pbancDvsCd": "A", "adongSdCd": sd_cd, "adongSggCd": sgg_cd})
    items = res.json().get("data", {}).get("adongEmdLst", [])
    return {i["name"]: i["code"] for i in items}


@st.cache_data
def get_lcl_list():
    res = requests.post(URL_LCL, headers=HEADERS, json={"dsignUsgDvsCd": ""})
    data = res.json().get("data", {})
    items = data.get("usgLclLst") or data.get("lclLst") or []
    return {i["name"]: i["code"] for i in items}


@st.cache_data
def get_mcl_list(lcl_cd):
    if not lcl_cd:
        return {}
    res = requests.post(URL_MCL, headers=HEADERS, json={"code": lcl_cd})
    data = res.json().get("data", {})
    items = data.get("usgMclLst") or data.get("mclLst") or []
    return {i["name"]: i["code"] for i in items}


@st.cache_data
def get_scl_list(mcl_cd):
    if not mcl_cd:
        return {}
    res = requests.post(URL_SCL, headers=HEADERS, json={"code": mcl_cd})
    data = res.json().get("data", {})
    items = data.get("usgSclLst") or data.get("sclLst") or []
    return {i["name"]: i["code"] for i in items}


# ===== 검색 API =====
def fetch_page(page_no, sd_cd, sgg_cd, emd_cd, min_price, max_price, obj_type, cs_no, lcl_cd, mcl_cd, scl_cd, date_from, date_to):
    payload = {
        "dma_pageInfo": {"pageNo": page_no, "pageSize": 10, "bfPageNo": "", "startRowNo": "", "totalCnt": "", "totalYn": "Y", "groupTotalCount": ""},
        "dma_srchGdsDtlSrchInfo": {
            "rletDspslSpcCondCd": "", "bidDvsCd": "", "mvprpRletDvsCd": obj_type,
            "cortAuctnSrchCondCd": "0004601", "cortOfcCd": "", "cortStDvs": "2",
            "csNo": cs_no, "pgmId": "PGJ151F01",
            "aeeEvlAmtMax": max_price, "aeeEvlAmtMin": min_price,
            "bidBgngYmd": date_from, "bidEndYmd": date_to,
            "dspslDxdyYmd": "", "dspslPlcNm": "",
            "execrOfcDvsCd": "", "flbdNcntMax": "", "flbdNcntMin": "",
            "fothDspslHm": "", "fstDspslHm": "", "scndDspslHm": "", "thrdDspslHm": "",
            "gdsVendNm": "", "jdbnCd": "", "lafjOrderBy": "",
            "lwsDspslPrcMax": "", "lwsDspslPrcMin": "",
            "lwsDspslPrcRateMax": "", "lwsDspslPrcRateMin": "",
            "mvprpArtclKndCd": "", "mvprpArtclNm": "", "mvprpAtchmPlcTypCd": "",
            "rprsAdongSdCd": sd_cd, "rprsAdongSggCd": sgg_cd, "rprsAdongEmdCd": emd_cd,
            "mvprpDspslPlcAdongSdCd": "", "mvprpDspslPlcAdongSggCd": "", "mvprpDspslPlcAdongEmdCd": "",
            "rdDspslPlcAdongSdCd": "", "rdDspslPlcAdongSggCd": "", "rdDspslPlcAdongEmdCd": "",
            "rdnmSdCd": "", "rdnmSggCd": "", "rdnmNo": "",
            "lclDspslGdsLstUsgCd": lcl_cd, "mclDspslGdsLstUsgCd": mcl_cd, "sclDspslGdsLstUsgCd": scl_cd,
            "notifyLoc": "", "objctArDtsMax": "", "objctArDtsMin": "",
            "statNum": 1, "sideDvsCd": "", "grbxTypCd": "", "fuelKndCd": "",
            "carMdyrMax": "", "carMdyrMin": "", "carMdlNm": "", "cortAuctnMbrsId": "",
        }
    }
    res = requests.post(URL_SEARCH, headers=HEADERS_SEARCH, json=payload)
    inner = res.json().get("data") or {}
    rows = inner.get("dlt_srchResult") or []
    total = (inner.get("dma_pageInfo") or {}).get("totalCnt") or 0
    return rows, int(total)


# ===== Vercel API 호출 =====
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
        if isinstance(items, list):
            return items
        elif items:
            return [items]
        return []
    except:
        return []


def vercel_realtrade(lawd_cd):
    try:
        now = date.today()
        ym = f"{now.year}{now.month:02d}"
        r = requests.get(f"{VERCEL_BASE}/realtrade?lawdCd={lawd_cd}&dealYmd={ym}", timeout=15)
        data = r.json()
        return data.get("items") or []
    except:
        return []


# ===== 세션 초기화 =====
if "results" not in st.session_state:
    st.session_state.results = None
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# ===== 메인 =====
st.markdown("## 🏛️ 경매 전문 관리 시스템")
st.caption("새로공인중개사사무소 · 최나림")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 검색", "📊 종합분석", "⭐ 관심물건", "👥 의뢰인", "📅 일정"])


# ═══════════════════════════════════════════
# 탭 1: 검색
# ═══════════════════════════════════════════
with tab1:
    st.subheader("📍 지역")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        sd_map = get_sd_list()
        sd_label = st.selectbox("시/도", ["선택 안함"] + list(sd_map.keys()))
        sd_cd = sd_map.get(sd_label, "")
    with r1c2:
        sgg_map = get_sgg_list(sd_cd)
        sgg_label = st.selectbox("시/군/구", ["선택 안함"] + list(sgg_map.keys()))
        sgg_cd = sgg_map.get(sgg_label, "")
    with r1c3:
        emd_map = get_emd_list(sd_cd, sgg_cd)
        emd_label = st.selectbox("읍/면/동", ["선택 안함"] + list(emd_map.keys()))
        emd_cd = emd_map.get(emd_label, "")

    st.subheader("🏗️ 용도")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        lcl_map = get_lcl_list()
        lcl_label = st.selectbox("대분류", ["선택 안함"] + list(lcl_map.keys()))
        lcl_cd = lcl_map.get(lcl_label, "")
    with r2c2:
        mcl_map = get_mcl_list(lcl_cd)
        mcl_label = st.selectbox("중분류", ["선택 안함"] + list(mcl_map.keys()))
        mcl_cd = mcl_map.get(mcl_label, "")
    with r2c3:
        scl_map = get_scl_list(mcl_cd)
        scl_label = st.selectbox("소분류", ["선택 안함"] + list(scl_map.keys()))
        scl_cd = scl_map.get(scl_label, "")

    st.subheader("🔍 검색 조건")
    r3c1, r3c2, r3c3, r3c4, r3c5 = st.columns(5)
    with r3c1:
        obj_label = st.selectbox("물건종류", list(OBJ_TYPES.keys()))
    with r3c2:
        cs_no = st.text_input("사건번호", "")
    with r3c3:
        min_price = st.text_input("감정가 이상(만원)", "")
    with r3c4:
        max_price = st.text_input("감정가 이하(만원)", "")
    with r3c5:
        use_date = st.checkbox("기간 설정", value=False)

    if use_date:
        dc1, dc2 = st.columns(2)
        with dc1:
            date_from = st.date_input("시작", value=date.today())
        with dc2:
            date_to = st.date_input("종료", value=date.today() + timedelta(days=14))
    else:
        date_from, date_to = None, None

    if st.button("🔍 검색", type="primary", use_container_width=True):
        obj_type = OBJ_TYPES[obj_label]
        min_p = str(int(min_price) * 10000) if min_price else ""
        max_p = str(int(max_price) * 10000) if max_price else ""
        d_from = date_from.strftime("%Y%m%d") if date_from else ""
        d_to = date_to.strftime("%Y%m%d") if date_to else ""

        all_rows = []
        status = st.empty()
        progress = st.progress(0)

        first_rows, total = fetch_page(1, sd_cd, sgg_cd, emd_cd, min_p, max_p, obj_type, cs_no, lcl_cd, mcl_cd, scl_cd, d_from, d_to)
        all_rows.extend(first_rows)
        total_pages = max(1, -(-total // 10))
        st.info(f"전체 {total}건 / {total_pages}페이지")

        for page_no in range(2, min(total_pages + 1, 101)):
            status.text(f"{page_no}/{total_pages} 페이지 수집 중...")
            progress.progress(page_no / min(total_pages, 100))
            rows, _ = fetch_page(page_no, sd_cd, sgg_cd, emd_cd, min_p, max_p, obj_type, cs_no, lcl_cd, mcl_cd, scl_cd, d_from, d_to)
            if not rows:
                break
            all_rows.extend(rows)
            time.sleep(0.3)

        progress.progress(1.0)
        status.text(f"완료: {len(all_rows)}건")
        st.session_state.results = all_rows if all_rows else None

    # 결과 표시
    results = st.session_state.results
    if results:
        df = pd.DataFrame(results)

        col_map = {
            "srnSaNo": "사건번호", "jiwonNm": "법원",
            "printSt": "소재지", "dspslUsgNm": "물건종류",
            "gamevalAmt": "감정가", "minmaePrice": "최저가",
            "yuchalCnt": "유찰", "maeGiil": "매각기일",
        }

        display_cols = [k for k in col_map.keys() if k in df.columns]
        df_display = df[display_cols].copy() if display_cols else df.copy()
        df_display.columns = [col_map.get(c, c) for c in df_display.columns]

        for col in ["감정가", "최저가"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(lambda x: fmt_price(x))
        if "매각기일" in df_display.columns:
            df_display["매각기일"] = df_display["매각기일"].apply(lambda x: fmt_date(x))

        st.subheader(f"📋 검색 결과 ({len(df)}건)")
        event = st.dataframe(df_display, use_container_width=True, hide_index=True,
                             on_select="rerun", selection_mode="single-row", key="result_table")

        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        st.download_button("📥 엑셀 다운로드", buf, "경매결과.xlsx")

        sel = event.selection.rows if event and event.selection else []
        if sel:
            row = df.iloc[sel[0]].to_dict()
            st.session_state.selected_row = row
            st.info("📊 **종합분석** 탭에서 상세 분석을 확인하세요!")

            if st.button("⭐ 관심물건 등록"):
                cs = _pick(row, "srnSaNo", "userCsNo", "csNo")
                addr = _pick(row, "printSt", "rprsAdongNm")
                appr = safe_int(row.get("gamevalAmt") or row.get("aeeEvlAmt") or 0)
                low = safe_int(row.get("minmaePrice") or row.get("lwsDspslPrc") or 0)
                fail = safe_int(row.get("yuchalCnt") or row.get("flbdNcnt") or 0)
                sale_date = _pick(row, "maeGiil", "dspslDxdyYmd")

                item = {
                    "caseNo": cs, "address": addr,
                    "appraisal": appr, "minPrice": low,
                    "failCount": fail, "saleDate": sale_date,
                    "status": "입찰예정", "memo": "",
                    "raw": row
                }
                if not any(w["caseNo"] == cs for w in st.session_state.watchlist):
                    st.session_state.watchlist.append(item)
                    st.success(f"⭐ {cs} 관심등록 완료!")
                else:
                    st.warning("이미 등록된 물건입니다.")


# ═══════════════════════════════════════════
# 탭 2: 종합분석
# ═══════════════════════════════════════════
with tab2:
    st.subheader("📊 물건 종합 분석")

    row = st.session_state.selected_row
    manual_addr = st.text_input("주소 직접 입력 (검색 탭에서 선택하거나 여기에 입력)", value="")

    if row or manual_addr:
        if manual_addr:
            address = manual_addr
        elif row:
            address = _pick(row, "printSt", "rprsAdongNm", "adongNm")
        else:
            address = ""

        if not address:
            st.warning("주소를 찾을 수 없습니다.")
        else:
            # ── 경매 정보 ──
            if row:
                st.markdown("### 📋 경매 정보")
                cs = _pick(row, "srnSaNo", "userCsNo", "csNo")
                court = _pick(row, "jiwonNm", "cortOfcNm")
                appr = safe_int(row.get("gamevalAmt") or row.get("aeeEvlAmt") or 0)
                low = safe_int(row.get("minmaePrice") or row.get("lwsDspslPrc") or 0)
                fail = safe_int(row.get("yuchalCnt") or row.get("flbdNcnt") or 0)
                sale_date = _pick(row, "maeGiil", "dspslDxdyYmd")
                rate = safe_int(row.get("notifyMinmaePriceRate1") or row.get("lwsDspslPrcRate") or 0)
                deposit = int(low * 0.1) if low else 0

                ac1, ac2, ac3, ac4 = st.columns(4)
                ac1.metric("감정가", fmt_price(appr))
                ac2.metric("최저가", fmt_price(low))
                ac3.metric("유찰횟수", f"{fail}회")
                ac4.metric("최저가율", f"{rate}%" if rate else "-")

                ac5, ac6, ac7, ac8 = st.columns(4)
                ac5.metric("법원", court)
                ac6.metric("사건번호", cs)
                ac7.metric("매각기일", fmt_date(sale_date))
                ac8.metric("보증금(10%)", fmt_price(deposit))

            st.divider()

            # ── Vercel API 호출 ──
            with st.spinner("🔄 토지·건물·실거래 데이터 조회 중..."):
                geo = vercel_geocode(address)

            pnu = geo.get("pnu")
            lat = geo.get("latitude") or geo.get("lat")
            lon = geo.get("longitude") or geo.get("lon") or geo.get("lng")

            if not pnu:
                st.error(f"❌ PNU를 찾을 수 없습니다: {address}")
            else:
                st.caption(f"PNU: {pnu} · 좌표: {lat}, {lon}")

                with st.spinner("토지특성·건축물·실거래 조회 중..."):
                    land = vercel_land(pnu)
                    buildings = vercel_building(pnu)
                    lawd_cd = pnu[:5]
                    trades = vercel_realtrade(lawd_cd)

                # ── 토지 정보 ──
                st.markdown("### 📐 토지 정보")
                if land:
                    area = float(land.get("lndpclAr", 0) or 0)
                    jiga = int(float(land.get("pblntfPclnd", 0) or 0))

                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("지목", land.get("lndcgrCodeNm", "-"))
                    lc2.metric("면적", f"{area:,.1f}㎡ ({area/3.3058:.1f}평)" if area else "-")
                    lc3.metric("용도지역", land.get("prposArea1Nm", "-"))

                    lc4, lc5, lc6 = st.columns(3)
                    lc4.metric("공시지가", f"{jiga:,}원/㎡" if jiga else "-")
                    lc5.metric("도로접면", land.get("roadSideCodeNm", "-"))
                    lc6.metric("이용상황", land.get("ladUseSittnNm", "-"))

                    if jiga > 0 and area > 0:
                        total_jiga = int(jiga * area)
                        st.info(f"📌 공시지가 총액: **{fmt_price(total_jiga)}** · 기준연도: {land.get('stdrYear', '-')}년")
                        if row and appr:
                            ratio = appr / total_jiga * 100 if total_jiga > 0 else 0
                            st.info(f"📌 감정가 / 공시지가 총액: **{ratio:.1f}%**")

                    checks = []
                    yongdo = land.get("prposArea1Nm", "")
                    jimok = land.get("lndcgrCodeNm", "")
                    road = land.get("roadSideCodeNm", "")
                    if "농림" in yongdo:
                        checks.append("⚠️ 농림지역 — 농지전용 필요")
                    if "보전" in yongdo:
                        checks.append("⚠️ 보전지역 — 개발제한")
                    if jimok in ("전", "답", "과수원"):
                        checks.append("ℹ️ 농취증 필요")
                    if jimok == "임야":
                        checks.append("ℹ️ 산지관리법 적용")
                    if "맹지" in road or road == "":
                        checks.append("⚠️ 도로 접면 확인 필요")
                    if "계획관리" in yongdo:
                        checks.append("✅ 계획관리지역 — 개발 가능성 양호")
                    if checks:
                        st.markdown("**⚠️ 규제 체크리스트**")
                        for c in checks:
                            st.markdown(f"- {c}")
                else:
                    st.warning("토지 정보를 가져오지 못했습니다.")

                # ── 건물 정보 ──
                st.markdown("### 🏢 건물 정보")
                if buildings:
                    for b in buildings[:5]:
                        bc1, bc2, bc3 = st.columns(3)
                        bc1.metric("용도", b.get("mainPurpsCdNm", "-"))
                        bc2.metric("구조", b.get("strctCdNm", "-"))
                        bc3.metric("연면적", f"{float(b.get('totArea', 0)):,.1f}㎡" if b.get("totArea") else "-")

                        bc4, bc5, bc6 = st.columns(3)
                        bc4.metric("층수", f"지상{b.get('grndFlrCnt', 0)} / 지하{b.get('ugrndFlrCnt', 0)}")
                        use_apr = str(b.get("useAprDay", ""))
                        bc5.metric("사용승인", fmt_date(use_apr))
                        bc6.metric("건물명", b.get("bldNm", "-") or "-")
                else:
                    st.info("🏗️ 건축물대장에 등록된 건물 없음 — **나지(裸地)**로 판단")

                # ── 실거래가 ──
                st.markdown("### 📈 주변 실거래가 (최근 6개월)")
                avg_p = 0
                if trades:
                    addr_parts = address.split()
                    umd = ""
                    for p in addr_parts:
                        if p.endswith(("읍", "면", "동", "리")):
                            umd = p
                            break

                    same_umd = [t for t in trades if umd and t.get("umdNm") and umd in t["umdNm"]] if umd else []
                    prices_per_pyeong = []

                    if same_umd:
                        for t in same_umd:
                            amt = safe_int(str(t.get("dealAmount", "0")).replace(",", "")) * 10000
                            area_t = float(t.get("dealArea", 0) or 0)
                            if area_t > 0:
                                prices_per_pyeong.append(int(amt / area_t * 3.3058))

                        if prices_per_pyeong:
                            avg_p = sum(prices_per_pyeong) // len(prices_per_pyeong)
                            min_pp = min(prices_per_pyeong)
                            max_pp = max(prices_per_pyeong)

                            tc1, tc2, tc3, tc4 = st.columns(4)
                            tc1.metric(f"{umd} 거래", f"{len(same_umd)}건")
                            tc2.metric("평균", f"{avg_p:,}원/평")
                            tc3.metric("최저", f"{min_pp:,}원/평")
                            tc4.metric("최고", f"{max_pp:,}원/평")

                    trade_display = []
                    for t in trades[:20]:
                        amt = safe_int(str(t.get("dealAmount", "0")).replace(",", "")) * 10000
                        area_t = float(t.get("dealArea", 0) or 0)
                        pp = int(amt / area_t * 3.3058) if area_t > 0 else 0
                        trade_display.append({
                            "거래일": f"{t.get('dealYear', '')}.{str(t.get('dealMonth', '')).zfill(2)}.{str(t.get('dealDay', '')).zfill(2)}",
                            "읍면동": t.get("umdNm", ""),
                            "지목": t.get("jimok", ""),
                            "면적(㎡)": area_t,
                            "거래가": fmt_price(amt),
                            "평단가": f"{pp:,}원/평" if pp else "-",
                            "유형": t.get("dealingGbn", "")
                        })
                    if trade_display:
                        st.dataframe(pd.DataFrame(trade_display), use_container_width=True, hide_index=True)
                else:
                    st.info("최근 6개월 실거래 내역 없음")

                # ── 투자분석 ──
                if row:
                    if low and area:
                        st.markdown("### 💰 투자 분석 요약")
                        pp_low = int(low / (area / 3.3058)) if area > 0 else 0

                        ic1, ic2, ic3 = st.columns(3)
                        ic1.metric("최저가 평단가", f"{pp_low:,}원/평" if pp_low else "-")
                        if jiga > 0 and area > 0:
                            ic2.metric("최저가/공시지가", f"{low / (jiga * area) * 100:.1f}%")
                        if avg_p > 0 and pp_low > 0:
                            diff = ((pp_low - avg_p) / avg_p * 100)
                            ic3.metric("실거래 평균 대비", f"{diff:+.1f}%")

                    st.markdown("**⚠️ 현장 확인 체크리스트**")
                    st.markdown("""
- □ 진입로 확보 여부
- □ 형질변경/개발행위 가능 여부
- □ 분묘/지장물/폐기물 확인
- □ 임차인/유치권 여부
- □ 법정지상권 성립 여부
- □ 지분매각 여부
""")

                # ── 버튼 ──
                st.divider()
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    st.link_button("📝 입찰 신청서 보내기", "https://realty-board.vercel.app/bid-form.html")
                with bc2:
                    st.link_button("📄 기일입찰표 작성", "https://realty-board.vercel.app/bid-sheet.html")
                with bc3:
                    st.link_button("📋 확인설명서", "https://realty-board.vercel.app/auction-form.html")
    else:
        st.info("🔍 검색 탭에서 물건을 선택하거나, 위에 주소를 입력하세요.")


# ═══════════════════════════════════════════
# 탭 3: 관심물건
# ═══════════════════════════════════════════
with tab3:
    st.subheader("⭐ 관심물건 관리")

    watchlist = st.session_state.watchlist

    if not watchlist:
        st.info("검색 탭에서 물건을 선택 후 '⭐ 관심물건 등록' 버튼을 눌러주세요.")
    else:
        for i, item in enumerate(watchlist):
            sale = item.get("saleDate", "")
            d_day_str = "-"
            urgent = "⚪"
            if sale and len(str(sale)) == 8:
                try:
                    sale_date_obj = date(int(str(sale)[:4]), int(str(sale)[4:6]), int(str(sale)[6:]))
                    d_day = (sale_date_obj - date.today()).days
                    d_day_str = f"D-{d_day}" if d_day > 0 else ("D-Day" if d_day == 0 else f"D+{abs(d_day)}")
                    urgent = "🔴" if d_day <= 3 else ("🟡" if d_day <= 7 else "🟢")
                except:
                    pass

            with st.expander(f"{urgent} {item['caseNo']} — {item['address']} | {fmt_price(item['minPrice'])} | {d_day_str}", expanded=False):
                wc1, wc2, wc3, wc4 = st.columns(4)
                wc1.metric("감정가", fmt_price(item["appraisal"]))
                wc2.metric("최저가", fmt_price(item["minPrice"]))
                wc3.metric("유찰", f"{item['failCount']}회")
                wc4.metric("매각기일", fmt_date(item.get("saleDate", "")))

                new_status = st.selectbox("상태", ["입찰예정", "입찰완료", "낙찰", "패찰", "포기"],
                                         index=["입찰예정", "입찰완료", "낙찰", "패찰", "포기"].index(item.get("status", "입찰예정")),
                                         key=f"status_{i}")
                item["status"] = new_status

                memo = st.text_area("메모", value=item.get("memo", ""), key=f"memo_{i}")
                item["memo"] = memo

                mc1, mc2 = st.columns(2)
                with mc1:
                    if st.button("📊 종합분석", key=f"analyze_{i}"):
                        st.session_state.selected_row = item.get("raw", {})
                        st.info("📊 종합분석 탭을 확인하세요.")
                with mc2:
                    if st.button("🗑️ 삭제", key=f"delete_{i}"):
                        st.session_state.watchlist.pop(i)
                        st.rerun()


# ═══════════════════════════════════════════
# 탭 4: 의뢰인 관리
# ═══════════════════════════════════════════
with tab4:
    st.subheader("👥 의뢰인 접수 현황")

    try:
        notion_res = requests.get(f"{VERCEL_BASE}/notion-bid-list", timeout=10)
        notion_data = notion_res.json()
        items = notion_data.get("items") or []

        if not items:
            st.info("접수된 의뢰인이 없습니다.")
        else:
            for ni, item in enumerate(items):
                bid_type_icon = "🏢" if item.get("bidType") == "법인" else "👤"
                sale = item.get("saleDate", "")
                d_str = "-"
                if sale:
                    try:
                        sd_obj = date.fromisoformat(sale)
                        d = (sd_obj - date.today()).days
                        d_str = f"D-{d}" if d > 0 else ("D-Day" if d == 0 else f"D+{abs(d)}")
                    except:
                        pass

                with st.expander(f"{bid_type_icon} {item.get('caseNo', '-')} | {item.get('name', '-')} | {item.get('court', '-')} | {d_str}"):
                    nc1, nc2, nc3, nc4 = st.columns(4)
                    nc1.metric("사건번호", item.get("caseNo", "-"))
                    nc2.metric("법원", item.get("court", "-"))
                    nc3.metric("매각기일", sale or "-")
                    nc4.metric("입찰가", fmt_price(item.get("bidPrice", 0)))

                    nc5, nc6, nc7, nc8 = st.columns(4)
                    nc5.metric("성명", item.get("name", "-"))
                    nc6.metric("연락처", item.get("phone", "-"))
                    nc7.metric("입찰유형", item.get("bidType", "-"))
                    nc8.metric("은행", item.get("bank", "-"))

                    st.text(f"주소: {item.get('address', '-')}")
                    st.text(f"계좌: {item.get('account', '-')}")

                    if item.get("bidType") == "법인":
                        st.text(f"회사: {item.get('company', '-')} | 사업자: {item.get('bizNo', '-')} | 법인: {item.get('corpNo', '-')}")

                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.link_button("📄 입찰표 작성", "https://realty-board.vercel.app/bid-sheet.html")
                    with dc2:
                        st.link_button("📋 확인설명서", "https://realty-board.vercel.app/auction-form.html")

    except Exception as e:
        st.error(f"노션 연동 실패: {e}")


# ═══════════════════════════════════════════
# 탭 5: 입찰 일정
# ═══════════════════════════════════════════
with tab5:
    st.subheader("📅 입찰 일정 대시보드")

    all_schedule = []

    for item in st.session_state.watchlist:
        sale = item.get("saleDate", "")
        all_schedule.append({
            "유형": "⭐ 관심",
            "사건번호": item.get("caseNo", "-"),
            "소재지": item.get("address", "-"),
            "금액": fmt_price(item.get("minPrice", 0)),
            "매각기일": fmt_date(sale),
            "상태": item.get("status", "-"),
            "_sort": str(sale) if sale else "99999999"
        })

    try:
        notion_res2 = requests.get(f"{VERCEL_BASE}/notion-bid-list", timeout=10)
        notion_items2 = notion_res2.json().get("items") or []
        for item in notion_items2:
            sale = item.get("saleDate", "")
            all_schedule.append({
                "유형": "👥 의뢰",
                "사건번호": item.get("caseNo", "-"),
                "소재지": f"{item.get('name', '')} ({item.get('court', '')})",
                "금액": fmt_price(item.get("bidPrice", 0)),
                "매각기일": sale or "-",
                "상태": "접수",
                "_sort": sale.replace("-", "") if sale else "99999999"
            })
    except:
        pass

    if all_schedule:
        all_schedule.sort(key=lambda x: x.get("_sort", "99999999"))
        df_schedule = pd.DataFrame(all_schedule).drop(columns=["_sort"])
        st.dataframe(df_schedule, use_container_width=True, hide_index=True)
    else:
        st.info("관심물건 등록 또는 의뢰인 접수가 없습니다.")
